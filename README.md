## Overview

Container image to manage X.509 certificates and crypto keys in Janssen Server.
The container designed to run as one-time command (or Job in kubernetes world).

## Versions

See [Releases](https://github.com/JanssenProject/docker-jans-certmanager/releases) for stable versions.
For bleeding-edge/unstable version, use `janssenproject/certmanager:5.00_dev`.

## Environment Variables

The following environment variables are supported by the container:

- `JANS_CONFIG_ADAPTER`: The config backend adapter, can be `consul` (default) or `kubernetes`.
- `JANS_CONFIG_CONSUL_HOST`: hostname or IP of Consul (default to `localhost`).
- `JANS_CONFIG_CONSUL_PORT`: port of Consul (default to `8500`).
- `JANS_CONFIG_CONSUL_CONSISTENCY`: Consul consistency mode (choose one of `default`, `consistent`, or `stale`). Default to `stale` mode.
- `JANS_CONFIG_CONSUL_SCHEME`: supported Consul scheme (`http` or `https`).
- `JANS_CONFIG_CONSUL_VERIFY`: whether to verify cert or not (default to `false`).
- `JANS_CONFIG_CONSUL_CACERT_FILE`: path to Consul CA cert file (default to `/etc/certs/consul_ca.crt`). This file will be used if it exists and `JANS_CONFIG_CONSUL_VERIFY` set to `true`.
- `JANS_CONFIG_CONSUL_CERT_FILE`: path to Consul cert file (default to `/etc/certs/consul_client.crt`).
- `JANS_CONFIG_CONSUL_KEY_FILE`: path to Consul key file (default to `/etc/certs/consul_client.key`).
- `JANS_CONFIG_CONSUL_TOKEN_FILE`: path to file contains ACL token (default to `/etc/certs/consul_token`).
- `JANS_CONFIG_KUBERNETES_NAMESPACE`: Kubernetes namespace (default to `default`).
- `JANS_CONFIG_KUBERNETES_CONFIGMAP`: Kubernetes configmaps name (default to `jans`).
- `JANS_CONFIG_KUBERNETES_USE_KUBE_CONFIG`: Load credentials from `$HOME/.kube/config`, only useful for non-container environment (default to `false`).
- `JANS_SECRET_ADAPTER`: The secrets adapter, can be `vault` or `kubernetes`.
- `JANS_SECRET_VAULT_SCHEME`: supported Vault scheme (`http` or `https`).
- `JANS_SECRET_VAULT_HOST`: hostname or IP of Vault (default to `localhost`).
- `JANS_SECRET_VAULT_PORT`: port of Vault (default to `8200`).
- `JANS_SECRET_VAULT_VERIFY`: whether to verify cert or not (default to `false`).
- `JANS_SECRET_VAULT_ROLE_ID_FILE`: path to file contains Vault AppRole role ID (default to `/etc/certs/vault_role_id`).
- `JANS_SECRET_VAULT_SECRET_ID_FILE`: path to file contains Vault AppRole secret ID (default to `/etc/certs/vault_secret_id`).
- `JANS_SECRET_VAULT_CERT_FILE`: path to Vault cert file (default to `/etc/certs/vault_client.crt`).
- `JANS_SECRET_VAULT_KEY_FILE`: path to Vault key file (default to `/etc/certs/vault_client.key`).
- `JANS_SECRET_VAULT_CACERT_FILE`: path to Vault CA cert file (default to `/etc/certs/vault_ca.crt`). This file will be used if it exists and `JANS_SECRET_VAULT_VERIFY` set to `true`.
- `JANS_SECRET_KUBERNETES_NAMESPACE`: Kubernetes namespace (default to `default`).
- `JANS_SECRET_KUBERNETES_CONFIGMAP`: Kubernetes secrets name (default to `jans`).
- `JANS_SECRET_KUBERNETES_USE_KUBE_CONFIG`: Load credentials from `$HOME/.kube/config`, only useful for non-container environment (default to `false`).
- `JANS_PERSISTENCE_TYPE`: Persistence backend being used (one of `ldap`, `couchbase`, or `hybrid`; default to `ldap`).
- `JANS_PERSISTENCE_LDAP_MAPPING`: Specify data that should be saved in LDAP (one of `default`, `user`, `cache`, `site`, or `token`; default to `default`). Note this environment only takes effect when `JANS_PERSISTENCE_TYPE` is set to `hybrid`.
- `JANS_LDAP_URL`: Address and port of LDAP server (default to `localhost:1636`); required if `JANS_PERSISTENCE_TYPE` is set to `ldap` or `hybrid`.
- `JANS_COUCHBASE_URL`: Address of Couchbase server (default to `localhost`); required if `JANS_PERSISTENCE_TYPE` is set to `couchbase` or `hybrid`.
- `JANS_COUCHBASE_USER`: Username of Couchbase server (default to `admin`); required if `JANS_PERSISTENCE_TYPE` is set to `couchbase` or `hybrid`.
- `JANS_COUCHBASE_CERT_FILE`: Couchbase root certificate location (default to `/etc/certs/couchbase.crt`); required if `JANS_PERSISTENCE_TYPE` is set to `couchbase` or `hybrid`.
- `JANS_COUCHBASE_PASSWORD_FILE`: Path to file contains Couchbase password (default to `/etc/jans/conf/couchbase_password`); required if `JANS_PERSISTENCE_TYPE` is set to `couchbase` or `hybrid`.
- `JANS_CONTAINER_METADATA`: The name of scheduler to pull container metadata (one of `docker` or `kubernetes`; default to `docker`).

## Usage

### Commands

The following commands are supported by the container:

- `patch`

#### patch

Updates X.509 certificates and/or crypto keys related to the service.

```text
Usage: certmanager patch [OPTIONS] SERVICE

  Patch cert and/or crypto keys for the targeted service.

Options:
  --dry-run                       Generate save certs and/or crypto keys only
                                  without saving it to external backends.
  --opts KEY:VALUE                Options for targeted service (can be set
                                  multiple times).
  -h, --help                      Show this message and exit.
```

Global options:

- `--dry-run`
- `--opts`: service-dependent options, example: `--opts interval:48`

Supported services:

1.  `web` (nginx container or ingress)

    Load from existing or re-generate:

    - `/etc/certs/jans_https.crt`
    - `/etc/certs/jans_https.key`.

    Options:

    - `source`: `from-files` or empty string

1.  `oxauth`

    Re-generate:

    - `/etc/certs/oxauth-keys.json`
    - `/etc/certs/oxauth-keys.jks`

    Options:

    - `interval`: cryto keys expiration time (in hours)
    - `push-to-container`: whether to _push_ `oxauth-keys.jks` and `oxauth-keys.json` to oxAuth containers (default to `true`)

1.  `ldap`

    Re-generate:

    - `/etc/certs/opendj.crt`
    - `/etc/certs/opendj.key`
    - `/etc/certs/opendj.pem`
    - `/etc/certs/opendj.pkcs12`

    Options:

    - `subj-alt-name`: Subject Alternative Name (SAN) for certificate (default to `localhost`)

1.  `passport`

    Re-generate:

    - `/etc/certs/passport-rs.jks`
    - `/etc/certs/passport-rs-keys.json`
    - `/etc/certs/passport-rp.jks`
    - `/etc/certs/passport-rp-keys.json`
    - `/etc/certs/passport-rp.pem`
    - `/etc/certs/passport-sp.key`
    - `/etc/certs/passport-sp.crt`

1.  `scim`

    Re-generate:

    - `/etc/certs/scim-rs.jks`
    - `/etc/certs/scim-rs-keys.json`
    - `/etc/certs/scim-rp.jks`
    - `/etc/certs/scim-rp-keys.json`

Docker example:

```sh
docker run \
    --rm \
    --network container:consul \
    -e JANS_CONFIG_ADAPTER=consul \
    -e JANS_CONFIG_CONSUL_HOST=consul \
    -e JANS_SECRET_ADAPTER=vault \
    -e JANS_SECRET_VAULT_HOST=vault \
    -v $PWD/vault_role_id.txt:/etc/certs/vault_role_id \
    -v $PWD/vault_secret_id.txt:/etc/certs/vault_secret_id \
    -v $PWD/ssl.crt:/etc/certs/jans_https.crt \
    -v $PWD/ssl.key:/etc/certs/jans_https.key \
    -v /var/run/docker.sock:/var/run/docker.sock \
    janssenproject/certmanager:5.0.0_dev patch web --opts source:from-files
```

Kubernetes CronJob example:

```yaml
kind: CronJob
apiVersion: batch/v1beta1
metadata:
  name: oxauth-key-rotation
spec:
  schedule: "0 */48 * * *"
  concurrencyPolicy: Forbid
  jobTemplate:
    spec:
      template:
        spec:
          containers:
            - name: oxauth-key-rotation
              image: janssenproject/certmanager:5.0.0_dev
              resources:
                requests:
                  memory: "300Mi"
                  cpu: "300m"
                limits:
                  memory: "300Mi"
                  cpu: "300m"
              envFrom:
                - configMapRef:
                    name: jans-config-cm
              args: ["patch", "oxauth", "--opts", "interval:48"]
          restartPolicy: Never
```
