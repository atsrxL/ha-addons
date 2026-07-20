#!/usr/bin/with-contenv bashio
set -Eeuo pipefail

readonly NUT_CONFIG_DIR="/etc/nut"
readonly NUT_RUN_DIR="/run/nut"

UPSD_PID=""
RESOLVED_DEVICE=""

nut_quote() {
    local value="$1"
    value="${value//\\/\\\\}"
    value="${value//\"/\\\"}"
    printf '"%s"' "${value}"
}

reject_line_breaks() {
    local name="$1"
    local value="$2"
    if [[ "${value}" == *$'\n'* || "${value}" == *$'\r'* ]]; then
        bashio::log.fatal "${name} must not contain line breaks."
        exit 1
    fi
}

list_serial_devices() {
    local candidate
    local found_by_id=false

    for candidate in /dev/serial/by-id/*; do
        if [[ -e "${candidate}" ]]; then
            found_by_id=true
            printf '%s\n' "${candidate}"
        fi
    done

    if bashio::var.true "${found_by_id}"; then
        return
    fi

    for candidate in \
        /dev/ttyXRUSB* \
        /dev/ttyUSB* \
        /dev/ttyACM*; do
        if [[ -e "${candidate}" ]]; then
            printf '%s\n' "${candidate}"
        fi
    done
}

resolve_device() {
    local configured_device="$1"
    local driver="$2"
    local candidate
    local -a serial_devices=()

    if [[ "${configured_device}" != "auto" ]]; then
        reject_line_breaks "device" "${configured_device}"
        if [[ "${configured_device}" == /dev/* && ! -e "${configured_device}" ]]; then
            bashio::log.fatal "Configured device does not exist: ${configured_device}"
            exit 1
        fi
        RESOLVED_DEVICE="${configured_device}"
        return
    fi

    case "${driver}" in
        usbhid-ups|blazer_usb|bcmxcp_usb|richcomm_usb|tripplite_usb|riello_usb|nutdrv_qx)
            bashio::log.info "Driver ${driver} normally uses raw USB access; using port=auto."
            RESOLVED_DEVICE="auto"
            return
            ;;
    esac

    while IFS= read -r candidate; do
        serial_devices+=("${candidate}")
    done < <(list_serial_devices)

    if (( ${#serial_devices[@]} == 1 )); then
        RESOLVED_DEVICE="${serial_devices[0]}"
        bashio::log.info "Automatically selected serial device: ${RESOLVED_DEVICE}"
        return
    fi

    if (( ${#serial_devices[@]} > 1 )); then
        RESOLVED_DEVICE="${serial_devices[0]}"
        bashio::log.warning "Multiple serial devices were found. Selecting the first one: ${RESOLVED_DEVICE}"
        bashio::log.warning "Set the device option to a stable /dev/serial/by-id path to avoid ambiguity."
        return
    fi

    if [[ -d /dev/bus/usb ]]; then
        bashio::log.warning "No serial device was found; falling back to port=auto for raw USB drivers."
        RESOLVED_DEVICE="auto"
        return
    fi

    bashio::log.fatal "No usable UPS device was detected."
    bashio::log.fatal "Connect the UPS, verify that HAOS detects it, or set device explicitly."
    exit 1
}

append_extra_ups_config() {
    local extra_config="$1"
    local line

    [[ -z "${extra_config}" ]] && return

    printf '\n    # Additional driver options from the app configuration\n' >> "${NUT_CONFIG_DIR}/ups.conf"
    while IFS= read -r line || [[ -n "${line}" ]]; do
        line="${line%$'\r'}"
        [[ -z "${line//[[:space:]]/}" ]] && continue
        if [[ "${line}" =~ ^[[:space:]]*\[ ]]; then
            bashio::log.fatal "extra_ups_config must contain driver options only, not section headers."
            exit 1
        fi
        printf '    %s\n' "${line}" >> "${NUT_CONFIG_DIR}/ups.conf"
    done <<< "${extra_config}"
}

cleanup() {
    local exit_code=$?
    trap - EXIT INT TERM

    if [[ -n "${UPSD_PID}" ]] && kill -0 "${UPSD_PID}" 2>/dev/null; then
        bashio::log.info "Stopping NUT server..."
        kill -TERM "${UPSD_PID}" 2>/dev/null || true
        wait "${UPSD_PID}" 2>/dev/null || true
    fi

    bashio::log.info "Stopping UPS driver..."
    upsdrvctl -u root stop "${UPS_NAME:-}" >/dev/null 2>&1 || true
    exit "${exit_code}"
}

trap cleanup EXIT
trap 'exit 0' INT TERM

UPS_NAME="$(bashio::config 'ups_name')"
DRIVER="$(bashio::config 'driver')"
CONFIGURED_DEVICE="$(bashio::config 'device')"
DESCRIPTION="$(bashio::config 'description')"
POLL_INTERVAL="$(bashio::config 'poll_interval')"
MAX_RETRY="$(bashio::config 'max_retry')"
RETRY_DELAY="$(bashio::config 'retry_delay')"
MONITOR_USER="$(bashio::config 'monitor_user')"
MONITOR_PASSWORD="$(bashio::config 'monitor_password')"
MONITOR_ROLE="$(bashio::config 'monitor_role')"
ADMIN_ENABLED="$(bashio::config 'admin_enabled')"
ADMIN_USER="$(bashio::config 'admin_user')"
ADMIN_PASSWORD="$(bashio::config 'admin_password')"
ADMIN_ROLE="$(bashio::config 'admin_role')"
ALLOW_ADMIN_COMMANDS="$(bashio::config 'allow_admin_commands')"
EXTRA_UPS_CONFIG="$(bashio::config 'extra_ups_config')"
HEALTHCHECK_INTERVAL="$(bashio::config 'healthcheck_interval')"
HEALTHCHECK_FAILURES="$(bashio::config 'healthcheck_failures')"
LOG_LEVEL="$(bashio::config 'log_level')"

bashio::log.level "${LOG_LEVEL}"

reject_line_breaks "ups_name" "${UPS_NAME}"
reject_line_breaks "driver" "${DRIVER}"
reject_line_breaks "description" "${DESCRIPTION}"
reject_line_breaks "monitor_user" "${MONITOR_USER}"
reject_line_breaks "monitor_password" "${MONITOR_PASSWORD}"
reject_line_breaks "admin_user" "${ADMIN_USER}"
reject_line_breaks "admin_password" "${ADMIN_PASSWORD}"

if [[ ! -x "/usr/lib/nut/${DRIVER}" ]] && ! command -v "${DRIVER}" >/dev/null 2>&1; then
    bashio::log.fatal "NUT driver is not installed in this image: ${DRIVER}"
    bashio::log.info "Available drivers can be listed from the app terminal with: ls /usr/lib/nut"
    exit 1
fi

resolve_device "${CONFIGURED_DEVICE}" "${DRIVER}"

install -d -m 0755 "${NUT_CONFIG_DIR}"
install -d -o nut -g nut -m 0770 "${NUT_RUN_DIR}"
rm -f "${NUT_RUN_DIR}"/*.pid "${NUT_RUN_DIR}"/*.sock 2>/dev/null || true

cat > "${NUT_CONFIG_DIR}/nut.conf" <<EOF_NUT
MODE=netserver
EOF_NUT

cat > "${NUT_CONFIG_DIR}/ups.conf" <<EOF_UPS
maxretry = ${MAX_RETRY}
retrydelay = ${RETRY_DELAY}
pollinterval = ${POLL_INTERVAL}
user = root

[${UPS_NAME}]
    driver = ${DRIVER}
    port = $(nut_quote "${RESOLVED_DEVICE}")
    desc = $(nut_quote "${DESCRIPTION}")
EOF_UPS
append_extra_ups_config "${EXTRA_UPS_CONFIG}"

UPSD_MAXAGE=$((POLL_INTERVAL * 3))
if (( UPSD_MAXAGE < 30 )); then
    UPSD_MAXAGE=30
fi

cat > "${NUT_CONFIG_DIR}/upsd.conf" <<EOF_UPSD
LISTEN 0.0.0.0 3493
MAXAGE ${UPSD_MAXAGE}
EOF_UPSD

cat > "${NUT_CONFIG_DIR}/upsd.users" <<EOF_USERS
[${MONITOR_USER}]
    password = $(nut_quote "${MONITOR_PASSWORD}")
    upsmon ${MONITOR_ROLE}
EOF_USERS

if bashio::var.true "${ADMIN_ENABLED}"; then
    {
        printf '\n[%s]\n' "${ADMIN_USER}"
        printf '    password = %s\n' "$(nut_quote "${ADMIN_PASSWORD}")"
        printf '    upsmon %s\n' "${ADMIN_ROLE}"
        if bashio::var.true "${ALLOW_ADMIN_COMMANDS}"; then
            printf '    actions = SET\n'
            printf '    instcmds = ALL\n'
        fi
    } >> "${NUT_CONFIG_DIR}/upsd.users"
fi

chmod 0640 \
    "${NUT_CONFIG_DIR}/nut.conf" \
    "${NUT_CONFIG_DIR}/ups.conf" \
    "${NUT_CONFIG_DIR}/upsd.conf"
chmod 0600 "${NUT_CONFIG_DIR}/upsd.users"

bashio::log.info "Starting Network UPS Tools $(upsd -V 2>&1 | head -n 1 || true)"
bashio::log.info "UPS name: ${UPS_NAME}"
bashio::log.info "Driver: ${DRIVER}"
bashio::log.info "Device: ${RESOLVED_DEVICE}"
bashio::log.info "NUT server port: 3493"

upsdrvctl -u root start "${UPS_NAME}"

upsd -F -u root &
UPSD_PID=$!

ready=false
for _ in $(seq 1 60); do
    if ! kill -0 "${UPSD_PID}" 2>/dev/null; then
        bashio::log.fatal "NUT server exited during startup."
        wait "${UPSD_PID}" || true
        exit 1
    fi

    if upsc "${UPS_NAME}@127.0.0.1" >/dev/null 2>&1; then
        ready=true
        break
    fi
    sleep 1
done

if ! bashio::var.true "${ready}"; then
    bashio::log.fatal "The UPS driver did not become ready within 60 seconds."
    bashio::log.info "Check the selected driver, device path, cable, and extra driver options."
    exit 1
fi

bashio::log.info "UPS is online and responding to NUT queries."
INITIAL_STATUS="$(upsc "${UPS_NAME}@127.0.0.1" ups.status 2>/dev/null || true)"
if [[ -n "${INITIAL_STATUS}" ]]; then
    bashio::log.info "Initial UPS status: ${INITIAL_STATUS}"
fi

consecutive_failures=0
while kill -0 "${UPSD_PID}" 2>/dev/null; do
    sleep "${HEALTHCHECK_INTERVAL}"

    if upsc "${UPS_NAME}@127.0.0.1" ups.status >/dev/null 2>&1; then
        consecutive_failures=0
        continue
    fi

    consecutive_failures=$((consecutive_failures + 1))
    bashio::log.warning "UPS health check failed (${consecutive_failures}/${HEALTHCHECK_FAILURES})."

    if (( consecutive_failures >= HEALTHCHECK_FAILURES )); then
        bashio::log.fatal "UPS communication has remained unavailable; restarting the app."
        exit 1
    fi
done

wait "${UPSD_PID}"
