# Raritan PX MQTT

This add-on connects a Raritan PX2/PX3 PDU to Home Assistant using the PDU's
JSON-RPC API and Home Assistant MQTT Discovery.

It **does not contain an MQTT broker**. The add-on requires and automatically
uses the MQTT service supplied by the installed Mosquitto Broker add-on.

## Before installation

1. Confirm the Mosquitto Broker add-on is installed and running.
2. Confirm MQTT is configured in Home Assistant.
3. Create or choose a Raritan web user that can read sensors and control outlets.
4. Confirm the PDU web interface is reachable from Home Assistant.

SNMP and Modbus do not need to be enabled for this add-on.

## Options

- `pdu_host`: PDU IP address or hostname.
- `pdu_username`: Raritan web/JSON-RPC username.
- `pdu_password`: Raritan web/JSON-RPC password.
- `protocol`: `https` is recommended. Use `http` only when necessary.
- `verify_ssl`: Enable only when the PDU certificate is trusted by the add-on.
- `poll_interval`: Polling period in seconds. Recommended: 10–30 seconds.
- `discovery_prefix`: Usually `homeassistant`.
- `topic_prefix`: Root MQTT topic used by this bridge.
- `log_level`: Logging verbosity.

## Home Assistant entities

The add-on automatically probes the actual hardware. It creates only entities
whose JSON-RPC sensor references work on the connected PDU.

All entities share one MQTT device entry for the PDU, including:

- Inlet electrical measurements
- Outlet electrical measurements
- One switch for every switchable outlet
- One power-cycle button for every switchable outlet

Names configured in the Raritan web interface are used for the outlet entities.

## Migration from direct SNMP YAML

After this add-on is working, remove or comment out the old Raritan entries in
`sensors.yaml` and `switches.yaml` to avoid duplicate entities. SNMP may remain
enabled on the PDU for diagnostics; this add-on does not use it.

## Troubleshooting

- `PDU initialization failed`: Check the PDU address, protocol, username and
  password. Also confirm JSON-RPC/HTTP access is not blocked by a firewall.
- Certificate errors: Keep `verify_ssl: false` for the factory/self-signed PDU
  certificate, or install a trusted certificate on the PDU.
- No MQTT entities: Confirm the Mosquitto Broker add-on and Home Assistant MQTT
  integration are running, then restart this add-on.
- Outlet command rejected: Grant the Raritan user outlet switching permission.
