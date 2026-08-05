#!/usr/bin/with-contenv bashio
set -Eeuo pipefail

export SWITCH_URL="$(bashio::config 'switch_url')"
export SWITCH_USERNAME="$(bashio::config 'username')"
export SWITCH_PASSWORD="$(bashio::config 'password')"
export POLL_INTERVAL="$(bashio::config 'poll_interval')"
export REQUEST_TIMEOUT="$(bashio::config 'request_timeout')"
export DISCOVERY_PREFIX="$(bashio::config 'discovery_prefix')"
export TOPIC_PREFIX="$(bashio::config 'topic_prefix')"
export LOG_LEVEL="$(bashio::config 'log_level')"

export MQTT_HOST="$(bashio::services mqtt 'host')"
export MQTT_PORT="$(bashio::services mqtt 'port')"
export MQTT_USERNAME="$(bashio::services mqtt 'username')"
export MQTT_PASSWORD="$(bashio::services mqtt 'password')"
export MQTT_SSL="$(bashio::services mqtt 'ssl')"

if [[ -z "${SWITCH_URL}" || -z "${SWITCH_USERNAME}" || -z "${SWITCH_PASSWORD}" ]]; then
    bashio::log.fatal "switch_url, username, and password must not be empty."
    exit 1
fi

if [[ -z "${MQTT_HOST}" || -z "${MQTT_PORT}" ]]; then
    bashio::log.fatal "The Home Assistant MQTT service is unavailable. Start the Mosquitto Broker app first."
    exit 1
fi

bashio::log.info "Starting Mercury PoE MQTT bridge"
bashio::log.info "Switch: ${SWITCH_URL}"
bashio::log.info "MQTT: ${MQTT_HOST}:${MQTT_PORT} (existing Supervisor service)"
bashio::log.info "Polling interval: ${POLL_INTERVAL}s"

exec python3 -u /app/main.py
