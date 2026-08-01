# Changelog

## 1.0.4

- Changed the default UPS name to `Ups`.
- Kept `ups_name` as an editable option in the Home Assistant app configuration page.
- Documented changing the UPS name and using the new client endpoint.

## 1.0.3

- Changed the default UPS name to `1uRackups`.
- Set the requested `monuser` and `admin` default passwords to `123456`.

## 1.0.2

- Set the default driver to `usbhid-ups` for the Eaton 5P 1150iR.
- Match the connected Eaton USB HID device by vendor `0463` and product `ffff`.
- Document USB HID setup and verification for the Eaton 5P.

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