"""MicroPython display unit tests with fake SPI/I2C, no attached board."""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "firmware"))
from round_screen import (BatteryGauge, CST816Touch, FRAME_SIZE, GC9A01,
                          RoundScreen, blend_row)


class Pin:
    OUT = 1

    def __init__(self, number, mode=None, value=0):
        self.number = number
        self.state = value

    def value(self, new=None):
        if new is not None:
            self.state = new
        return self.state


class SPI:
    def __init__(self, ident, **kw):
        self.ident = ident
        self.kw = kw
        self.writes = []

    def write(self, data):
        self.writes.append(bytes(data))


class PWM:
    def __init__(self, pin, freq, duty_u16):
        self.duty = duty_u16

    def duty_u16(self, value):
        self.duty = value


class ADC:
    ATTN_11DB = 3

    def __init__(self, pin):
        self.pin = pin

    def atten(self, attenuation):
        self.attenuation = attenuation

    def read_uv(self):
        return 1_160_000


class Machine:
    Pin = Pin
    SPI = SPI
    PWM = PWM
    ADC = ADC


class I2C:
    def __init__(self):
        self.value = b"\x01\x00\x64\x00\x78"

    def scan(self):
        return [0x15, 0x6b]

    def readfrom_mem(self, addr, register, size):
        assert (addr, register, size) == (0x15, 0x02, 5)
        return self.value


class Display:
    def __init__(self):
        self.rows = 0
        self.pixels = 0
        self.calls = []

    def window(self, *args):
        self.calls.append(("window", args))

    def start_pixels(self):
        pass

    def write_pixels(self, chunk):
        self.rows += 1
        self.pixels += len(chunk)

    def stop_pixels(self):
        pass

    def solid(self, *args):
        self.calls.append(("solid", args))


class RoundScreenTest(unittest.TestCase):
    def test_alpha_and_validation(self):
        red, green = b"\xf8\x00", b"\x07\xe0"
        self.assertEqual(blend_row(red, green, 0), red)
        self.assertEqual(blend_row(red, green, 255), green)
        self.assertNotEqual(blend_row(red, green, 127), red)
        self.assertNotEqual(blend_row(red, green, 127), green)
        with self.assertRaises(ValueError):
            blend_row(b"\xff", b"\xff", 127)

    def test_spi_pin_mapping(self):
        lcd = GC9A01(Machine, lambda _: None)
        self.assertEqual(lcd.spi.kw["sck"].number, 10)
        self.assertEqual(lcd.spi.kw["mosi"].number, 11)
        self.assertEqual(lcd.cs.number, 9)
        self.assertEqual(lcd.dc.number, 8)
        self.assertEqual(lcd.reset.number, 14)
        self.assertEqual(lcd.backlight.number, 2)
        lcd.window(0, 0, 240, 240)
        self.assertEqual(lcd.spi.writes[-1], b"\x2c")
        lcd.solid(20, 20, 3, 2, 0xf800)
        self.assertIn(b"\xf8\x00" * 3, lcd.spi.writes)

    def test_touch_single_press_only(self):
        bus = I2C()
        touch = CST816Touch(bus)
        self.assertEqual(touch.tapped(), (100, 120))
        self.assertIsNone(touch.tapped())
        bus.value = b"\x00\x00\x00\x00\x00"
        self.assertIsNone(touch.tapped())
        bus.value = b"\x01\x00\x40\x00\x50"
        self.assertEqual(touch.tapped(), (64, 80))

    def test_battery_divider_not_fake_charging(self):
        status = BatteryGauge(Machine).status()
        self.assertAlmostEqual(status["voltage"], 3.48)
        self.assertTrue(status["low"])
        self.assertIsNone(status["charging"])

    def test_streamed_artwork_and_low_battery_overlay(self):
        previous = os.getcwd()
        with tempfile.TemporaryDirectory() as directory:
            try:
                os.chdir(directory)
                os.mkdir("assets")
                with open("assets/city-young.dat", "wb") as f:
                    f.write(b"\xf8\x00" * (FRAME_SIZE // 2))
                with open("assets/city-mature.dat", "wb") as f:
                    f.write(b"\x07\xe0" * (FRAME_SIZE // 2))
                device = Display()
                screen = RoundScreen(device, battery=BatteryGauge(Machine))
                screen.choose("city")
                self.assertTrue(screen.show(1440 * 15))
                self.assertEqual(device.rows, 240)
                self.assertEqual(device.pixels, FRAME_SIZE)
                self.assertEqual(screen.status()["selected"], "city")
                self.assertTrue(any(x[0] == "solid" for x in device.calls))
                self.assertEqual(screen.next_world(), "hybrid")
                with self.assertRaises(ValueError):
                    screen.choose("../main.py")
                self.assertFalse(screen.show(0))
                for stage in ("young", "mature"):
                    with open("assets/river-" + stage + ".dat", "wb") as f:
                        f.write(b"\x04\x00" * (FRAME_SIZE // 2))
                screen.choose("aquarium")
                screen.choose_water_area("river")
                self.assertTrue(screen.show(0))
                self.assertEqual(screen.status()["water_area"], "river")
                screen.choose_water_area("deepsea")
                self.assertFalse(screen.show(0))
                with self.assertRaises(ValueError):
                    screen.choose_water_area("ocean/../../settings")
            finally:
                os.chdir(previous)


if __name__ == "__main__":
    unittest.main()
