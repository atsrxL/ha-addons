from __future__ import annotations

import http.cookiejar
import re
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any

PASSWORD_KEY = "RDpbLfCPsJZ7fiv"
PASSWORD_DICTIONARY = (
    "yLwVl0zKqws7LgKPRQ84Mdt708T1qQ3Ha7xv3H7NyU84p21BriUWBU43odz3iP4r"
    "BL3cD02KZciXTysVXiV8ngg6vL48rPJyAUw0HurW20xqxv9aYb4M9wK1Ae0wlro5"
    "10qXeU07kV57fQMc8L6aLgMLwygtc0F10a0Dg70TOoouyFhdysuRMO51yY5ZlOZZ"
    "LEal1h0t9YQW0Ko7oBwmCAHoic4HYbUyVeU3sfQ1xtXcPcf1aT303wAQhv66qzW"
)

POWER_STATUS = {
    0: "not_powering",
    1: "starting",
    2: "powering",
    3: "overload",
    4: "short_circuit",
    5: "non_standard_pd",
    6: "voltage_high",
    7: "voltage_low",
    8: "hardware_error",
    9: "over_temperature",
}


class MercuryError(RuntimeError):
    pass


@dataclass(frozen=True)
class PoeSnapshot:
    model: str
    system_total_w: float
    system_used_w: float
    system_remaining_w: float
    system_usage_percent: float
    ports: list[dict[str, Any]]


def security_encode(value: str) -> str:
    output: list[str] = []
    length = max(len(value), len(PASSWORD_KEY))
    for index in range(length):
        left = 187
        right = 187
        if index >= len(value):
            right = ord(PASSWORD_KEY[index])
        elif index >= len(PASSWORD_KEY):
            left = ord(value[index])
        else:
            left = ord(value[index])
            right = ord(PASSWORD_KEY[index])
        output.append(PASSWORD_DICTIONARY[(left ^ right) % len(PASSWORD_DICTIONARY)])
    return "".join(output)


def _object_block(html: str, variable: str) -> str:
    match = re.search(
        rf"var\s+{re.escape(variable)}\s*=\s*\{{(.*?)\}}\s*;", html, re.DOTALL
    )
    if not match:
        raise MercuryError(f"Missing {variable} data in switch response")
    return match.group(1)


def _integer(block: str, key: str) -> int:
    match = re.search(rf"\b{re.escape(key)}\s*:\s*(-?\d+)", block)
    if not match:
        raise MercuryError(f"Missing {key} in switch response")
    return int(match.group(1))


def _array(block: str, key: str) -> list[int]:
    match = re.search(rf"\b{re.escape(key)}\s*:\s*\[([^]]*)\]", block, re.DOTALL)
    if not match:
        raise MercuryError(f"Missing {key} in switch response")
    values = [item.strip() for item in match.group(1).split(",") if item.strip()]
    try:
        return [int(item) for item in values]
    except ValueError as exc:
        raise MercuryError(f"Invalid {key} array in switch response") from exc


def parse_poe_page(html: str, model: str = "SE109P Pro") -> PoeSnapshot:
    count_match = re.search(r"var\s+poe_port_num\s*=\s*(\d+)", html)
    if not count_match:
        raise MercuryError(
            "PoE page did not contain a port count; authentication may have expired"
        )
    port_count = int(count_match.group(1))
    global_block = _object_block(html, "globalConfig")
    port_block = _object_block(html, "portConfig")

    total = _integer(global_block, "system_power_limit") / 10
    used = _integer(global_block, "system_power_consumption") / 10
    remaining = _integer(global_block, "system_power_remain") / 10
    arrays = {
        key: _array(port_block, key)
        for key in (
            "state",
            "fastpoe",
            "pptlpoe",
            "priority",
            "powerlimit",
            "power",
            "current",
            "voltage",
            "pdclass",
            "powerstatus",
        )
    }
    for key, values in arrays.items():
        if len(values) != port_count:
            raise MercuryError(
                f"Expected {port_count} {key} values, received {len(values)}"
            )

    priority_names = {0: "high", 1: "medium", 2: "low"}
    ports: list[dict[str, Any]] = []
    for index in range(port_count):
        status_code = arrays["powerstatus"][index]
        pd_class = arrays["pdclass"][index]
        ports.append(
            {
                "port": index + 1,
                "enabled": bool(arrays["state"][index]),
                "fast_poe": bool(arrays["fastpoe"][index]),
                "permanent_poe": bool(arrays["pptlpoe"][index]),
                "priority": priority_names.get(arrays["priority"][index], "unknown"),
                "max_power_w": arrays["powerlimit"][index] / 10,
                "power_w": arrays["power"][index] / 10,
                "current_ma": arrays["current"][index],
                "voltage_v": arrays["voltage"][index] / 10,
                "pd_class": f"Class {pd_class}" if 0 <= pd_class <= 4 else "unknown",
                "power_status": POWER_STATUS.get(status_code, "unknown"),
            }
        )
    return PoeSnapshot(
        model=model,
        system_total_w=total,
        system_used_w=used,
        system_remaining_w=remaining,
        system_usage_percent=round(used / total * 100, 1) if total else 0.0,
        ports=ports,
    )


