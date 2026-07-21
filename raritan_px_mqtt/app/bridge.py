from __future__ import annotations

import json
import logging
import os
import queue
import signal
import ssl
import threading
import time
from pathlib import Path
from typing import Any

import paho.mqtt.client as mqtt

from models import sanitize
from raritan_device import RaritanDevice

LOG = logging.getLogger("raritan2mqtt")
DISCOVERY_CACHE = Path("/data/discovery_topics.json")


def env_bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


def json_publish(client: mqtt.Client, topic: str, payload: dict[str, Any], retain: bool = True) -> None:
    message = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
    result = client.publish(topic, message, qos=0, retain=retain)
    if result.rc != mqtt.MQTT_ERR_SUCCESS:
        LOG.warning("MQTT publish failed for %s: rc=%s", topic, result.rc)


class Bridge:
    def __init__(self) -> None:
        self.poll_interval = max(5, int(os.getenv("POLL_INTERVAL", "15")))
        self.discovery_prefix = os.getenv("DISCOVERY_PREFIX", "homeassistant").strip("/")
        topic_prefix = os.getenv("TOPIC_PREFIX", "raritan2mqtt").strip("/")
        self.device = RaritanDevice(
            host=os.environ["PDU_HOST"],
            username=os.environ["PDU_USERNAME"],
            password=os.environ["PDU_PASSWORD"],
            protocol=os.getenv("PDU_PROTOCOL", "https"),
            verify_ssl=env_bool("PDU_VERIFY_SSL", False),
            timeout=max(10, self.poll_interval),
            topic_prefix=topic_prefix,
        )

        self.stop_event = threading.Event()
        self.mqtt_connected = threading.Event()
        self.commands: queue.Queue[tuple[int, str]] = queue.Queue()
        self.discovery_topics: set[str] = set()
        self.client = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            client_id=f"raritan2mqtt_{sanitize(self.device.host)}",
            clean_session=True,
        )
        self.client.username_pw_set(os.getenv("MQTT_USERNAME", ""), os.getenv("MQTT_PASSWORD", ""))
        if env_bool("MQTT_SSL", False):
            self.client.tls_set(cert_reqs=ssl.CERT_REQUIRED)
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_message = self._on_message
        self.mqtt_host = os.environ["MQTT_HOST"]
        self.mqtt_port = int(os.environ["MQTT_PORT"])

    def connect_device(self) -> None:
        self.device.connect()

    def connect_mqtt(self) -> None:
        self.client.will_set(self.device.availability_topic, "offline", qos=0, retain=True)
        LOG.info("Connecting to existing MQTT broker at %s:%d", self.mqtt_host, self.mqtt_port)
        self.client.connect(self.mqtt_host, self.mqtt_port, keepalive=60)
        self.client.loop_start()
        if not self.mqtt_connected.wait(timeout=20):
            raise RuntimeError("Timed out while connecting to the Supervisor MQTT service")

    def _on_connect(self, client: mqtt.Client, userdata: Any, flags: Any, reason_code: Any, properties: Any) -> None:
        if reason_code != 0:
            LOG.error("MQTT connection failed: %s", reason_code)
            return
        self.mqtt_connected.set()
        LOG.info("Connected to MQTT broker")
        client.subscribe(f"{self.device.base_topic}/outlet/+/set", qos=0)
        client.subscribe(f"{self.device.base_topic}/outlet/+/cycle", qos=0)
        self.publish_discovery()
        client.publish(self.device.availability_topic, "online", qos=0, retain=True)

    def _on_disconnect(self, client: mqtt.Client, userdata: Any, flags: Any, reason_code: Any, properties: Any) -> None:
        self.mqtt_connected.clear()
        if not self.stop_event.is_set():
            LOG.warning("Disconnected from MQTT broker: %s", reason_code)

    def _on_message(self, client: mqtt.Client, userdata: Any, message: mqtt.MQTTMessage) -> None:
        parts = message.topic.split("/")
        try:
            pos = parts.index("outlet")
            index = int(parts[pos + 1]) - 1
            command_type = parts[pos + 2]
            payload = message.payload.decode("utf-8", errors="replace").strip().upper()
        except (ValueError, IndexError):
            LOG.warning("Ignoring malformed command topic: %s", message.topic)
            return
        if not 0 <= index < len(self.device.outlets):
            LOG.warning("Ignoring command for unknown outlet %d", index + 1)
        elif command_type == "set" and payload in {"ON", "OFF"}:
            self.commands.put((index, payload))
        elif command_type == "cycle":
            self.commands.put((index, "CYCLE"))

    def publish_discovery(self) -> None:
        current: set[str] = set()
        info = dict(self.device.device_info)
        for binding in self.device.sensors:
            scope_name = (
                f"Inlet {binding.index + 1}"
                if binding.scope == "inlet"
                else self.device.outlets[binding.index].name
            )
            object_id = sanitize(f"{self.device.device_id}_{binding.scope}_{binding.index + 1}_{binding.attribute}")
            topic = f"{self.discovery_prefix}/sensor/{object_id}/config"
            payload: dict[str, Any] = {
                "name": f"{scope_name} {binding.spec.label}",
                "unique_id": object_id,
                "state_topic": binding.state_topic,
                "value_template": "{{ value_json.%s }}" % binding.state_key,
                "availability_topic": self.device.availability_topic,
                "payload_available": "online",
                "payload_not_available": "offline",
                "device": info,
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
            current.add(topic)

        for outlet in self.device.outlets:
            if not outlet.switchable:
                continue
            switch_id = sanitize(f"{self.device.device_id}_outlet_{outlet.index + 1}_switch")
            switch_topic = f"{self.discovery_prefix}/switch/{switch_id}/config"
            json_publish(
                self.client,
                switch_topic,
                {
                    "name": outlet.name,
                    "unique_id": switch_id,
                    "state_topic": outlet.state_topic,
                    "value_template": "{{ value_json.power_state }}",
                    "json_attributes_topic": outlet.state_topic,
                    "command_topic": outlet.command_topic,
                    "payload_on": "ON",
                    "payload_off": "OFF",
                    "state_on": "ON",
                    "state_off": "OFF",
                    "availability_topic": self.device.availability_topic,
                    "payload_available": "online",
                    "payload_not_available": "offline",
                    "icon": "mdi:power-socket",
                    "device": info,
                },
            )
            current.add(switch_topic)

            button_id = sanitize(f"{self.device.device_id}_outlet_{outlet.index + 1}_cycle")
            button_topic = f"{self.discovery_prefix}/button/{button_id}/config"
            json_publish(
                self.client,
                button_topic,
                {
                    "name": f"{outlet.name} Power cycle",
                    "unique_id": button_id,
                    "command_topic": outlet.cycle_topic,
                    "payload_press": "CYCLE",
                    "availability_topic": self.device.availability_topic,
                    "payload_available": "online",
                    "payload_not_available": "offline",
                    "icon": "mdi:restart-alert",
                    "device": info,
                },
            )
            current.add(button_topic)

        try:
            old = set(json.loads(DISCOVERY_CACHE.read_text(encoding="utf-8")))
        except (FileNotFoundError, json.JSONDecodeError, TypeError):
            old = set()
        for stale_topic in old - current:
            self.client.publish(stale_topic, "", qos=0, retain=True)
        DISCOVERY_CACHE.write_text(json.dumps(sorted(current), indent=2), encoding="utf-8")
        self.discovery_topics = current
        LOG.info("Published %d MQTT Discovery configurations", len(current))

    def poll(self) -> None:
        for topic, payload in self.device.poll().items():
            json_publish(self.client, topic, payload)
        self.client.publish(self.device.availability_topic, "online", qos=0, retain=True)

    def process_commands(self) -> bool:
        processed = False
        while True:
            try:
                index, action = self.commands.get_nowait()
            except queue.Empty:
                return processed
            processed = True
            outlet = self.device.outlets[index]
            try:
                result = self.device.execute(index, action)
                if result == 0:
                    LOG.info("Executed %s for %s", action, outlet.name)
                else:
                    LOG.error("Raritan rejected %s for %s with result code %s", action, outlet.name, result)
            except Exception as exc:
                LOG.exception("Unable to execute %s for %s: %s", action, outlet.name, exc)

    def run(self) -> None:
        while not self.stop_event.is_set():
            try:
                self.connect_device()
                break
            except Exception as exc:
                LOG.error("PDU initialization failed: %s; retrying in 15 seconds", exc)
                self.stop_event.wait(15)
        if self.stop_event.is_set():
            return
        self.connect_mqtt()

        next_poll = 0.0
        failures = 0
        while not self.stop_event.is_set():
            command_processed = self.process_commands()
            now = time.monotonic()
            if command_processed:
                next_poll = min(next_poll, now + 0.5)
            if now >= next_poll:
                try:
                    self.poll()
                    failures = 0
                except Exception as exc:
                    failures += 1
                    LOG.error("PDU polling failed (%d): %s", failures, exc)
                    self.client.publish(self.device.availability_topic, "offline", qos=0, retain=True)
                    if failures >= 3:
                        try:
                            LOG.warning("Reinitializing the PDU connection")
                            self.connect_device()
                            self.publish_discovery()
                            failures = 0
                        except Exception as reconnect_exc:
                            LOG.error("PDU reinitialization failed: %s", reconnect_exc)
                next_poll = time.monotonic() + self.poll_interval
            self.stop_event.wait(0.2)

    def stop(self) -> None:
        self.stop_event.set()
        try:
            self.client.publish(self.device.availability_topic, "offline", qos=0, retain=True).wait_for_publish(timeout=2)
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
    bridge = Bridge()

    def handle_signal(signum: int, frame: Any) -> None:
        LOG.info("Received signal %s, stopping", signum)
        bridge.stop_event.set()

    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)
    try:
        bridge.run()
    finally:
        bridge.stop()
