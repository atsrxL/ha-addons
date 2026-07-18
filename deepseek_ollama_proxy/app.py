#!/usr/bin/env python3

"""Expose the DeepSeek Chat Completions API as an Ollama-compatible API."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from aiohttp import ClientError, ClientSession, ClientTimeout, web


LOGGER = logging.getLogger("deepseek_ollama_proxy")
OPTIONS_PATH = Path("/data/options.json")
DEFAULT_MODEL = "deepseek-v4-flash"
LEGACY_MODEL_MAP = {
    "deepseek-chat": "deepseek-v4-flash",
    "deepseek-reasoner": "deepseek-v4-pro",
}


def load_addon_options(path: Path = OPTIONS_PATH) -> None:
    """Load Home Assistant Add-on options into the process environment."""
    if not path.exists():
        LOGGER.warning(
            "Options file %s does not exist; using environment variables", path
        )
        return

    options = json.loads(path.read_text(encoding="utf-8"))
    option_map = {
        "deepseek_api_key": "DEEPSEEK_API_KEY",
        "deepseek_base_url": "DEEPSEEK_BASE_URL",
        "models": "OLLAMA_MODELS",
        "timeout": "DEEPSEEK_TIMEOUT",
        "log_level": "LOG_LEVEL",
    }
    for option, environment in option_map.items():
        value = options.get(option)
        if value is not None:
            os.environ[environment] = str(value)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def deepseek_base_url() -> str:
    return os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com").rstrip("/")


def api_key() -> str | None:
    return os.environ.get("DEEPSEEK_API_KEY")


def advertised_models() -> list[str]:
    raw_models = os.environ.get("OLLAMA_MODELS", "deepseek-v4-flash,deepseek-v4-pro")
    models = [model.strip() for model in raw_models.split(",") if model.strip()]
    return models or [DEFAULT_MODEL]


def model_to_deepseek(model: str | None) -> str:
    if not model:
        return DEFAULT_MODEL
    if model in advertised_models():
        return model
    return LEGACY_MODEL_MAP.get(model, DEFAULT_MODEL)


def ollama_model_info(name: str) -> dict[str, Any]:
    return {
        "name": name,
        "model": name,
        "modified_at": "2026-01-01T00:00:00Z",
        "size": 0,
        "digest": f"deepseek-proxy-{name}",
        "details": {
            "parent_model": "",
            "format": "api",
            "family": "deepseek",
            "families": ["deepseek"],
            "parameter_size": "api",
            "quantization_level": "api",
        },
    }


def normalize_content(content: Any) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        text_parts: list[str] = []
        for item in content:
            if isinstance(item, dict):
                if item.get("type") == "text" and isinstance(item.get("text"), str):
                    text_parts.append(item["text"])
                elif isinstance(item.get("content"), str):
                    text_parts.append(item["content"])
                else:
                    text_parts.append(json.dumps(item, ensure_ascii=False))
            else:
                text_parts.append(str(item))
        return "\n".join(part for part in text_parts if part)
    return json.dumps(content, ensure_ascii=False)


def has_tool_result(messages: list[dict[str, Any]]) -> bool:
    return any(message.get("role") in {"tool", "tool_result"} for message in messages)


def convert_ollama_tool_calls_for_deepseek(
    tool_calls: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    converted: list[dict[str, Any]] = []
    for index, tool_call in enumerate(tool_calls):
        function = tool_call.get("function") or {}
        arguments = function.get("arguments", {})
        if not isinstance(arguments, str):
            arguments = json.dumps(arguments or {}, ensure_ascii=False)
        converted.append(
            {
                "id": tool_call.get("id") or f"call_{index}",
                "type": tool_call.get("type") or "function",
                "function": {
                    "name": function.get("name", ""),
                    "arguments": arguments,
                },
            }
        )
    return converted


def convert_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Convert Ollama/HA history to DeepSeek's stricter OpenAI format."""
    converted: list[dict[str, Any]] = []
    tool_result_present = has_tool_result(messages)
    for message in messages:
        role = message.get("role", "user")
        content = normalize_content(message.get("content", ""))

        if role in {"tool", "tool_result"}:
            tool_name = message.get("name") or message.get("tool_name") or "tool"
            if message.get("tool_result") is not None:
                content = normalize_content(message["tool_result"])
            converted.append(
                {
                    "role": "user",
                    "content": f"Home Assistant tool result from {tool_name}: {content}",
                }
            )
            continue

        output: dict[str, Any] = {"role": role, "content": content}
        # HA does not preserve DeepSeek reasoning_content. Once a tool result is
        # present, flatten the earlier tool-call turn and let DeepSeek produce
        # the final answer from the textual tool result.
        if message.get("tool_calls") and not tool_result_present:
            output["tool_calls"] = convert_ollama_tool_calls_for_deepseek(
                message["tool_calls"]
            )
        if message.get("tool_call_id"):
            output["tool_call_id"] = message["tool_call_id"]
        converted.append(output)
    return converted


