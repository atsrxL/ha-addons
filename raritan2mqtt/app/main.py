#!/usr/bin/env python3
"""Raritan PX2/PX3 JSON-RPC to Home Assistant MQTT Discovery bridge."""

from __future__ import annotations

import json
import logging
import os
import queue
import re
import signal
import ssl
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable

import paho.mqtt.client as mqtt
from raritan import rpc
from raritan.rpc import pdumodel


LOG = logging.getLogger("raritan2mqtt")
DATA_DIR = Path("/data")
DISCOVERY_CACHE = DATA_DIR / "discovery_topics.json"


@dataclass(frozen=True)
class SensorSpec:
    label: str
    unit: str | None = None
    device_class: str | None = None
    state_class: str | None = "measurement"
    precision: int | None = None
    icon: str | None = None


# The bridge probes all of these attributes and only exposes sensors that the
# PDU actually implements. Unsupported references return an RPC exception and
# are ignored, so the same add-on also works with other PX2/PX3 variants.
SENSOR_SPECS: dict[str, SensorSpec] = {
    "voltage": SensorSpec("Voltage", "V", "voltage", precision=1),
    "current": SensorSpec("Current", "A", "current", precision=3),
    "peakCurrent": SensorSpec("Peak current", "A", "current", precision=3),
    "maximumCurrent": SensorSpec("Maximum current", "A", "current", precision=3),
    "residualCurrent": SensorSpec("Residual current", "A", "current", precision=3),
    "residualACCurrent": SensorSpec("Residual AC current", "A", "current", precision=3),
    "residualDCCurrent": SensorSpec("Residual DC current", "A", "current", precision=3),
    "unbalancedCurrent": SensorSpec("Current unbalance", "%", precision=1),
    "activePower": SensorSpec("Active power", "W", "power", precision=1),
    "reactivePower": SensorSpec("Reactive power", "var", "reactive_power", precision=1),
    "apparentPower": SensorSpec("Apparent power", "VA", "apparent_power", precision=1),
    "powerFactor": SensorSpec("Power factor", None, "power_factor", precision=2),
    "displacementPowerFactor": SensorSpec("Displacement power factor", None, "power_factor", precision=2),
    "activeEnergy": SensorSpec("Active energy", "Wh", "energy", "total_increasing", 3),
    "apparentEnergy": SensorSpec("Apparent energy", "VAh", None, "total_increasing", 3),
    "phaseAngle": SensorSpec("Phase angle", "°", None, precision=1),
    "lineFrequency": SensorSpec("Frequency", "Hz", "frequency", precision=1),
    "crestFactor": SensorSpec("Crest factor", None, None, precision=2),
    "voltageThd": SensorSpec("Voltage THD", "%", None, precision=1),
    "currentThd": SensorSpec("Current THD", "%", None, precision=1),
    "inrushCurrent": SensorSpec("Inrush current", "A", "current", precision=3),
}


@dataclass
class SensorBinding:
    scope: str
    index: int
    attribute: str
    sensor: Any
    spec: SensorSpec
    state_topic: str = ""
    state_key: str = ""


@dataclass
class OutletBinding:
    index: int
    outlet: Any
    label: str
    name: str
    switchable: bool
    state_topic: str = ""
    command_topic: str = ""
    cycle_topic: str = ""


def env_bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


def sanitize(value: str) -> str:
    text = re.sub(r"[^a-zA-Z0-9_-]+", "_", value.strip())
    return text.strip("_").lower() or "unknown"


def safe_attr(obj: Any, name: str, default: Any = None) -> Any:
    try:
        value = getattr(obj, name)
    except Exception:
        return default
    return default if value is None else value


def json_publish(client: mqtt.Client, topic: str, payload: dict[str, Any], *, retain: bool = True) -> None:
    result = client.publish(topic, json.dumps(payload, separators=(",", ":"), ensure_ascii=False), qos=0, retain=retain)
    if result.rc != mqtt.MQTT_ERR_SUCCESS:
        LOG.warning("MQTT publish failed for %s: rc=%s", topic, result.rc)


def rpc_bulk(agent: Any, calls: Iterable[tuple[Callable[..., Any], list[Any]]]) -> list[Any]:
    call_list = list(calls)
    if not call_list:
        return []

    # BulkRequestHelper is present in the firmware-matched 3.6.0 SDK and
    # combines all queued reads into one HTTP transaction.
    helper = rpc.BulkRequestHelper(agent)
    for method, args in call_list:
        helper.add_request(method, *args)
    return helper.perform_bulk(raise_subreq_failure=False)


