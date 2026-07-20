# UPS NUT Server

Home Assistant app (add-on) that runs a Network UPS Tools server for USB and serial UPS devices.

The default profile is compatible with the original `atsrxL/ups-nut-server` Docker project:

- UPS name: `qnapups`
- Driver: `huawei-ups2000`
- Device: automatically detected
- NUT port: `3493`
- QNAP-compatible user: `admin` / `123456`
- Synology-compatible user: `monuser` / `secret`

Change the default passwords before exposing port `3493` outside a trusted LAN.

See [DOCS.md](DOCS.md) for configuration and troubleshooting.
