import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "firmware"))
from motion_effects import MotionEffects
from qmi8658 import QMI8658


class FakeI2C:
    def __init__(self, sample):
        self.sample = sample
        self.writes = []

    def readfrom_mem(self, address, register, count):
        if address != 0x6B:
            raise OSError("missing sensor")
        if register == 0x00:
            return b"\x05"
        if register == 0xB5:
            return self.sample
        raise AssertionError((address, register, count))

    def writeto_mem(self, address, register, data):
        self.writes.append((address, register, data[0]))


class TestMotionEffects(unittest.TestCase):
    def test_qmi8658_reads_signed_and_scaled_axes(self):
        # +1g, -0.5g, 0g; +64dps, -32dps, 0dps.
        sample = (16384).to_bytes(2, "little", signed=True) + (-8192).to_bytes(2, "little", signed=True)
        sample += (0).to_bytes(2, "little", signed=True)
        sample += (8192).to_bytes(2, "little", signed=True) + (-4096).to_bytes(2, "little", signed=True)
        sample += (0).to_bytes(2, "little", signed=True)
        i2c = FakeI2C(sample)
        imu = QMI8658(i2c)
        accel, gyro = imu.read()
        self.assertEqual(accel, (1.0, -0.5, 0.0))
        self.assertEqual(gyro, (64.0, -32.0, 0.0))
        self.assertEqual(i2c.writes[-1], (0x6B, 0x08, 0x03))
        imu.standby()
        self.assertEqual(i2c.writes[-1], (0x6B, 0x08, 0x00))

    def test_tilt_is_smoothed_and_bounded(self):
        effects = MotionEffects()
        for n in range(20):
            snapshot = effects.observe((0.7, -0.7, 0.3), (0, 0, 0), n * 80)
        self.assertGreater(snapshot["tilt_x"], 0.5)
        self.assertLess(snapshot["tilt_y"], -0.5)
        self.assertLessEqual(abs(snapshot["tilt_x"]), 1.0)
        self.assertTrue(snapshot["connected"])

    def test_shake_off_by_default(self):
        effects = MotionEffects()
        self.assertEqual(effects.observe((3, 0, 0), (300, 300, 300), 100)["shake_id"], 0)

    def test_shake_cooldown(self):
        effects = MotionEffects(shake_enabled=True)
        self.assertEqual(effects.observe((3, 0, 0), (0, 0, 0), 100)["shake_id"], 1)
        self.assertEqual(effects.observe((3, 0, 0), (0, 0, 0), 200)["shake_id"], 1)
        self.assertEqual(effects.observe((3, 0, 0), (0, 0, 0), 15200)["shake_id"], 2)


if __name__ == "__main__":
    unittest.main()
