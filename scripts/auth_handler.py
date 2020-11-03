import base64
import json
import logging.config
import os
import time
from collections import Counter

from ldap3 import Connection
from ldap3 import Server
from ldap3 import BASE
from ldap3 import MODIFY_REPLACE

from jans.pycloudlib.persistence.couchbase import CouchbaseClient
from jans.pycloudlib.persistence.couchbase import get_couchbase_user
from jans.pycloudlib.persistence.couchbase import get_couchbase_password
from jans.pycloudlib.utils import decode_text
from jans.pycloudlib.utils import encode_text
from jans.pycloudlib.utils import exec_cmd
from jans.pycloudlib.utils import generate_base64_contents
from jans.pycloudlib.utils import as_boolean
from jans.pycloudlib.meta import DockerMeta
from jans.pycloudlib.meta import KubernetesMeta

from base_handler import BaseHandler
from settings import LOGGING_CONFIG

logging.config.dictConfig(LOGGING_CONFIG)
logger = logging.getLogger("certmanager")

SIG_KEYS = "RS256 RS384 RS512 ES256 ES384 ES512 PS256 PS384 PS512"
ENC_KEYS = "RSA1_5 RSA-OAEP"


def key_expired(exp):
    now = int(time.time()) * 1000  # in milliseconds
    return now >= exp


def keytool_import_key(src_jks_fn, dest_jks_fn, alias, password):
    cmd = f"keytool -importkeystore -srckeystore {src_jks_fn} -srcstorepass {password} -srcalias {alias} -destkeystore {dest_jks_fn} -deststorepass {password} -destalias {alias}"
    return exec_cmd(cmd)


def encode_jks(manager, jks="/etc/certs/oxauth-keys.jks"):
    encoded_jks = ""
    with open(jks, "rb") as fd:
        encoded_jks = encode_text(fd.read(), manager.secret.get("encoded_salt"))
    return encoded_jks


def generate_openid_keys(passwd, jks_path, dn, exp=48):
    if os.path.isfile(jks_path):
        os.unlink(jks_path)

    cmd = (
        "java -Dlog4j.defaultInitOverride=true "
        "-jar /app/javalibs/oxauth-client.jar "
        f"-enc_keys {ENC_KEYS} -sig_keys {SIG_KEYS} "
        f"-dnname '{dn}' -expiration_hours {exp} "
        f"-keystore {jks_path} -keypasswd {passwd}"
    )
    return exec_cmd(cmd)


class BasePersistence(object):
    def get_oxauth_config(self):
        raise NotImplementedError

    def modify_oxauth_config(self, id_, ox_rev, conf_dynamic, conf_webkeys):
        raise NotImplementedError


class LdapPersistence(BasePersistence):
    def __init__(self, host, user, password):
        ldap_server = Server(host, port=1636, use_ssl=True)
        self.backend = Connection(ldap_server, user, password)
        self.namespace = os.environ.get("CN_NAMESPACE", "jans")

    def get_oxauth_config(self):
        # base DN for oxAuth config
        oxauth_base = ",".join([
            "ou=oxauth",
            "ou=configuration",
            f"o={self.namespace}",
        ])

        with self.backend as conn:
            conn.search(
                search_base=oxauth_base,
                search_filter="(objectClass=*)",
                search_scope=BASE,
                attributes=[
                    "oxRevision",
                    "oxAuthConfWebKeys",
                    "oxAuthConfDynamic",
                ]
            )

            if not conn.entries:
                return {}

            entry = conn.entries[0]

            config = {
                "id": entry.entry_dn,
                "oxRevision": entry["oxRevision"][0],
                "oxAuthConfWebKeys": entry["oxAuthConfWebKeys"][0],
                "oxAuthConfDynamic": entry["oxAuthConfDynamic"][0],
            }
            return config

    def modify_oxauth_config(self, id_, ox_rev, conf_dynamic, conf_webkeys):
        with self.backend as conn:
            conn.modify(id_, {
                'oxRevision': [(MODIFY_REPLACE, [str(ox_rev)])],
                'oxAuthConfWebKeys': [(MODIFY_REPLACE, [json.dumps(conf_webkeys)])],
                'oxAuthConfDynamic': [(MODIFY_REPLACE, [json.dumps(conf_dynamic)])],
            })

            result = conn.result["description"]
            return result == "success"


