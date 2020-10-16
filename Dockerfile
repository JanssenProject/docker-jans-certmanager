FROM adoptopenjdk/openjdk11:jre-11.0.8_10-alpine

# ===============
# Alpine packages
# ===============

RUN apk update \
    && apk add --no-cache openssl py3-pip curl tini \
    && apk add --no-cache --virtual build-deps wget git

# =============
# oxAuth client
# =============

# JAR files required to generate OpenID Connect keys
ENV JANS_VERSION=5.0.0-SNAPSHOT
ENV JANS_BUILD_DATE="2020-09-28 18:22"

# @TODO: get JARs from jans-auth-server
RUN mkdir -p /app/javalibs \
    && wget -q https://ox.gluu.org/maven/org/janssen/janssen-client/${JANS_VERSION}/janssen-client-${JANS_VERSION}-jar-with-dependencies.jar -O /app/javalibs/janssen-client.jar

# removed as they're not part of Janssen
# =================
# Shibboleth sealer
# =================

# RUN mkdir -p /app/javalibs \
#     && wget -q https://build.shibboleth.net/nexus/content/repositories/releases/net/shibboleth/utilities/java-support/7.5.1/java-support-7.5.1.jar -O /app/javalibs/java-support.jar \
#     && wget -q https://repo1.maven.org/maven2/com/beust/jcommander/1.48/jcommander-1.48.jar -P /app/javalibs/ \
#     && wget -q https://repo1.maven.org/maven2/org/slf4j/slf4j-api/1.7.26/slf4j-api-1.7.26.jar -P /app/javalibs/ \
#     && wget -q https://repo1.maven.org/maven2/org/slf4j/slf4j-simple/1.7.26/slf4j-simple-1.7.26.jar -P /app/javalibs/

# ======
# Python
# ======

RUN apk add --no-cache py3-cryptography
COPY requirements.txt /app/requirements.txt
RUN pip3 install --no-cache-dir -U pip \
    && pip3 install --no-cache-dir -r /app/requirements.txt \
    && rm -rf /src/jans-pycloudlib/.git

# =======
# Cleanup
# =======

RUN apk del build-deps \
    && rm -rf /var/cache/apk/*

# =======
# License
# =======

RUN mkdir -p /licenses
COPY LICENSE /licenses/

# ==========
# Config ENV
# ==========

ENV JANS_CONFIG_ADAPTER=consul \
    JANS_CONFIG_CONSUL_HOST=localhost \
    JANS_CONFIG_CONSUL_PORT=8500 \
    JANS_CONFIG_CONSUL_CONSISTENCY=default \
    JANS_CONFIG_CONSUL_SCHEME=http \
    JANS_CONFIG_CONSUL_VERIFY=false \
    JANS_CONFIG_CONSUL_CACERT_FILE=/etc/certs/consul_ca.crt \
    JANS_CONFIG_CONSUL_CERT_FILE=/etc/certs/consul_client.crt \
    JANS_CONFIG_CONSUL_KEY_FILE=/etc/certs/consul_client.key \
    JANS_CONFIG_CONSUL_TOKEN_FILE=/etc/certs/consul_token \
    JANS_CONFIG_CONSUL_NAMESPACE=jans \
    JANS_CONFIG_KUBERNETES_NAMESPACE=default \
    JANS_CONFIG_KUBERNETES_CONFIGMAP=jans \
    JANS_CONFIG_KUBERNETES_USE_KUBE_CONFIG=false

# ==========
# Secret ENV
# ==========

ENV JANS_SECRET_ADAPTER=vault \
    JANS_SECRET_VAULT_SCHEME=http \
    JANS_SECRET_VAULT_HOST=localhost \
    JANS_SECRET_VAULT_PORT=8200 \
    JANS_SECRET_VAULT_VERIFY=false \
    JANS_SECRET_VAULT_ROLE_ID_FILE=/etc/certs/vault_role_id \
    JANS_SECRET_VAULT_SECRET_ID_FILE=/etc/certs/vault_secret_id \
    JANS_SECRET_VAULT_CERT_FILE=/etc/certs/vault_client.crt \
    JANS_SECRET_VAULT_KEY_FILE=/etc/certs/vault_client.key \
    JANS_SECRET_VAULT_CACERT_FILE=/etc/certs/vault_ca.crt \
    JANS_SECRET_VAULT_NAMESPACE=jans \
    JANS_SECRET_KUBERNETES_NAMESPACE=default \
    JANS_SECRET_KUBERNETES_SECRET=jans \
    JANS_SECRET_KUBERNETES_USE_KUBE_CONFIG=false

# ===========
# Generic ENV
# ===========

ENV JANS_WAIT_MAX_TIME=300 \
    JANS_WAIT_SLEEP_DURATION=10 \
    JANS_CONTAINER_METADATA=docker \
    JANS_NAMESPACE=jans

# ====
# misc
# ====

LABEL name="Certmanager" \
    maintainer="Janssen Project <support@jans.io>" \
    vendor="Janssen Project" \
    version="5.0.0" \
    release="dev" \
    summary="Janssen Certmanager" \
    description="Manage certs and crypto keys for Janssen Server"

COPY scripts /app/scripts

RUN mkdir -p /etc/certs \
    && chmod +x /app/scripts/entrypoint.sh

ENTRYPOINT ["tini", "-g", "--", "sh", "/app/scripts/entrypoint.sh"]
CMD ["--help"]
