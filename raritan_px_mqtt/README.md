# Home Assistant app: Raritan PX MQTT

Bridge Raritan PX2/PX3 PDUs into Home Assistant with the PDU JSON-RPC API and MQTT Discovery.

- Uses the existing Home Assistant Mosquitto Broker service
- Does not include or start another MQTT broker
- Automatically detects inlets, outlets, and supported measurements
- Groups all entities under one Home Assistant device
- Creates numeric measurement sensors for history and trend graphs
- Creates separate outlet switches for on/off control
- Supports outlet power-cycle commands
- Supports polling intervals down to 1 second

See `DOCS.md` for installation and configuration.

## Tile card: power graph and outlet control

Keep the active-power sensor as the card entity, then make the icon call the corresponding switch:

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

This preserves the power graph and history while letting the icon control the outlet.
