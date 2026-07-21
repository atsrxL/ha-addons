#!/usr/bin/env python3

from __future__ import annotations

from typing import Any

import bridge
from raritan_device import RaritanDevice


_DISPLAY_ATTRIBUTE_KEYS = {
    "active_power_display",
    "apparent_power_display",
    "current_display",
    "voltage_display",
    "power_factor_display",
    "active_energy_display",
}


class SensorFirstRaritanDevice(RaritanDevice):
    """Keep measurements on sensor entities and switches control-only."""

    def poll(self) -> dict[str, dict[str, Any]]:
        payloads = super().poll()
        for payload in payloads.values():
            for key in _DISPLAY_ATTRIBUTE_KEYS:
                payload.pop(key, None)
        return payloads


_original_json_publish = bridge.json_publish


def _json_publish_without_switch_attributes(
    client: Any,
    topic: str,
    payload: dict[str, Any],
    retain: bool = True,
) -> None:
    if "/switch/" in topic and topic.endswith("/config"):
        payload = dict(payload)
        payload.pop("json_attributes_topic", None)
    _original_json_publish(client, topic, payload, retain=retain)


# The bridge still creates independent numeric sensors and outlet switches. These
# overrides only remove the later switch-attribute presentation layer so power
# sensors remain the canonical entities for history and trend graphs.
bridge.RaritanDevice = SensorFirstRaritanDevice
bridge.json_publish = _json_publish_without_switch_attributes


if __name__ == "__main__":
    bridge.main()
