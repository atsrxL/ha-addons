# DeepSeek Ollama Proxy

This Add-on translates Home Assistant's Ollama requests to DeepSeek's
OpenAI-compatible Chat Completions API. It is based on the proxy that was
previously validated as a macOS LaunchAgent for Home Assistant Assist.

## Configuration

Before starting the Add-on, open **Configuration** and set:

- `deepseek_api_key`: your DeepSeek API key. The UI masks this field.
- `deepseek_base_url`: normally `https://api.deepseek.com`.
- `models`: comma-separated model names exposed to Home Assistant. The default
  is `deepseek-v4-flash,deepseek-v4-pro`.
- `timeout`: upstream request timeout in seconds.
- `log_level`: log verbosity. API keys are never written to logs.

DeepSeek thinking mode is intentionally disabled. Home Assistant's Ollama tool
loop does not retain DeepSeek's `reasoning_content`; disabling thinking keeps
multi-step tool calls compatible and avoids a DeepSeek 400 response.

## Connect Home Assistant

1. Start the Add-on and check its log for `Starting DeepSeek Ollama proxy`.
2. Go to **Settings > Devices & services > Add integration**.
3. Add **Ollama**.
4. Use `http://HOME_ASSISTANT_IP:11435` as the URL.
5. Choose `deepseek-v4-flash` or `deepseek-v4-pro`.
6. Select that conversation agent in the Assist pipeline.

The URL must include `http://`. If port `11435` is already in use, change the
host-side port on the Add-on's **Network** page and use that port in the URL.

## Compatibility behavior

- Implements `/api/version`, `/api/tags`, `/api/show`, `/api/chat`, and
  `/api/generate`.
- Converts Ollama tool arguments to DeepSeek/OpenAI format.
- Converts DeepSeek tool calls back to the object format expected by HA.
- Converts structured HA tool results into text for the follow-up turn.
- Returns streaming requests as one complete NDJSON record so tool calls arrive
  atomically.
- Removes over-specific, likely invented Chinese sensor names from
  `GetLiveContext` while retaining its domain filter.
- Maps legacy `deepseek-chat` and `deepseek-reasoner` requests to current V4
  model names.

## Security

The API key remains in Home Assistant's Add-on configuration and is only sent
to the configured DeepSeek endpoint. The proxy port has no additional
authentication, so keep Home Assistant on a trusted LAN and do not expose port
`11435` to the internet.
