from __future__ import annotations

import importlib
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
mercury = importlib.import_module("mercury")
MercuryError = mercury.MercuryError
parse_poe_page = mercury.parse_poe_page
security_encode = mercury.security_encode


SAMPLE = """
<script>
var poe_port_num = 3;
var globalConfig = {
system_power_limit:1160,
system_power_consumption:271,
system_power_remain:889
};
var portConfig ={
state:[1,1,0],
fastpoe:[1,1,1],
pptlpoe:[1,1,1],
priority:[2,1,0],
powerlimit:[300,154,40],
power:[215,45,0],
current:[406,86,0],
voltage:[530,531,0],
pdclass:[4,3,5],
powerstatus:[2,1,0]
};
</script>
"""


class MercuryParserTests(unittest.TestCase):
    def test_password_encoding_matches_switch_javascript(self) -> None:
        self.assertEqual(security_encode("admin"), "WaQ7xbhc9TefbwK")

    def test_parse_live_shape_and_units(self) -> None:
        snapshot = parse_poe_page(SAMPLE, "SE109P Pro")
        self.assertEqual(snapshot.system_total_w, 116.0)
        self.assertEqual(snapshot.system_used_w, 27.1)
        self.assertEqual(snapshot.system_remaining_w, 88.9)
        self.assertEqual(snapshot.system_usage_percent, 23.4)
        self.assertEqual(len(snapshot.ports), 3)
        self.assertEqual(snapshot.ports[0]["power_w"], 21.5)
        self.assertEqual(snapshot.ports[0]["voltage_v"], 53.0)
        self.assertEqual(snapshot.ports[0]["power_status"], "powering")
        self.assertEqual(snapshot.ports[1]["max_power_w"], 15.4)
        self.assertEqual(snapshot.ports[2]["pd_class"], "unknown")
        self.assertFalse(snapshot.ports[2]["enabled"])

    def test_rejects_incomplete_port_arrays(self) -> None:
        with self.assertRaisesRegex(MercuryError, "Expected 3 power values"):
            parse_poe_page(SAMPLE.replace("power:[215,45,0]", "power:[215,45]"))


if __name__ == "__main__":
    unittest.main()
