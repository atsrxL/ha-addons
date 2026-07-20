# UPS NUT Server

Home Assistant app (add-on) that runs a Network UPS Tools server for USB and serial UPS devices.

The app is distributed as a pre-built multi-architecture image for `aarch64` and `amd64` through GitHub Container Registry.

The default UPS profile is compatible with the original `atsrxL/ups-nut-server` Docker project:

- UPS name: `qnapups`
- Driver: `huawei-ups2000`
- Device: automatically detected
- NUT port: `3493`
- QNAP-compatible user name: `admin`
- Synology-compatible user name: `monuser`

Set secure monitor and administrator passwords in the app configuration before starting it.

See [DOCS.md](DOCS.md) for configuration and troubleshooting.