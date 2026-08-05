# Home Assistant app: Mercury PoE MQTT

Bridge Mercury managed PoE switches into Home Assistant with the switch web interface and MQTT Discovery.

- Publishes total, used, remaining, and usage-percentage PoE power
- Publishes each port's power, current, voltage, PD Class, priority, and supply status
- Creates one **Re-power** button per PoE port
- Uses the existing Home Assistant Mosquitto Broker service
- Provides a configurable polling interval from 1 to 3600 seconds
- Does not store the switch password in the image or repository

The implementation is verified against a Mercury **SE109P Pro** with eight PoE ports.

See `DOCS.md` for setup and entity details.