class MercurySwitch:
    def __init__(
        self, base_url: str, username: str, password: str, timeout: int = 10
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.username = username
        self.password = password
        self.timeout = timeout
        self.cookies = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self.cookies)
        )
        self.token: str | None = None
        self.model = "Mercury PoE Switch"

    def _request(self, path: str, data: dict[str, str] | None = None) -> str:
        encoded = (
            urllib.parse.urlencode(data).encode("utf-8") if data is not None else None
        )
        request = urllib.request.Request(
            f"{self.base_url}/{path.lstrip('/')}",
            data=encoded,
            headers={"User-Agent": "HomeAssistant-Mercury-PoE-MQTT/0.1"},
        )
        try:
            with self.opener.open(request, timeout=self.timeout) as response:
                return response.read().decode("utf-8", errors="replace")
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise MercuryError(
                f"Unable to reach switch at {self.base_url}: {exc}"
            ) from exc

    def login(self) -> None:
        response = self._request(
            "/logon.cgi",
            {
                "username": self.username,
                "password": security_encode(self.password),
                "isIe": "false",
                "logon": "Login",
            },
        )
        status = re.search(r"var\s+logonInfo\s*=\s*new\s+Array\(\s*(\d+)", response)
        if status and int(status.group(1)) != 0:
            raise MercuryError(f"Switch rejected the login (error {status.group(1)})")

        home = self._request("/")
        token = re.search(r"\bg_tid\s*=\s*(\d+)", home)
        if not token:
            raise MercuryError("Login did not return a management token")
        self.token = token.group(1)
        model = re.search(r"\bg_title\s*=\s*['\"]([^'\"]+)", home)
        if model:
            self.model = model.group(1).strip()

    def poll(self) -> PoeSnapshot:
        if self.token is None:
            self.login()
        page = self._request("/PoeConfigRpm.htm")
        try:
            return parse_poe_page(page, self.model)
        except MercuryError:
            self.token = None
            self.login()
            return parse_poe_page(self._request("/PoeConfigRpm.htm"), self.model)

    def reboot_port(self, port: int) -> None:
        snapshot = self.poll()
        if not 1 <= port <= len(snapshot.ports):
            raise MercuryError(
                f"Port {port} is outside the valid range 1-{len(snapshot.ports)}"
            )
        if not snapshot.ports[port - 1]["enabled"]:
            raise MercuryError(f"Port {port} is disabled and cannot be rebooted")
        if self.token is None:
            raise MercuryError("No management token is available")
        response = self._request(
            "/poe_port_config.cgi",
            {
                "name_pstate": "7",
                "name_fastpstate": "7",
                "name_pptlpstate": "7",
                "name_ppriority": "7",
                "name_ppowerlimit": "7",
                "name_ppowerlimit2": "",
                f"reset_{port}": "重新上电",
                "token": self.token,
            },
        )
        if "logonInfo" in response:
            self.token = None
            raise MercuryError(
                "Switch session expired while rebooting the port; retry the command"
            )
