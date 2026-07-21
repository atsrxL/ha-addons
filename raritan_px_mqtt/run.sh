#!/usr/bin/with-contenv bashio
set -Eeuo pipefail

export PDU_HOST="$(bashio::config 'pdu_host')"
export PDU_USERNAME="$(bashio::config 'pdu_username')"
export PDU_PASSWORD="$(bashio::config 'pdu_password')"
export PDU_PROTOCOL="$(bashio::config 'protocol')"
export PDU_VERIFY_SSL="$(bashio::config 'verify_ssl')"
export POLL_INTERVAL="$(bashio::config 'poll_interval')"
export HIDE_OUTLET_SENSORS="$(jq -c '.hide_outlet_sensors // []' /data/options.json)"
export DISCOVERY_PREFIX="$(bashio::config 'discovery_prefix')"
export TOPIC_PREFIX="$(bashio::config 'topic_prefix')"
export LOG_LEVEL="$(bashio::config 'log_level')"

export MQTT_HOST="$(bashio::services mqtt 'host')"
export MQTT_PORT="$(bashio::services mqtt 'port')"
export MQTT_USERNAME="$(bashio::services mqtt 'username')"
export MQTT_PASSWORD="$(bashio::services mqtt 'password')"
export MQTT_SSL="$(bashio::services mqtt 'ssl')"

if [[ -z "${PDU_HOST}" ]]; then
    bashio::log.fatal "pdu_host must not be empty."
    exit 1
fi

if [[ -z "${PDU_USERNAME}" ]]; then
    bashio::log.fatal "pdu_username must not be empty."
    exit 1
fi

if [[ -z "${MQTT_HOST}" || -z "${MQTT_PORT}" ]]; then
    bashio::log.fatal "The Home Assistant MQTT service is unavailable. Start the Mosquitto Broker app first."
    exit 1
fi

bashio::log.info "Starting Raritan PX MQTT bridge"
bashio::log.info "PDU: ${PDU_PROTOCOL}://${PDU_HOST}"
bashio::log.info "MQTT: ${MQTT_HOST}:${MQTT_PORT} (existing Supervisor service)"
bashio::log.info "Polling interval: ${POLL_INTERVAL}s"
bashio::log.info "Hidden outlet sensors: ${HIDE_OUTLET_SENSORS}"

exec python3 -u /app/main.py
