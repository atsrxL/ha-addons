# UPS NUT Server

Home Assistant app (add-on) that runs a Network UPS Tools server for USB and serial UPS devices.

The app is distributed as a pre-built multi-architecture image for `aarch64` and `amd64` through GitHub Container Registry.

The default UPS profile is configured for the Eaton 5P 1150iR USB HID device (`0463:ffff`):

- UPS name: `1uRackups`
- Driver: `usbhid-ups`
- Device: automatically detected (`port = auto`)
- USB matching: `vendorid = 0463`, `productid = ffff`
- NUT port: `3493`
- QNAP-compatible user name: `admin`
- Synology-compatible user name: `monuser`

Set secure monitor and administrator passwords in the app configuration before starting it.

See [DOCS.md](DOCS.md) for configuration and troubleshooting.