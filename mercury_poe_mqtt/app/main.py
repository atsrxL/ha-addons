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
from typing import Any
from urllib.parse import urlparse

import paho.mqtt.client as mqtt
from mercury import MercuryError, MercurySwitch, PoeSnapshot

LOG = logging.getLogger("mercury_poe_mqtt")


def env_bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


def slug(value: str) -> str:
    return re.sub(r"[^a-z0-9_-]+", "_", value.lower()).strip("_") or "switch"


def publish_json(
    client: mqtt.Client, topic: str, payload: dict[str, Any], retain: bool = True
) -> None:
    result = client.publish(
        topic,
        json.dumps(payload, separators=(",", ":"), ensure_ascii=False),
        qos=0,
        retain=retain,
    )
    if result.rc != mqtt.MQTT_ERR_SUCCESS:
        LOG.warning("MQTT publish failed for %s: rc=%s", topic, result.rc)


class Bridge:
    def __init__(self) -> None:
        self.switch = MercurySwitch(
            os.environ["SWITCH_URL"],
            os.environ["SWITCH_USERNAME"],
            os.environ["SWITCH_PASSWORD"],
            max(3, int(os.getenv("REQUEST_TIMEOUT", "10"))),
        )
        self.poll_interval = max(1, int(os.getenv("POLL_INTERVAL", "30")))
        self.discovery_prefix = os.getenv("DISCOVERY_PREFIX", "homeassistant").strip(
            "/"
        )
        self.topic_prefix = os.getenv("TOPIC_PREFIX", "mercury_poe").strip("/")
        host = urlparse(self.switch.base_url).hostname or self.switch.base_url
        self.device_id = slug(host)
        self.base_topic = f"{self.topic_prefix}/{self.device_id}"
        self.availability_topic = f"{self.base_topic}/availability"
        self.commands: queue.Queue[int] = queue.Queue()
        self.stop_event = threading.Event()
        self.mqtt_connected = threading.Event()
        self.snapshot: PoeSnapshot | None = None

        self.client = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            client_id=f"mercury_poe_{self.device_id}",
            clean_session=True,
        )
        self.client.username_pw_set(
            os.getenv("MQTT_USERNAME", ""), os.getenv("MQTT_PASSWORD", "")
        )
        if env_bool("MQTT_SSL", False):
            self.client.tls_set(cert_reqs=ssl.CERT_REQUIRED)
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_message = self._on_message

    @property
    def device(self) -> dict[str, Any]:
        model = self.snapshot.model if self.snapshot else "PoE Switch"
        return {
            "identifiers": [f"mercury_poe_{self.device_id}"],
            "name": f"Mercury {model}",
            "manufacturer": "Mercury",
            "model": model,
            "configuration_url": f"{self.switch.base_url}/",
        }

    def _on_connect(
        self,
        client: mqtt.Client,
        userdata: Any,
        flags: Any,
        reason_code: Any,
        properties: Any,
    ) -> None:
        is_failure = getattr(reason_code, "is_failure", reason_code != 0)
        if is_failure:
            LOG.error("MQTT connection failed: %s", reason_code)
            return
        self.mqtt_connected.set()
        client.subscribe(f"{self.base_topic}/port/+/reboot", qos=0)
        client.publish(self.availability_topic, "online", qos=0, retain=True)
        if self.snapshot:
            self.publish_discovery()
        LOG.info("Connected to MQTT broker")

    def _on_disconnect(
        self,
        client: mqtt.Client,
        userdata: Any,
        flags: Any,
        reason_code: Any,
        properties: Any,
    ) -> None:
        self.mqtt_connected.clear()
        if not self.stop_event.is_set():
            LOG.warning("Disconnected from MQTT broker: %s", reason_code)

    def _on_message(
        self, client: mqtt.Client, userdata: Any, message: mqtt.MQTTMessage
    ) -> None:
        match = re.fullmatch(
            rf"{re.escape(self.base_topic)}/port/(\d+)/reboot", message.topic
        )
        if (
            not match
            or message.payload.decode("utf-8", errors="replace").strip().upper()
            != "PRESS"
        ):
            return
        self.commands.put(int(match.group(1)))

    def connect_mqtt(self) -> None:
        self.client.will_set(self.availability_topic, "offline", qos=0, retain=True)
        host = os.environ["MQTT_HOST"]
        port = int(os.environ["MQTT_PORT"])
        LOG.info("Connecting to existing MQTT broker at %s:%d", host, port)
        self.client.connect(host, port, keepalive=60)
        self.client.loop_start()
        if not self.mqtt_connected.wait(20):
            raise RuntimeError(
                "Timed out while connecting to the Supervisor MQTT service"
            )

    def _sensor_config(
        self,
        object_id: str,
        name: str,
        state_topic: str,
        value_template: str,
        unit: str | None = None,
        device_class: str | None = None,
        icon: str | None = None,
        entity_category: str | None = None,
    ) -> None:
        unique_id = f"mercury_{self.device_id}_{object_id}"
        payload: dict[str, Any] = {
            "name": name,
            "unique_id": unique_id,
            "state_topic": state_topic,
            "value_template": value_template,
            "availability_topic": self.availability_topic,
            "payload_available": "online",
            "payload_not_available": "offline",
            "device": self.device,
        }
        if unit:
            payload["unit_of_measurement"] = unit
            payload["state_class"] = "measurement"
        if device_class:
            payload["device_class"] = device_class
        if icon:
            payload["icon"] = icon
        if entity_category:
            payload["entity_category"] = entity_category
        publish_json(
            self.client, f"{self.discovery_prefix}/sensor/{unique_id}/config", payload
        )

    def publish_discovery(self) -> None:
        if not self.snapshot:
            return
        system_topic = f"{self.base_topic}/state"
        system_sensors = (
            ("total_power", "PoE 总功率", "system_total_w", "W", "power", "mdi:flash"),
            (
                "used_power",
                "PoE 已使用功率",
                "system_used_w",
                "W",
                "power",
                "mdi:transmission-tower-export",
            ),
            (
                "remaining_power",
                "PoE 剩余功率",
                "system_remaining_w",
                "W",
                "power",
                "mdi:transmission-tower-import",
            ),
            (
                "usage_percent",
                "PoE 功率占用率",
                "system_usage_percent",
                "%",
                None,
                "mdi:gauge",
            ),
        )
        for object_id, name, key, unit, device_class, icon in system_sensors:
            self._sensor_config(
                object_id,
                name,
                system_topic,
                f"{{{{ value_json.{key} }}}}",
                unit,
                device_class,
                icon,
            )

        for port in self.snapshot.ports:
            number = int(port["port"])
            state_topic = f"{self.base_topic}/port/{number}/state"
            specs = (
                ("power", "功率", "power_w", "W", "power", "mdi:flash", None),
                (
                    "current",
                    "电流",
                    "current_ma",
                    "mA",
                    "current",
                    "mdi:current-dc",
                    None,
                ),
                ("voltage", "电压", "voltage_v", "V", "voltage", "mdi:sine-wave", None),
                (
                    "max_power",
                    "最大功率",
                    "max_power_w",
                    "W",
                    "power",
                    "mdi:flash-alert",
                    "diagnostic",
                ),
                (
                    "power_status",
                    "供电状态",
                    "power_status",
                    None,
                    None,
                    "mdi:power-plug",
                    None,
                ),
                (
                    "pd_class",
                    "PD Class",
                    "pd_class",
                    None,
                    None,
                    "mdi:power-socket",
                    "diagnostic",
                ),
                (
                    "priority",
                    "优先级",
                    "priority",
                    None,
                    None,
                    "mdi:sort",
                    "diagnostic",
                ),
            )
            for key_suffix, label, key, unit, device_class, icon, category in specs:
                self._sensor_config(
                    f"port_{number}_{key_suffix}",
                    f"Port {number} {label}",
                    state_topic,
                    f"{{{{ value_json.{key} }}}}",
                    unit,
                    device_class,
                    icon,
                    category,
                )

            button_id = f"mercury_{self.device_id}_port_{number}_reboot"
            publish_json(
                self.client,
                f"{self.discovery_prefix}/button/{button_id}/config",
                {
                    "name": f"Port {number} 重新上电",
                    "unique_id": button_id,
                    "command_topic": f"{self.base_topic}/port/{number}/reboot",
                    "payload_press": "PRESS",
                    "availability_topic": self.availability_topic,
                    "payload_available": "online",
                    "payload_not_available": "offline",
                    "icon": "mdi:restart-alert",
                    "device": self.device,
                },
            )
        LOG.info("Published MQTT Discovery for %d PoE ports", len(self.snapshot.ports))

    def publish_state(self) -> None:
        if not self.snapshot:
            return
        publish_json(
            self.client,
            f"{self.base_topic}/state",
            {
                "system_total_w": self.snapshot.system_total_w,
                "system_used_w": self.snapshot.system_used_w,
                "system_remaining_w": self.snapshot.system_remaining_w,
                "system_usage_percent": self.snapshot.system_usage_percent,
            },
        )
        for port in self.snapshot.ports:
            publish_json(
                self.client, f"{self.base_topic}/port/{port['port']}/state", port
            )
        self.client.publish(self.availability_topic, "online", qos=0, retain=True)

    def process_commands(self) -> None:
        while True:
            try:
                port = self.commands.get_nowait()
            except queue.Empty:
                return
            try:
                self.switch.reboot_port(port)
                LOG.info("Port %d re-power command accepted by switch", port)
                self.stop_event.wait(2)
                self.snapshot = self.switch.poll()
                self.publish_state()
            except MercuryError as exc:
                LOG.error("Unable to re-power Port %d: %s", port, exc)

    def run(self) -> None:
        while not self.stop_event.is_set():
            try:
                self.snapshot = self.switch.poll()
                LOG.info(
                    "Connected to %s: %.1f W / %.1f W (%.1f%%), %d ports",
                    self.snapshot.model,
                    self.snapshot.system_used_w,
                    self.snapshot.system_total_w,
                    self.snapshot.system_usage_percent,
                    len(self.snapshot.ports),
                )
                break
            except MercuryError as exc:
                LOG.error(
                    "Switch initialization failed: %s; retrying in 15 seconds", exc
                )
                self.stop_event.wait(15)
        if self.stop_event.is_set():
            return

        self.connect_mqtt()
        self.publish_discovery()
        self.publish_state()
        next_poll = time.monotonic() + self.poll_interval
        failures = 0
        while not self.stop_event.is_set():
            self.process_commands()
            now = time.monotonic()
            if now >= next_poll:
                try:
                    self.snapshot = self.switch.poll()
                    self.publish_state()
                    failures = 0
                except MercuryError as exc:
                    failures += 1
                    LOG.error("PoE polling failed (%d): %s", failures, exc)
                    if failures >= 3:
                        self.client.publish(
                            self.availability_topic, "offline", qos=0, retain=True
                        )
                next_poll = now + self.poll_interval
            self.stop_event.wait(min(0.25, max(0.0, next_poll - time.monotonic())))

    def stop(self, signum: int | None = None, frame: Any = None) -> None:
        self.stop_event.set()

    def close(self) -> None:
        if self.mqtt_connected.is_set():
            self.client.publish(self.availability_topic, "offline", qos=0, retain=True)
        self.client.disconnect()
        self.client.loop_stop()


def main() -> None:
    logging.basicConfig(
        level=getattr(logging, os.getenv("LOG_LEVEL", "INFO").upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    bridge = Bridge()
    signal.signal(signal.SIGTERM, bridge.stop)
    signal.signal(signal.SIGINT, bridge.stop)
    try:
        bridge.run()
    finally:
        bridge.close()


if __name__ == "__main__":
    main()
