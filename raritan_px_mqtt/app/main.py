#!/usr/bin/env python3

from __future__ import annotations

import json
import logging
import os
from typing import Any

import bridge
from raritan_device import RaritanDevice


LOG = logging.getLogger("raritan2mqtt.visibility")

_DISPLAY_ATTRIBUTE_KEYS = {
    "active_power_display",
    "apparent_power_display",
    "current_display",
    "voltage_display",
    "power_factor_display",
    "active_energy_display",
}

_HIDE_OPTION_MAP = {
    "Apparent Power": "apparentPower",
    "Frequency": "lineFrequency",
    "Power Factor": "powerFactor",
    "PowerFactor": "powerFactor",
    "Voltage": "voltage",
    "Current": "current",
    # Accept internal names as well for manual options.json edits and upgrades.
    "apparentPower": "apparentPower",
    "lineFrequency": "lineFrequency",
    "powerFactor": "powerFactor",
    "voltage": "voltage",
    "current": "current",
}


def _hidden_outlet_sensor_attributes() -> set[str]:
    raw = os.getenv("HIDE_OUTLET_SENSORS", "[]").strip()
    try:
        configured = json.loads(raw)
    except json.JSONDecodeError:
        configured = [item.strip() for item in raw.split(",") if item.strip()]

    if isinstance(configured, str):
        configured = [configured]
    if not isinstance(configured, list):
        LOG.warning("Ignoring invalid hide_outlet_sensors value: %r", configured)
        return set()

    hidden: set[str] = set()
    for item in configured:
        attribute = _HIDE_OPTION_MAP.get(str(item))
        if attribute:
            hidden.add(attribute)
        else:
            LOG.warning("Ignoring unknown outlet sensor visibility option: %r", item)
    return hidden


class SensorFirstRaritanDevice(RaritanDevice):
    """Keep measurements on sensor entities and switches control-only."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.hidden_outlet_sensor_attributes = _hidden_outlet_sensor_attributes()

    def connect(self) -> None:
        super().connect()
        if not self.hidden_outlet_sensor_attributes:
            return

        before = len(self.sensors)
        self.sensors = [
            binding
            for binding in self.sensors
            if not (
                binding.scope == "outlet"
                and binding.attribute in self.hidden_outlet_sensor_attributes
            )
        ]
        hidden_count = before - len(self.sensors)
        LOG.info(
            "Hidden %d outlet sensor entities for fields: %s",
            hidden_count,
            ", ".join(sorted(self.hidden_outlet_sensor_attributes)),
        )

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
# overrides keep switches control-only and remove configured outlet measurements
# before Discovery is published. The Discovery cache then deletes stale retained
# topics so hidden entities disappear from Home Assistant after an app restart.
bridge.RaritanDevice = SensorFirstRaritanDevice
bridge.json_publish = _json_publish_without_switch_attributes


if __name__ == "__main__":
    bridge.main()
