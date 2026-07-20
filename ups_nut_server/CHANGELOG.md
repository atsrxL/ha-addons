# Changelog

## 1.0.1

- Switched Home Assistant installation to a pre-built GHCR image.
- Added automated `aarch64` and `amd64` builds with a generic multi-architecture manifest.
- Replaced insecure default passwords with `CHANGE_ME` placeholders.

## 1.0.0

- Initial Home Assistant app release.
- Added Huawei UPS2000 defaults compatible with the standalone Docker project.
- Added automatic serial-device detection with stable `/dev/serial/by-id` preference.
- Added raw USB support for HID and USB NUT drivers.
- Added configurable NUT driver, users, roles, polling, retries, and extra driver options.
- Added startup validation and continuous UPS communication health checks.