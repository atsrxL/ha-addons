#!/usr/bin/env python3

import json

from aiohttp import web


async def chat(request: web.Request) -> web.Response:
    data = await request.json()
    if data.get("tools"):
        message = {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "id": "call_test",
                    "type": "function",
                    "function": {
                        "name": "GetLiveContext",
                        "arguments": json.dumps(
                            {
                                "domain": ["sensor"],
                                "name": "LYB1室外温度传感器",
                            },
                            ensure_ascii=False,
                        ),
                    },
                }
            ],
        }
        finish_reason = "tool_calls"
    else:
        thinking = (data.get("thinking") or {}).get("type")
        message = {
            "role": "assistant",
            "content": f"mock-ok:{thinking}:{data.get('model')}",
        }
        finish_reason = "stop"
    return web.json_response(
        {
            "choices": [{"message": message, "finish_reason": finish_reason}],
            "usage": {"prompt_tokens": 5, "completion_tokens": 3},
        }
    )


app = web.Application()
app.router.add_post("/chat/completions", chat)
web.run_app(app, host="0.0.0.0", port=18080)