class RaritanBridge:
    def __init__(self) -> None:
        self.pdu_host = os.environ["PDU_HOST"]
        self.pdu_username = os.environ["PDU_USERNAME"]
        self.pdu_password = os.environ["PDU_PASSWORD"]
        self.pdu_protocol = os.getenv("PDU_PROTOCOL", "https")
        self.verify_ssl = env_bool("PDU_VERIFY_SSL", False)
        self.poll_interval = max(1, int(os.getenv("POLL_INTERVAL", "15")))
        self.discovery_prefix = os.getenv("DISCOVERY_PREFIX", "homeassistant").strip("/")
        self.topic_prefix = os.getenv("TOPIC_PREFIX", "raritan2mqtt").strip("/")

        self.mqtt_host = os.environ["MQTT_HOST"]
        self.mqtt_port = int(os.environ["MQTT_PORT"])
        self.mqtt_username = os.getenv("MQTT_USERNAME", "")
        self.mqtt_password = os.getenv("MQTT_PASSWORD", "")
        self.mqtt_ssl = env_bool("MQTT_SSL", False)

        self.stop_event = threading.Event()
        self.command_queue: queue.Queue[tuple[int, str]] = queue.Queue()

        self.agent: Any = None
        self.pdu: Any = None
        self.inlets: list[Any] = []
        self.outlets: list[OutletBinding] = []
        self.sensors: list[SensorBinding] = []
        self.device_id = sanitize(self.pdu_host)
        self.base_topic = f"{self.topic_prefix}/{self.device_id}"
        self.availability_topic = f"{self.base_topic}/availability"
        self.device: dict[str, Any] = {}
        self.discovery_topics: set[str] = set()
        self.mqtt_connected = threading.Event()

        self.client = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            client_id=f"raritan2mqtt_{sanitize(self.pdu_host)}",
            clean_session=True,
        )
        self.client.username_pw_set(self.mqtt_username, self.mqtt_password)
        if self.mqtt_ssl:
            self.client.tls_set(cert_reqs=ssl.CERT_REQUIRED)
        self.client.on_connect = self._on_mqtt_connect
        self.client.on_disconnect = self._on_mqtt_disconnect
        self.client.on_message = self._on_mqtt_message

    def connect_pdu(self) -> None:
        LOG.info("Connecting to Raritan JSON-RPC API at %s://%s", self.pdu_protocol, self.pdu_host)
        self.agent = rpc.Agent(
            self.pdu_protocol,
            self.pdu_host,
            self.pdu_username,
            self.pdu_password,
            disable_certificate_verification=not self.verify_ssl,
            timeout=max(10, self.poll_interval),
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
        for result, label in ((nameplate, "nameplate"), (metadata, "metadata"), (inlets, "inlets"), (outlet_objects, "outlets")):
            if isinstance(result, Exception):
                raise RuntimeError(f"Unable to read PDU {label}: {result}")

        self.inlets = list(inlets)
        outlet_objects = list(outlet_objects)

        manufacturer = str(safe_attr(nameplate, "manufacturer", "Raritan"))
        model = str(safe_attr(nameplate, "model", "PX PDU"))
        serial_number = str(safe_attr(nameplate, "serialNumber", self.pdu_host))
        firmware = str(safe_attr(metadata, "fwRevision", ""))
        configured_name = "" if isinstance(settings, Exception) else str(safe_attr(settings, "name", ""))
        display_name = configured_name.strip() or f"Raritan {model}"

        self.device_id = sanitize(serial_number)
        self.base_topic = f"{self.topic_prefix}/{self.device_id}"
        self.availability_topic = f"{self.base_topic}/availability"
        self.client.will_set(self.availability_topic, "offline", qos=0, retain=True)
        self.device = {
            "identifiers": [f"raritan_{self.device_id}"],
            "name": display_name,
            "manufacturer": manufacturer,
            "model": model,
            "serial_number": serial_number,
            "configuration_url": f"{self.pdu_protocol}://{self.pdu_host}/",
        }
        if firmware:
            self.device["sw_version"] = firmware

        # Fetch user names and static metadata in one request.
        calls: list[tuple[Callable[..., Any], list[Any]]] = []
        for outlet in outlet_objects:
            calls.extend([(outlet.getMetaData, []), (outlet.getSettings, []), (outlet.getSensors, [])])
        outlet_results = rpc_bulk(self.agent, calls)

        self.outlets = []
        outlet_sensor_structs: list[tuple[int, Any]] = []
        for idx, outlet in enumerate(outlet_objects):
            meta, outlet_settings, sensor_struct = outlet_results[idx * 3 : idx * 3 + 3]
            label = str(safe_attr(meta, "label", idx + 1)) if not isinstance(meta, Exception) else str(idx + 1)
            custom_name = str(safe_attr(outlet_settings, "name", "")) if not isinstance(outlet_settings, Exception) else ""
            name = custom_name.strip() or f"Outlet {label}"
            switchable = bool(safe_attr(meta, "isSwitchable", True)) if not isinstance(meta, Exception) else True
            binding = OutletBinding(
                index=idx,
                outlet=outlet,
                label=label,
                name=name,
                switchable=switchable,
                state_topic=f"{self.base_topic}/outlet/{idx + 1}/state",
                command_topic=f"{self.base_topic}/outlet/{idx + 1}/set",
                cycle_topic=f"{self.base_topic}/outlet/{idx + 1}/cycle",
            )
            self.outlets.append(binding)
            if not isinstance(sensor_struct, Exception):
                outlet_sensor_structs.append((idx, sensor_struct))

        inlet_sensor_results = rpc_bulk(self.agent, [(inlet.getSensors, []) for inlet in self.inlets])
        candidates: list[SensorBinding] = []
        for idx, sensor_struct in enumerate(inlet_sensor_results):
            if isinstance(sensor_struct, Exception):
                continue
            candidates.extend(self._sensor_candidates("inlet", idx, sensor_struct))
        for idx, sensor_struct in outlet_sensor_structs:
            candidates.extend(self._sensor_candidates("outlet", idx, sensor_struct))

        # Probe candidates once. A failed RPC means that the reference is not
        # implemented on this hardware/firmware and should not become an entity.
        probe_results = rpc_bulk(self.agent, [(candidate.sensor.getReading, []) for candidate in candidates])
        self.sensors = []
        for candidate, reading in zip(candidates, probe_results, strict=True):
            if isinstance(reading, Exception):
                continue
            candidate.state_key = candidate.attribute
            if candidate.scope == "inlet":
                candidate.state_topic = f"{self.base_topic}/inlet/{candidate.index + 1}/state"
            else:
                candidate.state_topic = self.outlets[candidate.index].state_topic
            self.sensors.append(candidate)

        LOG.info(
            "Detected %d inlet(s), %d outlet(s), %d usable numeric sensor(s)",
            len(self.inlets),
            len(self.outlets),
            len(self.sensors),
        )

    def _sensor_candidates(self, scope: str, index: int, sensor_struct: Any) -> list[SensorBinding]:
        candidates: list[SensorBinding] = []
        for attribute, spec in SENSOR_SPECS.items():
            try:
                sensor = getattr(sensor_struct, attribute)
            except Exception:
                continue
            if sensor is None or not hasattr(sensor, "getReading"):
                continue
            candidates.append(SensorBinding(scope, index, attribute, sensor, spec))
        return candidates

    def connect_mqtt(self) -> None:
        LOG.info("Connecting to existing MQTT broker at %s:%d", self.mqtt_host, self.mqtt_port)
        self.client.connect(self.mqtt_host, self.mqtt_port, keepalive=60)
        self.client.loop_start()
        if not self.mqtt_connected.wait(timeout=20):
            raise RuntimeError("Timed out while connecting to the Supervisor MQTT service")

    def _on_mqtt_connect(self, client: mqtt.Client, userdata: Any, flags: Any, reason_code: Any, properties: Any) -> None:
        if reason_code.is_failure:
            LOG.error("MQTT connection failed: %s", reason_code)
            return
        LOG.info("Connected to MQTT broker")
        self.mqtt_connected.set()
        client.subscribe(f"{self.base_topic}/outlet/+/set", qos=0)
        client.subscribe(f"{self.base_topic}/outlet/+/cycle", qos=0)
        self.publish_discovery()
        client.publish(self.availability_topic, "online", qos=0, retain=True)

    def _on_mqtt_disconnect(self, client: mqtt.Client, userdata: Any, disconnect_flags: Any, reason_code: Any, properties: Any) -> None:
        self.mqtt_connected.clear()
        if not self.stop_event.is_set():
            LOG.warning("Disconnected from MQTT broker: %s", reason_code)

    def _on_mqtt_message(self, client: mqtt.Client, userdata: Any, message: mqtt.MQTTMessage) -> None:
        parts = message.topic.split("/")
        try:
            outlet_pos = parts.index("outlet")
            outlet_index = int(parts[outlet_pos + 1]) - 1
            action_type = parts[outlet_pos + 2]
            payload = message.payload.decode("utf-8", errors="replace").strip().upper()
        except (ValueError, IndexError):
            LOG.warning("Ignoring malformed command topic: %s", message.topic)
            return

        if not 0 <= outlet_index < len(self.outlets):
            LOG.warning("Ignoring command for unknown outlet %d", outlet_index + 1)
            return
        if action_type == "set" and payload in {"ON", "OFF"}:
            self.command_queue.put((outlet_index, payload))
        elif action_type == "cycle":
            self.command_queue.put((outlet_index, "CYCLE"))

    def _entity_device(self) -> dict[str, Any]:
        return dict(self.device)

    def publish_discovery(self) -> None:
        current_topics: set[str] = set()

        for binding in self.sensors:
            scope_name = f"Inlet {binding.index + 1}" if binding.scope == "inlet" else self.outlets[binding.index].name
            object_id = sanitize(f"{self.device_id}_{binding.scope}_{binding.index + 1}_{binding.attribute}")
            topic = f"{self.discovery_prefix}/sensor/{object_id}/config"
            payload: dict[str, Any] = {
                "name": f"{scope_name} {binding.spec.label}",
                "unique_id": object_id,
                "state_topic": binding.state_topic,
                "value_template": "{{ value_json.%s }}" % binding.state_key,
                "availability_topic": self.availability_topic,
                "payload_available": "online",
                "payload_not_available": "offline",
                "device": self._entity_device(),
            }
            if binding.spec.unit:
                payload["unit_of_measurement"] = binding.spec.unit
            if binding.spec.device_class:
                payload["device_class"] = binding.spec.device_class
            if binding.spec.state_class:
                payload["state_class"] = binding.spec.state_class
            if binding.spec.precision is not None:
                payload["suggested_display_precision"] = binding.spec.precision
            if binding.spec.icon:
                payload["icon"] = binding.spec.icon
            json_publish(self.client, topic, payload)
            current_topics.add(topic)

        for outlet in self.outlets:
            if not outlet.switchable:
                continue
            switch_id = sanitize(f"{self.device_id}_outlet_{outlet.index + 1}_switch")
            switch_topic = f"{self.discovery_prefix}/switch/{switch_id}/config"
            switch_payload = {
                "name": outlet.name,
                "unique_id": switch_id,
                "state_topic": outlet.state_topic,
                "value_template": "{{ value_json.power_state }}",
                "command_topic": outlet.command_topic,
                "payload_on": "ON",
                "payload_off": "OFF",
                "state_on": "ON",
                "state_off": "OFF",
                "availability_topic": self.availability_topic,
                "payload_available": "online",
                "payload_not_available": "offline",
                "icon": "mdi:power-socket",
                "device": self._entity_device(),
            }
            json_publish(self.client, switch_topic, switch_payload)
            current_topics.add(switch_topic)

            button_id = sanitize(f"{self.device_id}_outlet_{outlet.index + 1}_cycle")
            button_topic = f"{self.discovery_prefix}/button/{button_id}/config"
            button_payload = {
                "name": f"{outlet.name} Power cycle",
                "unique_id": button_id,
                "command_topic": outlet.cycle_topic,
                "payload_press": "CYCLE",
                "availability_topic": self.availability_topic,
                "payload_available": "online",
                "payload_not_available": "offline",
                "icon": "mdi:restart-alert",
                "device": self._entity_device(),
            }
            json_publish(self.client, button_topic, button_payload)
            current_topics.add(button_topic)

        old_topics: set[str] = set()
        try:
            old_topics = set(json.loads(DISCOVERY_CACHE.read_text(encoding="utf-8")))
        except (FileNotFoundError, json.JSONDecodeError, TypeError):
            pass
        for stale_topic in old_topics - current_topics:
            self.client.publish(stale_topic, "", qos=0, retain=True)
        DISCOVERY_CACHE.write_text(json.dumps(sorted(current_topics), indent=2), encoding="utf-8")
        self.discovery_topics = current_topics
        LOG.info("Published %d MQTT Discovery configurations", len(current_topics))

    @staticmethod
    def reading_value(reading: Any, spec: SensorSpec) -> float | int | None:
        if not bool(safe_attr(reading, "available", False)) or not bool(safe_attr(reading, "valid", False)):
            return None
        value = safe_attr(reading, "value", None)
        if value is None:
            return None
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            return None
        if spec.precision is not None:
            numeric = round(numeric, spec.precision)
        return int(numeric) if numeric.is_integer() and spec.precision == 0 else numeric

    def poll(self) -> None:
        calls: list[tuple[Callable[..., Any], list[Any]]] = []
        calls.extend((binding.sensor.getReading, []) for binding in self.sensors)
        calls.extend((outlet.outlet.getState, []) for outlet in self.outlets)
        results = rpc_bulk(self.agent, calls)

        sensor_results = results[: len(self.sensors)]
        outlet_results = results[len(self.sensors) :]
        failed = sum(isinstance(result, Exception) for result in results)
        if results and failed == len(results):
            raise RuntimeError("All Raritan JSON-RPC polling calls failed")

        payloads: dict[str, dict[str, Any]] = {}
        for binding, reading in zip(self.sensors, sensor_results, strict=True):
            if isinstance(reading, Exception):
                continue
            payloads.setdefault(binding.state_topic, {})[binding.state_key] = self.reading_value(reading, binding.spec)

        for outlet, state in zip(self.outlets, outlet_results, strict=True):
            payload = payloads.setdefault(outlet.state_topic, {})
            if isinstance(state, Exception) or not bool(safe_attr(state, "available", False)):
                payload["power_state"] = None
                continue
            power_state = safe_attr(state, "powerState", None)
            payload["power_state"] = "ON" if power_state == pdumodel.Outlet.PowerState.PS_ON else "OFF"
            payload["cycle_in_progress"] = bool(safe_attr(state, "cycleInProgress", False))
            payload["switch_on_in_progress"] = bool(safe_attr(state, "switchOnInProgress", False))
            payload["last_power_state_change"] = safe_attr(state, "lastPowerStateChange", None)

        for topic, payload in payloads.items():
            json_publish(self.client, topic, payload, retain=True)
        self.client.publish(self.availability_topic, "online", qos=0, retain=True)

    def process_commands(self) -> bool:
        processed = False
        while True:
            try:
                index, action = self.command_queue.get_nowait()
            except queue.Empty:
                return processed
            processed = True
            outlet = self.outlets[index]
            try:
                if action == "ON":
                    result = outlet.outlet.setPowerState(pdumodel.Outlet.PowerState.PS_ON)
                elif action == "OFF":
                    result = outlet.outlet.setPowerState(pdumodel.Outlet.PowerState.PS_OFF)
                else:
                    result = outlet.outlet.cyclePowerState()
                if result != 0:
                    LOG.error("Raritan rejected %s for %s with result code %s", action, outlet.name, result)
                else:
                    LOG.info("Executed %s for %s", action, outlet.name)
            except Exception as exc:
                LOG.exception("Unable to execute %s for %s: %s", action, outlet.name, exc)

    def run(self) -> None:
        while not self.stop_event.is_set():
            try:
                self.connect_pdu()
                break
            except Exception as exc:
                LOG.error("PDU initialization failed: %s; retrying in 15 seconds", exc)
                self.stop_event.wait(15)
        if self.stop_event.is_set():
            return

        self.connect_mqtt()
        next_poll = 0.0
        consecutive_failures = 0
        while not self.stop_event.is_set():
            command_processed = self.process_commands()
            now = time.monotonic()
            if command_processed:
                next_poll = min(next_poll, now + 0.5)
            if now >= next_poll:
                try:
                    self.poll()
                    consecutive_failures = 0
                except Exception as exc:
                    consecutive_failures += 1
                    LOG.error("PDU polling failed (%d): %s", consecutive_failures, exc)
                    self.client.publish(self.availability_topic, "offline", qos=0, retain=True)
                    if consecutive_failures >= 3:
                        LOG.warning("Reinitializing the PDU connection")
                        try:
                            self.connect_pdu()
                            self.publish_discovery()
                            consecutive_failures = 0
                        except Exception as reconnect_exc:
                            LOG.error("PDU reinitialization failed: %s", reconnect_exc)
                next_poll = time.monotonic() + self.poll_interval
            self.stop_event.wait(0.2)

    def stop(self) -> None:
        self.stop_event.set()
        try:
            self.client.publish(self.availability_topic, "offline", qos=0, retain=True).wait_for_publish(timeout=2)
        except Exception:
            pass
        try:
            self.client.loop_stop()
            self.client.disconnect()
        except Exception:
            pass


def main() -> None:
    logging.basicConfig(
        level=getattr(logging, os.getenv("LOG_LEVEL", "INFO").upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    bridge = RaritanBridge()

    def handle_signal(signum: int, frame: Any) -> None:
        LOG.info("Received signal %s, stopping", signum)
        bridge.stop_event.set()

    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)
    try:
        bridge.run()
    finally:
        bridge.stop()


if __name__ == "__main__":
    main()
