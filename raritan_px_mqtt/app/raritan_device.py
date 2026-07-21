from __future__ import annotations

import logging
from typing import Any, Callable, Iterable

from raritan import rpc
from raritan.rpc import pdumodel

from models import (
    SENSOR_SPECS,
    OutletBinding,
    SensorBinding,
    datetime_value,
    reading_value,
    safe_attr,
    sanitize,
)

LOG = logging.getLogger("raritan2mqtt.device")


def rpc_bulk(agent: Any, calls: Iterable[tuple[Callable[..., Any], list[Any]]]) -> list[Any]:
    queued = list(calls)
    if not queued:
        return []
    helper = rpc.BulkRequestHelper(agent)
    for method, args in queued:
        helper.add_request(method, *args)
    return helper.perform_bulk(raise_subreq_failure=False)


class RaritanDevice:
    def __init__(
        self,
        host: str,
        username: str,
        password: str,
        protocol: str,
        verify_ssl: bool,
        timeout: int,
        topic_prefix: str,
    ) -> None:
        self.host = host
        self.username = username
        self.password = password
        self.protocol = protocol
        self.verify_ssl = verify_ssl
        self.timeout = timeout
        self.topic_prefix = topic_prefix.strip("/")

        self.agent: Any = None
        self.pdu: Any = None
        self.inlets: list[Any] = []
        self.outlets: list[OutletBinding] = []
        self.sensors: list[SensorBinding] = []
        self.device_id = sanitize(host)
        self.base_topic = f"{self.topic_prefix}/{self.device_id}"
        self.availability_topic = f"{self.base_topic}/availability"
        self.device_info: dict[str, Any] = {}

    def connect(self) -> None:
        LOG.info("Connecting to %s://%s", self.protocol, self.host)
        self.agent = rpc.Agent(
            self.protocol,
            self.host,
            self.username,
            self.password,
            disable_certificate_verification=not self.verify_ssl,
            timeout=self.timeout,
        )
        self.pdu = pdumodel.Pdu("/model/pdu/0", self.agent)

        nameplate, metadata, settings, inlets, outlet_objects = rpc_bulk(
            self.agent,
            [
                (self.pdu.getNameplate, []),
                (self.pdu.getMetaData, []),
                (self.pdu.getSettings, []),
                (self.pdu.getInlets, []),
                (self.pdu.getOutlets, []),
            ],
        )
        required = ((nameplate, "nameplate"), (metadata, "metadata"), (inlets, "inlets"), (outlet_objects, "outlets"))
        for result, label in required:
            if isinstance(result, Exception):
                raise RuntimeError(f"Unable to read PDU {label}: {result}")

        self.inlets = list(inlets)
        outlet_objects = list(outlet_objects)
        manufacturer = str(safe_attr(nameplate, "manufacturer", "Raritan"))
        model = str(safe_attr(nameplate, "model", "PX PDU"))
        serial = str(safe_attr(nameplate, "serialNumber", self.host))
        firmware = str(safe_attr(metadata, "fwRevision", ""))
        configured_name = "" if isinstance(settings, Exception) else str(safe_attr(settings, "name", ""))

        self.device_id = sanitize(serial)
        self.base_topic = f"{self.topic_prefix}/{self.device_id}"
        self.availability_topic = f"{self.base_topic}/availability"
        self.device_info = {
            "identifiers": [f"raritan_{self.device_id}"],
            "name": configured_name.strip() or f"Raritan {model}",
            "manufacturer": manufacturer,
            "model": model,
            "serial_number": serial,
            "configuration_url": f"{self.protocol}://{self.host}/",
        }
        if firmware:
            self.device_info["sw_version"] = firmware

        self._discover_outlets(outlet_objects)
        self._discover_sensors()
        LOG.info(
            "Detected %d inlet(s), %d outlet(s), %d usable numeric sensor(s)",
            len(self.inlets),
            len(self.outlets),
            len(self.sensors),
        )

    def _discover_outlets(self, outlet_objects: list[Any]) -> None:
        calls: list[tuple[Callable[..., Any], list[Any]]] = []
        for outlet in outlet_objects:
            calls.extend(((outlet.getMetaData, []), (outlet.getSettings, []), (outlet.getSensors, [])))
        results = rpc_bulk(self.agent, calls)

        self.outlets = []
        self._outlet_sensor_structs: list[tuple[int, Any]] = []
        for index, outlet in enumerate(outlet_objects):
            meta, settings, sensors = results[index * 3 : index * 3 + 3]
            label = str(safe_attr(meta, "label", index + 1)) if not isinstance(meta, Exception) else str(index + 1)
            custom_name = str(safe_attr(settings, "name", "")) if not isinstance(settings, Exception) else ""
            switchable = bool(safe_attr(meta, "isSwitchable", True)) if not isinstance(meta, Exception) else True
            self.outlets.append(
                OutletBinding(
                    index=index,
                    outlet=outlet,
                    label=label,
                    name=custom_name.strip() or f"Outlet {label}",
                    switchable=switchable,
                    state_topic=f"{self.base_topic}/outlet/{index + 1}/state",
                    command_topic=f"{self.base_topic}/outlet/{index + 1}/set",
                    cycle_topic=f"{self.base_topic}/outlet/{index + 1}/cycle",
                )
            )
            if not isinstance(sensors, Exception):
                self._outlet_sensor_structs.append((index, sensors))

    def _discover_sensors(self) -> None:
        candidates: list[SensorBinding] = []
        inlet_results = rpc_bulk(self.agent, [(inlet.getSensors, []) for inlet in self.inlets])
        for index, sensor_struct in enumerate(inlet_results):
            if not isinstance(sensor_struct, Exception):
                candidates.extend(self._sensor_candidates("inlet", index, sensor_struct))
        for index, sensor_struct in self._outlet_sensor_structs:
            candidates.extend(self._sensor_candidates("outlet", index, sensor_struct))

        probe_results = rpc_bulk(self.agent, [(candidate.sensor.getReading, []) for candidate in candidates])
        self.sensors = []
        for candidate, reading in zip(candidates, probe_results, strict=True):
            if isinstance(reading, Exception):
                continue
            candidate.state_key = candidate.attribute
            candidate.state_topic = (
                f"{self.base_topic}/inlet/{candidate.index + 1}/state"
                if candidate.scope == "inlet"
                else self.outlets[candidate.index].state_topic
            )
            self.sensors.append(candidate)

    @staticmethod
    def _sensor_candidates(scope: str, index: int, sensor_struct: Any) -> list[SensorBinding]:
        found: list[SensorBinding] = []
        for attribute, spec in SENSOR_SPECS.items():
            try:
                sensor = getattr(sensor_struct, attribute)
            except Exception:
                continue
            if sensor is not None and hasattr(sensor, "getReading"):
                found.append(SensorBinding(scope, index, attribute, sensor, spec))
        return found

    def poll(self) -> dict[str, dict[str, Any]]:
        calls: list[tuple[Callable[..., Any], list[Any]]] = []
        calls.extend((binding.sensor.getReading, []) for binding in self.sensors)
        calls.extend((outlet.outlet.getState, []) for outlet in self.outlets)
        results = rpc_bulk(self.agent, calls)
        if results and all(isinstance(result, Exception) for result in results):
            raise RuntimeError("All Raritan JSON-RPC polling calls failed")

        sensor_results = results[: len(self.sensors)]
        outlet_results = results[len(self.sensors) :]
        payloads: dict[str, dict[str, Any]] = {}
        for binding, reading in zip(self.sensors, sensor_results, strict=True):
            if not isinstance(reading, Exception):
                payloads.setdefault(binding.state_topic, {})[binding.state_key] = reading_value(reading, binding.spec)

        for outlet, state in zip(self.outlets, outlet_results, strict=True):
            payload = payloads.setdefault(outlet.state_topic, {})
            if isinstance(state, Exception) or not bool(safe_attr(state, "available", False)):
                payload["power_state"] = None
                continue
            power_state = safe_attr(state, "powerState")
            if power_state == pdumodel.Outlet.PowerState.PS_ON:
                payload["power_state"] = "ON"
            elif power_state == pdumodel.Outlet.PowerState.PS_OFF:
                payload["power_state"] = "OFF"
            else:
                payload["power_state"] = None
            payload["cycle_in_progress"] = bool(safe_attr(state, "cycleInProgress", False))
            payload["switch_on_in_progress"] = bool(safe_attr(state, "switchOnInProgress", False))
            payload["last_power_state_change"] = datetime_value(safe_attr(state, "lastPowerStateChange"))

        display_specs = (
            ("activePower", "active_power_display", "W"),
            ("apparentPower", "apparent_power_display", "VA"),
            ("current", "current_display", "A"),
            ("voltage", "voltage_display", "V"),
            ("powerFactor", "power_factor_display", ""),
            ("activeEnergy", "active_energy_display", "Wh"),
        )
        for outlet in self.outlets:
            payload = payloads.get(outlet.state_topic)
            if not payload:
                continue
            for source_key, display_key, unit in display_specs:
                value = payload.get(source_key)
                if value is not None:
                    rendered = f"{value:g}" if isinstance(value, float) else str(value)
                    payload[display_key] = f"{rendered} {unit}".strip()
        return payloads

    def execute(self, index: int, action: str) -> int:
        outlet = self.outlets[index].outlet
        if action == "ON":
            return outlet.setPowerState(pdumodel.Outlet.PowerState.PS_ON)
        if action == "OFF":
            return outlet.setPowerState(pdumodel.Outlet.PowerState.PS_OFF)
        return outlet.cyclePowerState()
