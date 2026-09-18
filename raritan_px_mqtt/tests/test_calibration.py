import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'app'))

from models import SENSOR_SPECS, SensorBinding
from raritan_device import RaritanDevice


class CalibrationTests(unittest.TestCase):
    def poll(self, real=False, offset=False, value=291, valid=True, available=True):
        device = RaritanDevice(
            'test', 'user', 'pass', 'https', False, 10, 'raritan2mqtt',
            inlet_real_power_calibration=real,
            inlet_fixed_offset_calibration=offset,
        )
        fields = [('inlet', 'activePower'), ('outlet', 'activePower'),
                  ('inlet', 'activeEnergy'), ('inlet', 'apparentPower')]
        device.sensors = [
            SensorBinding(scope, 0, attr, Mock(), SENSOR_SPECS[attr], scope, attr)
            for scope, attr in fields
        ]
        reading = SimpleNamespace(value=value, valid=valid, available=available)
        with patch('raritan_device.rpc_bulk', return_value=[reading] * len(fields)):
            return device.poll()

    def test_all_switch_combinations_and_scope(self):
        for real, offset, expected in [(False, False, 291), (True, False, 293.9),
                                       (False, True, 297.4), (True, True, 300.3)]:
            with self.subTest(real=real, offset=offset):
                payload = self.poll(real, offset)
                self.assertEqual(payload['inlet']['activePower'], expected)
                self.assertEqual(payload['outlet']['activePower'], 291)
                self.assertEqual(payload['inlet']['activeEnergy'], 291)
                self.assertEqual(payload['inlet']['apparentPower'], 291)

    def test_invalid_readings_do_not_become_offset(self):
        for kwargs in [dict(valid=False), dict(available=False), dict(value=None),
                       dict(value='invalid')]:
            with self.subTest(**kwargs):
                self.assertIsNone(self.poll(True, True, **kwargs)['inlet']['activePower'])

    def test_zero_load_includes_device_consumption(self):
        self.assertEqual(self.poll(True, True, value=0)['inlet']['activePower'], round(6.35, 1))


if __name__ == '__main__':
    unittest.main()