def looks_like_invented_sensor_name(name: str) -> bool:
    keywords = ("温度", "湿度", "温湿度", "传感器", "室外", "户外")
    return any(keyword in name for keyword in keywords)


def sanitize_ha_tool_arguments(function_name: str, arguments: Any) -> Any:
    if function_name != "GetLiveContext" or not isinstance(arguments, dict):
        return arguments
    name = arguments.get("name")
    if isinstance(name, str) and looks_like_invented_sensor_name(name):
        LOGGER.info("Removing over-specific GetLiveContext name filter: %s", name)
        return {key: value for key, value in arguments.items() if key != "name"}
    return arguments


def convert_deepseek_tool_calls(
    tool_calls: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    converted: list[dict[str, Any]] = []
    for tool_call in tool_calls:
        function = tool_call.get("function") or {}
        function_name = function.get("name", "")
        arguments = function.get("arguments") or {}
        if isinstance(arguments, str):
            try:
                arguments = json.loads(arguments) if arguments else {}
            except json.JSONDecodeError:
                arguments = {"_raw": arguments}
        arguments = sanitize_ha_tool_arguments(function_name, arguments)
        converted.append({"function": {"name": function_name, "arguments": arguments}})
    return converted


def convert_deepseek_message(message: dict[str, Any]) -> dict[str, Any]:
    output: dict[str, Any] = {
        "role": message.get("role", "assistant"),
        "content": message.get("content") or "",
    }
    if message.get("tool_calls"):
        output["tool_calls"] = convert_deepseek_tool_calls(message["tool_calls"])
    return output


def convert_options(options: dict[str, Any] | None) -> dict[str, Any]:
    if not options:
        return {}
    converted: dict[str, Any] = {}
    for source, target in {
        "temperature": "temperature",
        "top_p": "top_p",
        "seed": "seed",
        "num_predict": "max_tokens",
    }.items():
        if options.get(source) is not None:
            converted[target] = options[source]
    return converted


def deepseek_payload(data: dict[str, Any]) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "model": model_to_deepseek(data.get("model")),
        "messages": convert_messages(data.get("messages") or []),
        "stream": False,
        # DeepSeek defaults to thinking mode. HA's Ollama tool loop does not
        # retain reasoning_content, so thinking must stay disabled here.
        "thinking": {"type": "disabled"},
    }
    payload.update(convert_options(data.get("options")))
    for key in (
        "temperature",
        "top_p",
        "max_tokens",
        "frequency_penalty",
        "presence_penalty",
    ):
        if data.get(key) is not None:
            payload[key] = data[key]
    if data.get("tools"):
        payload["tools"] = data["tools"]
    if data.get("tool_choice"):
        payload["tool_choice"] = data["tool_choice"]
    return payload


def ollama_response(
    payload: dict[str, Any], data: dict[str, Any], started: int
) -> dict[str, Any]:
    choice = (data.get("choices") or [{}])[0]
    return {
        "model": payload["model"],
        "created_at": utc_now(),
        "message": convert_deepseek_message(choice.get("message") or {}),
        "done": True,
        "done_reason": choice.get("finish_reason", "stop"),
        "total_duration": time.monotonic_ns() - started,
        "load_duration": 0,
        "prompt_eval_count": (data.get("usage") or {}).get("prompt_tokens", 0),
        "eval_count": (data.get("usage") or {}).get("completion_tokens", 0),
    }


