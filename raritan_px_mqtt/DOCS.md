# Raritan PX MQTT

This app connects a Raritan PX2/PX3 PDU to Home Assistant using the PDU JSON-RPC API and Home Assistant MQTT Discovery.

It **does not contain an MQTT broker**. It requires and automatically uses the MQTT service provided by the installed Mosquitto Broker app.

## Before installation

1. Install and start the Mosquitto Broker app.
2. Confirm the MQTT integration is configured in Home Assistant.
3. Create or choose a Raritan web user that can read sensors and control outlets.
4. Confirm the PDU web interface is reachable from Home Assistant.

SNMP and Modbus do not need to be enabled for this app.

## Configuration

```yaml
pdu_host: 192.168.123.78
pdu_username: admin
pdu_password: YOUR_RARITAN_WEB_PASSWORD
protocol: https
verify_ssl: false
poll_interval: 15
discovery_prefix: homeassistant
topic_prefix: raritan2mqtt
log_level: INFO
```

- `pdu_host`: PDU IP address or hostname.
- `pdu_username`: Raritan web/JSON-RPC username.
- `pdu_password`: Raritan web/JSON-RPC password.
- `protocol`: `https` is recommended. Use `http` only when necessary.
- `verify_ssl`: Enable only when the PDU certificate is trusted by the app.
- `poll_interval`: Polling period in seconds. Values from 1 to 3600 seconds are accepted; 10–30 seconds is recommended for normal use.
- `discovery_prefix`: Normally `homeassistant`.
- `topic_prefix`: Root MQTT topic used by the bridge.
- `log_level`: Logging verbosity.

MQTT host, port, username, password, and TLS settings are obtained automatically from the Supervisor MQTT service. They are not duplicated in this app's configuration.

## Home Assistant entities

The app probes the actual hardware and creates only entities implemented by the connected PDU:

- Inlet electrical measurement sensors
- Outlet electrical measurement sensors
- One switch for every switchable outlet
- One power-cycle button for every switchable outlet

All entities share one Home Assistant device entry. Names configured in the Raritan web interface are used for outlet entities.

Measurement history and charts belong to the numeric `sensor` entities. Outlet `switch` entities are control-only.

## Tile card: power graph with an outlet toggle

Use the active-power sensor as the card entity so Home Assistant can display its history graph. Configure the icon action to call the corresponding outlet switch explicitly:

```yaml
type: tile
entity: sensor.YOUR_OUTLET_ACTIVE_POWER
name: Outlet 1
icon: mdi:power-socket
features:
  - type: trend-graph
    hours_to_show: 24
    detail: true
tap_action:
  action: more-info
icon_tap_action:
  action: perform-action
  perform_action: switch.toggle
  target:
    entity_id: switch.YOUR_OUTLET_SWITCH
```

The card remains a numeric power sensor, so the graph and sensor history work normally. Clicking the icon controls the separate switch entity and avoids attempts to call a nonexistent `sensor.turn_off` action.

## Migration from direct SNMP YAML

After the MQTT entities work, remove or comment out the old Raritan entries in `sensors.yaml` and `switches.yaml` to avoid duplicates. SNMP can remain enabled on the PDU for diagnostics; this app does not use it.

## Troubleshooting

- **PDU initialization failed:** Check the PDU address, protocol, username, password, and JSON-RPC access.
- **Certificate errors:** Keep `verify_ssl: false` for the factory/self-signed certificate, or install a trusted certificate on the PDU.
- **No MQTT entities:** Confirm Mosquitto Broker and the Home Assistant MQTT integration are running, then restart this app.
- **Outlet command rejected:** Grant the Raritan user outlet-switching permission.
- **No graph on a switch card:** Use the corresponding active-power sensor as the card entity and target the switch through `icon_tap_action`.
