# Mercury PoE MQTT

This app reads PoE power data from a Mercury managed switch and publishes it through Home Assistant MQTT Discovery. It uses the existing Mosquitto Broker app; it does not start a second broker.

## Before installation

1. Install and start the Mosquitto Broker app.
2. Confirm the MQTT integration is configured in Home Assistant.
3. Confirm the Mercury switch web page is reachable from the Home Assistant host.
4. Keep the switch on a trusted LAN. Its management interface uses unencrypted HTTP.

## Configuration

```yaml
switch_url: http://192.168.123.5
username: admin
password: YOUR_SWITCH_PASSWORD
poll_interval: 30
request_timeout: 10
discovery_prefix: homeassistant
topic_prefix: mercury_poe
log_level: INFO
```

- `switch_url`: Full management URL, including `http://`.
- `username` / `password`: Mercury web-management credentials. The password is masked in the app UI.
- `poll_interval`: Seconds between reads; accepted range is 1-3600. A 30-second default avoids unnecessary load on the switch.
- `request_timeout`: HTTP timeout in seconds.
- `discovery_prefix`: Normally `homeassistant`.
- `topic_prefix`: MQTT topic root for state and command messages.
- `log_level`: Logging verbosity.

MQTT host, port, username, password, and TLS settings are obtained automatically from the Supervisor MQTT service.

## Home Assistant entities

The app creates one device named after the detected switch model, with:

- PoE total power, used power, remaining power, and usage percentage
- Per-port power, current, voltage, maximum power, supply status, PD Class, and priority
- A **Port N 重新上电** button for every PoE port

Pressing a port button sends the switch's native `重新上电` command. Network cameras, access points, or other devices on that port will temporarily lose power and connectivity.

## Troubleshooting

- **Switch rejected the login:** Verify the web username and password. Restarting the app creates a fresh management session.
- **No MQTT entities:** Confirm Mosquitto Broker and the MQTT integration are running, then restart this app.
- **Polling failures:** Verify the switch URL is reachable from the Home Assistant host and increase `request_timeout` if needed.
- **Button command rejected:** The switch does not allow re-powering a disabled PoE port. Enable that port in the switch UI first.
