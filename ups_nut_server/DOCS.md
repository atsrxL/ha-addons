# UPS NUT Server documentation

## Purpose

This app connects a UPS attached to Home Assistant OS and publishes its data through Network UPS Tools (NUT) on TCP port `3493`. Home Assistant, QNAP, Synology, and other NUT clients can then use the same UPS.

It is based on the behavior of the separate `atsrxL/ups-nut-server` Docker project, but is independently maintained for Home Assistant OS. Installation uses a pre-built multi-architecture image from GitHub Container Registry instead of building packages on the Home Assistant device.

## Default Huawei UPS2000 configuration

The defaults match a Huawei UPS2000 connected through a supported USB-to-serial interface:

```yaml
ups_name: qnapups
driver: huawei-ups2000
device: auto
```

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

Before starting the app, replace both `CHANGE_ME` password placeholders in the configuration.

### Home Assistant NUT integration

Use:

- Host: the Home Assistant host IP, or the app hostname when supported
- Port: `3493`
- UPS name: `qnapups` by default
- Username: `monuser` by default
- Password: the value configured as `monitor_password`

### QNAP

The compatibility defaults are:

- UPS name: `qnapups`
- Username: `admin`
- Password: the value configured as `admin_password`

### Synology

The compatibility defaults are:

- Username: `monuser`
- Password: the value configured as `monitor_password`

Some DSM versions assume the UPS name `ups`. Change `ups_name` from `qnapups` to `ups` when necessary.

## Security

The app does not ship with usable default passwords. Replace the `CHANGE_ME` placeholders before first start, use unique passwords, and do not forward TCP port `3493` to the public internet.

Set `allow_admin_commands: false` when clients only need monitoring access.

## Troubleshooting

### No serial device detected

Open **Settings → System → Hardware → All hardware** and find the UPS serial path. Prefer a path below `/dev/serial/by-id/`.

The app logs all automatic selection decisions. Explicitly set `device` when another USB serial adapter is selected first.

### Driver does not start

Check:

- The selected `driver` exists in `/usr/lib/nut`
- The UPS cable is connected to only one communication port
- The selected device path exists
- Huawei UPS2000 USB models may require a compatible HAOS kernel driver such as `ch341` or `xr_serial`
- Driver-specific settings in `extra_ups_config`

### Test from another machine

```bash
upsc qnapups@HOME_ASSISTANT_IP
```

A successful response includes values such as `ups.status`, `battery.charge`, and `input.voltage` when the driver exposes them.