class CouchbasePersistence(BasePersistence):
    def __init__(self, host, user, password):
        self.backend = CouchbaseClient(host, user, password)
        self.namespace = os.environ.get("CN_NAMESPACE", "jans")

    def get_oxauth_config(self):
        req = self.backend.exec_query(
            "SELECT oxRevision, oxAuthConfDynamic, oxAuthConfWebKeys "
            f"FROM `{self.namespace}` "
            "USE KEYS 'configuration_oxauth'",
        )
        if not req.ok:
            return {}

        config = req.json()["results"][0]

        if not config:
            return {}

        config.update({"id": "configuration_oxauth"})
        return config

    def modify_oxauth_config(self, id_, ox_rev, conf_dynamic, conf_webkeys):
        conf_dynamic = json.dumps(conf_dynamic)
        conf_webkeys = json.dumps(conf_webkeys)

        req = self.backend.exec_query(
            f"UPDATE `{self.namespace}` USE KEYS '{id_}' "
            f"SET oxRevision={ox_rev}, oxAuthConfDynamic={conf_dynamic}, "
            f"oxAuthConfWebKeys={conf_webkeys} "
            "RETURNING oxRevision"
        )

        if not req.ok:
            return False
        return True


class AuthHandler(BaseHandler):
    def __init__(self, manager, dry_run, **opts):
        super().__init__(manager, dry_run, **opts)

        persistence_type = os.environ.get("CN_PERSISTENCE_TYPE", "ldap")
        ldap_mapping = os.environ.get("CN_PERSISTENCE_LDAP_MAPPING", "default")

        if persistence_type in ("ldap", "couchbase"):
            backend_type = persistence_type
        else:
            # persistence_type is hybrid
            if ldap_mapping == "default":
                backend_type = "ldap"
            else:
                backend_type = "couchbase"

        # resolve backend
        if backend_type == "ldap":
            host = os.environ.get("CN_LDAP_URL", "localhost:1636")
            user = manager.config.get("ldap_binddn")
            password = decode_text(
                manager.secret.get("encoded_ox_ldap_pw"),
                manager.secret.get("encoded_salt"),
            )
            backend_cls = LdapPersistence
        else:
            host = os.environ.get("CN_COUCHBASE_URL", "localhost")
            user = get_couchbase_user(manager)
            password = get_couchbase_password(manager)
            backend_cls = CouchbasePersistence

        self.backend = backend_cls(host, user, password)
        self.rotation_interval = opts.get("interval", 48)
        self.push_keys = as_boolean(opts.get("push-to-container", True))

        metadata = os.environ.get("CN_CONTAINER_METADATA", "docker")
        if metadata == "kubernetes":
            self.meta_client = KubernetesMeta()
        else:
            self.meta_client = DockerMeta()

    def get_merged_keys(self, exp_hours):
        # get previous JWKS
        old_jwks = json.loads(
            base64.b64decode(self.manager.secret.get("oxauth_openid_key_base64"))
        ).get("keys", [])

        # get previous JKS
        old_jks_fn = "/etc/certs/oxauth-keys.old.jks"
        self.manager.secret.to_file("oxauth_jks_base64", old_jks_fn, decode=True, binary_mode=True)

        # generate new JWKS and JKS
        jks_pass = self.manager.secret.get("oxauth_openid_jks_pass")
        jks_dn = r"{}".format(self.manager.config.get("default_openid_jks_dn_name"))
        jks_fn = "/etc/certs/oxauth-keys.jks"
        jwks_fn = "/etc/certs/oxauth-keys.json"
        logger.info(f"Generating new {jwks_fn} and {jks_fn}")
        out, err, retcode = generate_openid_keys(jks_pass, jks_fn, jks_dn, exp=exp_hours)

        if retcode != 0:
            logger.error(f"Unable to generate keys; reason={err.decode()}")
            return

        new_jwks = json.loads(out).get("keys", [])

        logger.info("Merging non-expired keys from previous rotation (if any)")
        for jwk in old_jwks:
            # filter out expired key
            if key_expired(jwk["exp"]):
                continue

            # cannot have more than 2 keys for same algorithm in new JWKS
            cnt = Counter(j["alg"] for j in new_jwks)
            if cnt[jwk["alg"]] >= 2:
                continue

            # add key to new JWKS
            new_jwks.append(jwk)
            # import key to new JKS
            keytool_import_key(old_jks_fn, jks_fn, jwk["kid"], jks_pass)

        # update new JWKS file
        with open(jwks_fn, "w") as f:
            data = {"keys": new_jwks}
            f.write(json.dumps(data, indent=2))

        # finalizing
        return jwks_fn, jks_fn

    def patch(self):
        config = self.backend.get_oxauth_config()

        if not config:
            # search failed due to missing entry
            logger.warning("Unable to find oxAuth config")
            return

        try:
            conf_dynamic = json.loads(config["oxAuthConfDynamic"])
        except TypeError:  # not string/buffer
            conf_dynamic = config["oxAuthConfDynamic"]

        if conf_dynamic["keyRegenerationEnabled"]:
            logger.warning("keyRegenerationEnabled config was set to true; "
                           "skipping proccess to avoid conflict with "
                           "builtin key rotation feature in oxAuth")
            return

        jks_pass = self.manager.secret.get("oxauth_openid_jks_pass")

        conf_dynamic.update({
            "keyRegenerationEnabled": False,  # always set to False
            "keyRegenerationInterval": int(self.rotation_interval),
            "webKeysStorage": "keystore",
            "keyStoreSecret": jks_pass,
        })

        exp_hours = int(self.rotation_interval) + int(conf_dynamic["idTokenLifetime"] / 3600)

        jwks_fn, jks_fn = self.get_merged_keys(exp_hours)

        if self.dry_run:
            return

        oxauth_containers = []

        if self.push_keys:
            oxauth_containers = self.meta_client.get_containers("APP_NAME=oxauth")
            if not oxauth_containers:
                logger.warning(
                    "Unable to find any oxAuth container; make sure "
                    "to deploy oxAuth and set APP_NAME=oxauth "
                    "label on container level"
                )
                # exit immediately to avoid persistence/secrets being modified
                return

        for container in oxauth_containers:
            name = self.meta_client.get_container_name(container)

            logger.info(f"creating backup of {name}:{jks_fn}")
            self.meta_client.exec_cmd(container, f"cp {jks_fn} {jks_fn}.backup")
            logger.info(f"creating new {name}:{jks_fn}")
            self.meta_client.copy_to_container(container, jks_fn)

            logger.info(f"creating backup of {name}:{jwks_fn}")
            self.meta_client.exec_cmd(container, "cp {jwks_fn} {jwks_fn}.backup")
            logger.info(f"creating new {name}:{jwks_fn}")
            self.meta_client.copy_to_container(container, jwks_fn)

        try:
            with open(jwks_fn) as f:
                keys = json.loads(f.read())

            logger.info("modifying oxAuth configuration")
            ox_rev = int(config["oxRevision"])
            ox_modified = self.backend.modify_oxauth_config(
                config["id"],
                ox_rev + 1,
                conf_dynamic,
                keys,
            )

            if not ox_modified:
                # restore jks and jwks
                logger.warning("failed to modify oxAuth configuration")
                for container in oxauth_containers:
                    name = self.meta_client.get_container_name(container)
                    logger.info(f"restoring backup of {name}:{jks_fn}")
                    self.meta_client.exec_cmd(container, "cp {jks_fn}.backup {jks_fn}")
                    logger.info(f"restoring backup of {name}:{jwks_fn}")
                    self.meta_client.exec_cmd(container, "cp {jwks_fn}.backup {jwks_fn}")
                return

            self.manager.secret.set("oxauth_jks_base64", encode_jks(self.manager))
            self.manager.config.set("oxauth_key_rotated_at", int(time.time()))
            self.manager.secret.set("oxauth_openid_jks_pass", jks_pass)
            # jwks
            self.manager.secret.set(
                "oxauth_openid_key_base64",
                generate_base64_contents(json.dumps(keys)),
            )
        except (TypeError, ValueError,) as exc:
            logger.warning(f"Unable to get public keys; reason={exc}")
