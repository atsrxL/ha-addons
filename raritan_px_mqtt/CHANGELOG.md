# Changelog

## 0.2.4

- Restore the sensor-first entity model: numeric measurements remain on `sensor` entities for history and trend graphs.
- Keep outlet `switch` entities focused on on/off control instead of duplicating measurement attributes.
- Document a Tile card that shows the active-power graph while the icon calls the matching switch.
- Preserve 1-second polling support and stable release status.

## 0.2.3

- Restore configurable polling intervals down to 1 second in both the add-on schema and runtime.
- Promote the add-on from experimental to stable.
- Restore serialization support for Raritan SDK Time values.
- Restore paho-mqtt v2 connection result handling.

## 0.2.0

- Expose outlet measurements as attributes of each MQTT switch.
- Add formatted active power, apparent power, current, voltage, power factor, and active energy attributes.
- Enable one Home Assistant Tile card to display active power and toggle the outlet.
- Use the existing Supervisor MQTT service without bundling another broker.

## 0.1.0

- Initial Raritan PX2/PX3 JSON-RPC sensor discovery.
- Add MQTT Discovery sensors, outlet switches, and power-cycle buttons.
