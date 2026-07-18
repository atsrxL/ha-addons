import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path


APP_PATH = Path(__file__).parents[1] / "app.py"
SPEC = importlib.util.spec_from_file_location("deepseek_proxy", APP_PATH)
proxy = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(proxy)


class ProxyConversionTests(unittest.TestCase):
    def setUp(self):
        self.original_environment = os.environ.copy()

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self.original_environment)

    def test_addon_options_are_loaded(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "options.json"
            path.write_text(
                json.dumps(
                    {
                        "deepseek_api_key": "test-token",
                        "deepseek_base_url": "https://example.test/",
                        "models": "deepseek-v4-pro",
                        "timeout": 45,
                        "log_level": "DEBUG",
                    }
                ),
                encoding="utf-8",
            )
            proxy.load_addon_options(path)

        self.assertEqual(proxy.api_key(), "test-token")
        self.assertEqual(proxy.deepseek_base_url(), "https://example.test")
        self.assertEqual(proxy.advertised_models(), ["deepseek-v4-pro"])
        self.assertEqual(os.environ["DEEPSEEK_TIMEOUT"], "45")

    def test_legacy_models_map_to_current_v4_names(self):
        self.assertEqual(proxy.model_to_deepseek("deepseek-chat"), "deepseek-v4-flash")
        self.assertEqual(
            proxy.model_to_deepseek("deepseek-reasoner"), "deepseek-v4-pro"
        )

    def test_tool_results_become_plain_text_context(self):
        messages = [
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "function": {
                            "name": "GetLiveContext",
                            "arguments": {"domain": ["sensor"]},
                        }
                    }
                ],
            },
            {
                "role": "tool_result",
                "tool_name": "GetLiveContext",
                "tool_result": {"temperature": 23.5},
            },
        ]

        converted = proxy.convert_messages(messages)
        self.assertNotIn("tool_calls", converted[0])
        self.assertEqual(converted[1]["role"], "user")
        self.assertIn('"temperature": 23.5', converted[1]["content"])

    def test_deepseek_tool_call_becomes_ollama_object(self):
        calls = proxy.convert_deepseek_tool_calls(
            [
                {
                    "function": {
                        "name": "TurnOn",
                        "arguments": '{"name": "客厅灯"}',
                    }
                }
            ]
        )
        self.assertEqual(calls[0]["function"]["arguments"], {"name": "客厅灯"})

    def test_over_specific_sensor_name_is_removed(self):
        calls = proxy.convert_deepseek_tool_calls(
            [
                {
                    "function": {
                        "name": "GetLiveContext",
                        "arguments": json.dumps(
                            {"domain": ["sensor"], "name": "LYB1室外温度传感器"},
                            ensure_ascii=False,
                        ),
                    }
                }
            ]
        )
        self.assertEqual(calls[0]["function"]["arguments"], {"domain": ["sensor"]})

    def test_payload_always_disables_thinking(self):
        payload = proxy.deepseek_payload(
            {
                "model": "deepseek-v4-flash",
                "messages": [{"role": "user", "content": "你好"}],
            }
        )
        self.assertEqual(payload["thinking"], {"type": "disabled"})
        self.assertFalse(payload["stream"])


if __name__ == "__main__":
    unittest.main()