async def call_deepseek(payload: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    started = time.monotonic_ns()
    key = api_key()
    if not key:
        return 500, {"error": "DeepSeek API key is not configured"}

    try:
        timeout = ClientTimeout(total=float(os.environ.get("DEEPSEEK_TIMEOUT", "90")))
        async with ClientSession(timeout=timeout) as session:
            async with session.post(
                f"{deepseek_base_url()}/chat/completions",
                headers={
                    "Authorization": f"Bearer {key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            ) as response:
                body = await response.text()
                try:
                    data = json.loads(body)
                except json.JSONDecodeError:
                    LOGGER.warning(
                        "DeepSeek returned non-JSON response: %s", body[:500]
                    )
                    return 502, {"error": "DeepSeek returned an invalid response"}
                if response.status >= 400:
                    LOGGER.warning(
                        "DeepSeek error %s: %s", response.status, body[:1000]
                    )
                    return response.status, data
                return 200, ollama_response(payload, data, started)
    except asyncio.TimeoutError:
        LOGGER.warning("DeepSeek request timed out")
        return 504, {"error": "DeepSeek request timed out"}
    except ClientError as err:
        LOGGER.warning("DeepSeek connection failed: %s", err)
        return 502, {"error": "Unable to connect to DeepSeek"}


async def read_json(request: web.Request) -> dict[str, Any]:
    try:
        data = await request.json()
    except (json.JSONDecodeError, web.HTTPBadRequest) as err:
        raise web.HTTPBadRequest(
            text=json.dumps({"error": "Invalid JSON"}), content_type="application/json"
        ) from err
    if not isinstance(data, dict):
        raise web.HTTPBadRequest(
            text=json.dumps({"error": "JSON object required"}),
            content_type="application/json",
        )
    return data


async def api_version(_: web.Request) -> web.Response:
    return web.json_response({"version": "0.24.0-deepseek-proxy"})


async def api_tags(_: web.Request) -> web.Response:
    return web.json_response(
        {"models": [ollama_model_info(model) for model in advertised_models()]}
    )


async def api_show(request: web.Request) -> web.Response:
    data = await read_json(request)
    model = data.get("model") or DEFAULT_MODEL
    return web.json_response(
        {
            **ollama_model_info(model),
            "license": "DeepSeek API",
            "modelfile": f"FROM {model}",
            "parameters": "",
            "template": "{{ .Prompt }}",
            "system": "",
        }
    )


async def api_chat(request: web.Request) -> web.StreamResponse:
    data = await read_json(request)
    wants_stream = bool(data.get("stream", False))
    status, body = await call_deepseek(deepseek_payload(data))
    if not wants_stream:
        return web.json_response(body, status=status)

    # HA asks Ollama for NDJSON streaming. A single complete NDJSON record is
    # intentional: tool calls must arrive atomically for reliable HA parsing.
    response = web.StreamResponse(
        status=200, headers={"Content-Type": "application/x-ndjson"}
    )
    await response.prepare(request)
    if status != 200:
        body = {"error": json.dumps(body, ensure_ascii=False), "done": True}
    try:
        await response.write(json.dumps(body, ensure_ascii=False).encode() + b"\n")
        await response.write_eof()
    except ConnectionResetError:
        LOGGER.info("Client closed streaming response early")
    return response


async def api_generate(request: web.Request) -> web.Response:
    data = await read_json(request)
    chat_data = {
        **data,
        "messages": [{"role": "user", "content": data.get("prompt", "")}],
    }
    status, body = await call_deepseek(deepseek_payload(chat_data))
    if status != 200:
        return web.json_response(body, status=status)
    return web.json_response(
        {
            "model": body.get("model", DEFAULT_MODEL),
            "created_at": utc_now(),
            "response": (body.get("message") or {}).get("content", ""),
            "done": True,
            "done_reason": body.get("done_reason", "stop"),
        }
    )


async def health(_: web.Request) -> web.Response:
    return web.json_response(
        {
            "ok": True,
            "api_key_configured": bool(api_key()),
            "base_url": deepseek_base_url(),
            "models": advertised_models(),
        }
    )


def make_app() -> web.Application:
    app = web.Application(client_max_size=2 * 1024 * 1024)
    app.router.add_get("/", health)
    app.router.add_get("/api/version", api_version)
    app.router.add_get("/api/tags", api_tags)
    app.router.add_post("/api/show", api_show)
    app.router.add_post("/api/chat", api_chat)
    app.router.add_post("/api/generate", api_generate)
    return app


def main() -> None:
    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    load_addon_options()
    logging.getLogger().setLevel(os.environ.get("LOG_LEVEL", "INFO"))
    LOGGER.info("Starting DeepSeek Ollama proxy on 0.0.0.0:11435")
    LOGGER.info("DeepSeek base URL: %s", deepseek_base_url())
    LOGGER.info("Advertised models: %s", ", ".join(advertised_models()))
    web.run_app(make_app(), host="0.0.0.0", port=11435)


if __name__ == "__main__":
    main()
