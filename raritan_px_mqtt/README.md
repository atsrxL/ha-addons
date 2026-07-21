# Home Assistant app: Raritan PX MQTT

Bridge Raritan PX2/PX3 PDUs into Home Assistant with the PDU JSON-RPC API and MQTT Discovery.

- Uses the existing Home Assistant Mosquitto Broker service
- Does not include or start another MQTT broker
- Automatically detects inlets, outlets, and supported measurements
- Groups all entities under one Home Assistant device
- Supports outlet on, off, and power-cycle commands
- Adds outlet measurements as attributes of the matching switch entity

See `DOCS.md` for installation and configuration.

## Tile card: show power and control the outlet

Use the switch entity as the card entity. The icon toggles the outlet while the card displays active power:

```yaml
type: tile
entity: switch.YOUR_OUTLET_SWITCH
name: Outlet 1
state_content:
  - state
  - active_power_display
icon_tap_action:
  action: toggle
tap_action:
  action: more-info
icon_hold_action:
  action: more-info
```

Available formatted attributes include `active_power_display`,
`apparent_power_display`, `current_display`, `voltage_display`,
`power_factor_display`, and `active_energy_display`.
