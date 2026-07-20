#!/usr/bin/with-contenv bashio
set -euo pipefail

export PDU_HOST="$(bashio::config 'pdu_host')"
export PDU_USERNAME="$(bashio::config 'pdu_username')"
export PDU_PASSWORD="$(bashio::config 'pdu_password')"
export PDU_PROTOCOL="$(bashio::config 'protocol')"
export PDU_VERIFY_SSL="$(bashio::config 'verify_ssl')"
export POLL_INTERVAL="$(bashio::config 'poll_interval')"
export DISCOVERY_PREFIX="$(bashio::config 'discovery_prefix')"
export TOPIC_PREFIX="$(bashio::config 'topic_prefix')"
export LOG_LEVEL="$(bashio::config 'log_level')"

# Reuse the MQTT service provided by the installed Mosquitto Broker add-on.
# No MQTT broker is installed or started in this add-on.
export MQTT_HOST="$(bashio::services mqtt 'host')"
export MQTT_PORT="$(bashio::services mqtt 'port')"
export MQTT_USERNAME="$(bashio::services mqtt 'username')"
export MQTT_PASSWORD="$(bashio::services mqtt 'password')"
export MQTT_SSL="$(bashio::services mqtt 'ssl')"

bashio::log.info "Using the Supervisor-provided MQTT service at ${MQTT_HOST}:${MQTT_PORT}"
bashio::log.info "Connecting to Raritan PDU at ${PDU_PROTOCOL}://${PDU_HOST}"

exec python3 -u /app/main.py
