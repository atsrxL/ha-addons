# UPS NUT Server documentation

## Purpose

This app connects a UPS attached to Home Assistant OS and publishes its data through Network UPS Tools (NUT) on TCP port `3493`. Home Assistant, QNAP, Synology, and other NUT clients can then use the same UPS.

It is based on the behavior of the separate `atsrxL/ups-nut-server` Docker project, but is independently maintained for Home Assistant OS. Installation uses a pre-built multi-architecture image from GitHub Container Registry instead of building packages on the Home Assistant device.

## Default Eaton 5P 1150iR configuration

The defaults are configured for the Eaton 5P 1150iR detected by this host as USB HID device `0463:ffff`:

```yaml
ups_name: 1uRackups
driver: usbhid-ups
device: auto
description: Eaton 5P 1150iR
extra_ups_config: |-
  vendorid = 0463
  productid = ffff
```

`usbhid-ups` identifies the UPS as Eaton 5P 1150 and exposes monitoring data and supported NUT instant commands. `device: auto` lets the driver select the raw USB HID device; no `/dev/tty*` serial path is needed.

With `device: auto`, the app searches in this order:

1. `/dev/serial/by-id/*`
2. `/dev/ttyXRUSB*`
3. `/dev/ttyUSB*`
4. `/dev/ttyACM*`
5. Raw USB mode (`port = auto`) when no serial device exists

When several serial devices are attached, configure the stable `/dev/serial/by-id/...` path explicitly.

## Other UPS models

The Alpine NUT package includes many drivers. Common examples:

| UPS connection | Suggested driver | Device value |
|---|---|---|
| USB HID UPS | `usbhid-ups` | `auto` |
| USB Qx protocol | `nutdrv_qx` | `auto` |
| Serial Qx protocol | `blazer_ser` | `/dev/serial/by-id/...` |
| Huawei UPS2000 | `huawei-ups2000` | `/dev/serial/by-id/...` or `auto` |

Driver-specific options can be entered in `extra_ups_config`, one option per line. Do not add a section header. Example:

```yaml
extra_ups_config: |-
  vendorid = 0463
  productid = FFFF
  pollfreq = 30
```

## Client settings

The default monitor and administrator password is `123456` as requested. Change it to a strong unique password before exposing NUT beyond the trusted LAN.

### Home Assistant NUT integration

Use:

- Host: the Home Assistant host IP, or the app hostname when supported
- Port: `3493`
- UPS name: `1uRackups` by default
- Username: `monuser` by default
- Password: the value configured as `monitor_password`

### QNAP

The compatibility defaults are:

- UPS name: `1uRackups`
- Username: `admin`
- Password: the value configured as `admin_password`

### Synology

The compatibility defaults are:

- Username: `monuser`
- Password: the value configured as `monitor_password`

Some DSM versions assume the UPS name `ups`. Change `ups_name` from `1uRackups` to `ups` when necessary.

## Security

The default credentials are `monuser`/`123456` and `admin`/`123456`. These credentials are intentionally simple for the requested setup; change them before exposing TCP port `3493`, and never forward that port to the public internet.

Set `allow_admin_commands: false` when clients only need monitoring access.

## Troubleshooting

### No device detected

For the Eaton USB HID connection, no `/dev/tty*` serial device is expected. Keep `driver: usbhid-ups` and `device: auto`; the app passes raw USB access to the driver.

For serial UPSes, open **Settings → System → Hardware → All hardware**, find the UPS serial path, and prefer a path below `/dev/serial/by-id/`. The app logs all automatic selection decisions. Explicitly set `device` when another USB serial adapter is selected first.

### Driver does not start

Check:

- The selected `driver` exists in `/usr/lib/nut`
- The UPS cable is connected to only one communication port
- The selected device path exists
- Huawei UPS2000 USB models may require a compatible HAOS kernel driver such as `ch341` or `xr_serial`
- Driver-specific settings in `extra_ups_config`

### Test from another machine

```bash
upsc 1uRackups@HOME_ASSISTANT_IP
```

A successful response includes values such as `ups.status`, `battery.charge`, and `input.voltage` when the driver exposes them.