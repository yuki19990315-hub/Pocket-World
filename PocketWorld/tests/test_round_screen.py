"""MicroPython display unit tests with fake SPI/I2C, no attached board."""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "firmware"))
from round_screen import (BatteryGauge, CST816Touch, FRAME_SIZE, GC9A01,
                          RoundScreen, ambience_row, blend_row, hybrid_art_frames,
                          hybrid_ambient_particles, hybrid_people,
                          nature_ambient_particles, water_ambient_particles,
                          town_art_alpha, town_people)


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
        self.value = b"\x00\x01\x00\x64\x00\x78"
        self.writes = []

    def scan(self):
        return [0x15, 0x6b]

    def writeto_mem(self, address, register, data):
        self.writes.append((address, register, data))

    def readfrom_mem(self, addr, register, size):
        assert (addr, register, size) == (0x15, 0x01, 6)
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

    def set_brightness(self, percent):
        self.calls.append(("brightness", percent))


class RoundScreenTest(unittest.TestCase):
    def test_day_tints_rgb565_and_city_lamps_appear_only_at_night(self):
        white=b"\xff\xff"
        self.assertEqual(ambience_row(white,"day"),white)
        self.assertNotEqual(ambience_row(white,"dawn"),white)
        self.assertNotEqual(ambience_row(white,"dusk"),white)
        self.assertNotEqual(ambience_row(white,"night"),white)
        self.assertNotEqual(ambience_row(white,"lights_out"),white)
        previous=os.getcwd()
        with tempfile.TemporaryDirectory() as directory:
            try:
                os.chdir(directory)
                os.mkdir("assets")
                for stage in ("young","mature"):
                    with open("assets/city-"+stage+".dat","wb") as handle:
                        handle.write(white*(FRAME_SIZE//2))
                screen=RoundScreen(Display())
                screen.choose("city")
                town={"houses":2,"residents":2}
                self.assertTrue(screen.show(0,world=town))
                before=len([x for x in screen.driver.calls if x[0]=="solid"])
                self.assertTrue(screen.set_lighting("night",0,world=town))
                with_lamps=len([x for x in screen.driver.calls if x[0]=="solid"])
                self.assertGreater(with_lamps,before)
                self.assertEqual(screen.status()["day_phase"],"night")
                self.assertTrue(screen.animate(0,world=town))
                self.assertTrue(screen.set_lighting("lights_out",0,world=town))
                after=len([x for x in screen.driver.calls if x[0]=="solid"])
                self.assertGreater(after,with_lamps)  # walkers, but no added lamps
                self.assertFalse(screen.set_lighting("lights_out",0,world=town))
            finally:
                os.chdir(previous)

    def test_town_population_moves_as_exact_one_by_three_pixel_figures(self):
        self.assertEqual(town_art_alpha(0, 1), 0)
        self.assertEqual(town_art_alpha(43200, 1), 0)
        self.assertGreater(town_art_alpha(180, 2), 0)
        self.assertEqual(town_art_alpha(43200, 14), 255)
        self.assertEqual(len(town_people(2, 1)), 2)
        self.assertNotEqual(town_people(2, 1), town_people(2, 2))
        self.assertEqual(len(town_people(40, 1)), 18)
        previous = os.getcwd()
        with tempfile.TemporaryDirectory() as directory:
            try:
                os.chdir(directory)
                os.mkdir("assets")
                for stage, color in (("young", b"\xf8\x00"),
                                     ("mature", b"\x07\xe0")):
                    with open("assets/city-" + stage + ".dat", "wb") as handle:
                        handle.write(color * (FRAME_SIZE // 2))
                driver = Display()
                screen = RoundScreen(driver)
                screen.choose("city")
                world = {"houses": 1, "residents": 2}
                self.assertTrue(screen.show(0, world=world))
                self.assertTrue(screen.animate(0, world=world))
                self.assertEqual(len(screen.people), 2)
                self.assertEqual(len(screen.particles), 4)  # canal + waterfall
                marks = [call for call in driver.calls if call[0] == "solid"]
                self.assertEqual(len(marks), 10)
                for _, (x, y, width, height, color) in marks[-6:]:
                    self.assertEqual((width, height), (1, 1))
                previous_patches = sum(p[2] for p in screen.particles)
                before = screen.people[:]
                self.assertTrue(screen.animate(0, world=world))
                self.assertNotEqual(screen.people, before)
                self.assertEqual(driver.rows, 240 + previous_patches + 6)
                world["residents"] = 4
                self.assertTrue(screen.animate(180, world=world))
                self.assertEqual(len(screen.people), 4)
                self.assertEqual(driver.rows, 240 + (previous_patches + 6) * 2)
            finally:
                os.chdir(previous)

    def test_hybrid_streams_three_village_ages_and_walkers_stay_on_terraces(self):
        self.assertEqual(hybrid_art_frames(0),
                         ("assets/hybrid-young.dat", "assets/hybrid-mid.dat", 0))
        self.assertEqual(hybrid_art_frames(10 * 1440),
                         ("assets/hybrid-mid.dat", "assets/hybrid-mature.dat", 0))
        self.assertEqual(hybrid_art_frames(30 * 1440),
                         ("assets/hybrid-mid.dat", "assets/hybrid-mature.dat", 255))
        self.assertEqual(len(hybrid_people(2, 1)), 2)
        self.assertTrue(all(35 <= x <= 115 and 105 <= y <= 175
                            for x, y in hybrid_people(18, 2)))
        previous = os.getcwd()
        with tempfile.TemporaryDirectory() as directory:
            try:
                os.chdir(directory)
                os.mkdir("assets")
                for stage, color in (("young", b"\xf8\x00"),
                                     ("mid", b"\x07\xe0"),
                                     ("mature", b"\x00\x1f")):
                    with open("assets/hybrid-" + stage + ".dat", "wb") as output:
                        output.write(color * (FRAME_SIZE // 2))

                class Capture(Display):
                    def __init__(self):
                        super().__init__()
                        self.last_frame_first_pixel = None

                    def write_pixels(self, chunk):
                        if self.rows % 240 == 0:
                            self.last_frame_first_pixel = bytes(chunk[:2])
                        super().write_pixels(chunk)

                driver = Capture()
                screen = RoundScreen(driver)
                screen.choose("hybrid")
                for minute, expected in ((0, b"\xf8\x00"),
                                         (10 * 1440, b"\x07\xe0"),
                                         (30 * 1440, b"\x00\x1f")):
                    self.assertTrue(screen.show(minute, world={"residents": 2, "houses": 1}))
                    self.assertEqual(driver.last_frame_first_pixel, expected)
                self.assertTrue(screen.animate(30 * 1440, world={"residents": 2}))
                self.assertEqual(len(screen.people), 2)
                previous_particles = screen.particles[:]
                previous_rows = driver.rows
                self.assertTrue(screen.animate(30 * 1440, world={"residents": 2}))
                self.assertEqual(driver.rows - previous_rows,
                                 sum(particle[2] for particle in previous_particles) + 6)
            finally:
                os.chdir(previous)

    def test_hybrid_leaf_and_water_sprites_are_subtle_bounded_and_animated(self):
        initial = hybrid_ambient_particles(1)
        moved = hybrid_ambient_particles(6)
        windy = hybrid_ambient_particles(6, weather="windy")
        nighttime = hybrid_ambient_particles(6, phase="night")
        self.assertEqual(len(initial), 9)  # 3 leaves, 4 lake glints, 2 waterfalls
        self.assertNotEqual([(x, y) for x, y, _, _ in initial],
                            [(x, y) for x, y, _, _ in moved])
        self.assertNotEqual([(x, y) for x, y, _, _ in moved],
                            [(x, y) for x, y, _, _ in windy])
        self.assertNotEqual(moved[0][3], nighttime[0][3])
        self.assertEqual(hybrid_ambient_particles(2, phase="lights_out"), [])
        self.assertTrue(all(color == 0xFFFF for _, _, _, color in
                            hybrid_ambient_particles(2, shaking=True)))
        for weather in ("sunny", "windy", "rain"):
            for x, y, size, _ in hybrid_ambient_particles(
                    12, weather=weather, tilt_x=8, tilt_y=8):
                self.assertTrue(0 <= x <= 240-size and 0 <= y <= 240-size)
                self.assertLess((x + size/2 - 120)**2 + (y + size/2 - 120)**2,
                                119**2)

    def test_water_motion_tracks_each_painted_scene_and_restores_with_light(self):
        for art in ("city", "forest", "fantasy", "aquarium", "river", "deepsea"):
            with self.subTest(art=art):
                a = water_ambient_particles(art, 1)
                b = water_ambient_particles(art, 5)
                self.assertTrue(a)
                self.assertNotEqual([(x, y) for x, y, _, _ in a],
                                    [(x, y) for x, y, _, _ in b])
                self.assertNotEqual(b[0][3], water_ambient_particles(art, 5, phase="night")[0][3])
                self.assertEqual(water_ambient_particles(art, 5, phase="lights_out"), [])
                self.assertTrue(all(color == 0xFFFF for _, _, _, color in
                                    water_ambient_particles(art, 5, shaking=True)))
                for tilt_x, tilt_y in ((-8, -8), (8, 8)):
                    for x, y, size, _ in water_ambient_particles(
                            art, 12, weather="windy", tilt_x=tilt_x, tilt_y=tilt_y):
                        self.assertGreaterEqual(min(x, y), 0)
                        self.assertLessEqual(max(x + size, y + size), 240)
                        self.assertLess((x + size/2 - 120)**2 + (y + size/2 - 120)**2,
                                        119**2)
        self.assertEqual(water_ambient_particles("nature", 3, growth=0), [])
        self.assertEqual(len(water_ambient_particles("nature", 3, growth=.4)), 2)
        self.assertEqual(len(water_ambient_particles("nature", 3, growth=.7)), 4)

    def test_nature_has_growing_wildlife_wind_sway_and_night_fireflies(self):
        sapling = nature_ambient_particles(1, growth=0)
        growing = nature_ambient_particles(1, growth=.4)
        waterfall = nature_ambient_particles(1, growth=.7)
        dusk = nature_ambient_particles(1, phase="dusk", growth=.7)
        self.assertEqual(len(sapling), 1)
        self.assertGreater(len(growing), len(sapling))
        self.assertEqual(len(waterfall), len(growing) + 2)
        self.assertEqual(len(dusk), len(waterfall) + 4)
        self.assertNotEqual(nature_ambient_particles(1, growth=.7),
                            nature_ambient_particles(6, growth=.7))
        self.assertNotEqual(nature_ambient_particles(6, growth=.7, weather="windy"),
                            nature_ambient_particles(6, growth=.7))
        self.assertEqual(nature_ambient_particles(5, phase="lights_out"), [])
        for phase in ("day", "night"):
            for x, y, size, _ in nature_ambient_particles(
                    14, phase=phase, growth=1, tilt_x=8, tilt_y=8):
                self.assertLess((x + size/2 - 120)**2 + (y + size/2 - 120)**2,
                                119**2)

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

    def test_touch_distinguishes_tap_swipe_and_chip_gestures(self):
        bus = I2C()
        now = [0]
        touch = CST816Touch(bus, clock_ms=lambda: now[0])
        self.assertIn((0x15, 0xFE, b"\x01"), bus.writes)
        self.assertIsNone(touch.poll_event())
        self.assertIsNone(touch.poll_event())
        bus.value = b"\x00\x00\x00\x00\x00\x00"
        self.assertEqual(touch.poll_event(), "tap")
        self.assertIsNone(touch.poll_event())
        bus.value = b"\x00\x01\x00\x32\x00\x50"
        self.assertIsNone(touch.poll_event())
        bus.value = b"\x00\x01\x00\xb4\x00\x50"
        self.assertIsNone(touch.poll_event())
        bus.value = b"\x00\x00\x00\x00\x00\x00"
        self.assertEqual(touch.poll_event(), "swipe_right")
        bus.value = b"\x0c\x01\x00\x40\x00\x50"
        self.assertIsNone(touch.poll_event())
        now[0] = 700
        bus.value = b"\x00\x00\x00\x00\x00\x00"
        self.assertEqual(touch.poll_event(), "long_press")

    def test_swipe_coordinates_override_stale_gesture_and_wait_for_release(self):
        bus = I2C()
        touch = CST816Touch(bus)
        # The previous right-swipe code remains latched during a new left swipe.
        bus.value = b"\x04\x01\x00\xb4\x00\x78"
        self.assertIsNone(touch.poll_event())
        bus.value = b"\x04\x01\x00\x3c\x00\x78"
        self.assertIsNone(touch.poll_event())
        bus.value = b"\x04\x00\x00\x3c\x00\x78"
        self.assertEqual(touch.poll_event(), "swipe_left")
        self.assertIsNone(touch.poll_event())

    def test_up_report_supplies_fast_swipe_endpoint(self):
        bus = I2C()
        touch = CST816Touch(bus)
        bus.value = b"\x00\x01\x00\xb4\x00\x78"
        self.assertIsNone(touch.poll_event())
        bus.value = b"\x00\x00\x40\x3c\x00\x78"
        self.assertEqual(touch.poll_event(), "swipe_left")

    def test_irq_distinguishes_repeated_fast_swipes_from_sticky_idle(self):
        class IRQ:
            def irq(self, trigger, handler):
                self.handler = handler

        now = [0]
        irq = IRQ()
        bus = I2C()
        touch = CST816Touch(bus, irq_pin=irq, clock_ms=lambda: now[0])
        bus.value = b"\x03\x00\x00\x3c\x00\x78"
        self.assertIsNone(touch.poll_event())
        irq.handler(irq)
        self.assertEqual(touch.poll_event(), "swipe_left")
        self.assertIsNone(touch.poll_event())
        now[0] = 100
        irq.handler(irq)
        self.assertIsNone(touch.poll_event())
        now[0] = 500
        irq.handler(irq)
        self.assertEqual(touch.poll_event(), "swipe_left")
        self.assertIsNone(touch.poll_event())

    def test_swipes_switch_world_and_only_unlocked_water_areas(self):
        class Touch:
            def __init__(self):
                self.events = iter(("swipe_left", "swipe_right", "swipe_up",
                                    "swipe_up", "tap", "long_press"))
            def poll_event(self):
                return next(self.events)
        screen = RoundScreen(Display())
        screen.touch = Touch()
        self.assertEqual(screen.poll_touch(), ("world", "city"))
        self.assertEqual(screen.poll_touch(), ("world", "nature"))
        screen.choose("aquarium")
        class Engine:
            worlds = {"aquarium": {"water_areas": {
                "river":{"unlocked":True},"ocean":{"unlocked":False},
                "deepsea":{"unlocked":True}}}}
        self.assertIsNone(screen.poll_touch(Engine()))
        Engine.worlds["aquarium"]["water_areas"]["ocean"]["unlocked"] = True
        self.assertEqual(screen.poll_touch(Engine()), ("area", "ocean"))
        self.assertEqual(screen.poll_touch(), ("tap", "aquarium"))
        self.assertEqual(screen.poll_touch(), ("info", "aquarium"))

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
                screen.set_brightness(32)
                self.assertEqual(screen.status()["brightness"], 32)
                with self.assertRaises(ValueError):
                    screen.set_brightness(0)
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
                before = device.rows
                self.assertTrue(screen.animate(120))
                self.assertEqual(screen.status()["animation_tick"], 1)
                self.assertEqual(len(screen.particles), 9)
                self.assertTrue(screen.animate(120))
                self.assertEqual(screen.status()["animation_tick"], 2)
                self.assertGreater(device.rows, before)
                class Motion:
                    shake_id = 0
                    def snapshot(self):
                        return {"connected": True, "tilt_x": 0.75,
                                "tilt_y": -0.5, "shake_enabled": True,
                                "shake_id": self.shake_id}
                motion = Motion()
                self.assertTrue(screen.animate(120, motion))
                self.assertEqual(screen.particles[0][0], 80)
                motion.shake_id = 1
                self.assertTrue(screen.animate(120, motion))
                self.assertEqual(screen.particles[0][3], 0xFFFF)
                self.assertTrue(screen.set_visible(False, 120))
                self.assertFalse(screen.status()["screen_on"])
                self.assertFalse(screen.animate(120))
                self.assertFalse(screen.show(120))
                self.assertTrue(screen.set_visible(True, 120))
                self.assertTrue(screen.status()["screen_on"])
                self.assertTrue(screen.show_info(120))
                self.assertEqual(screen.info_frames, 3)
                for _ in range(3):
                    self.assertTrue(screen.animate(120))
                self.assertEqual(screen.info_frames, 0)
                screen.choose_water_area("deepsea")
                self.assertFalse(screen.show(0))
                with self.assertRaises(ValueError):
                    screen.choose_water_area("ocean/../../settings")
            finally:
                os.chdir(previous)

    def test_charging_motif_only_when_status_is_truly_detected(self):
        class Charging:
            def status(self):
                return {"voltage": 3.92, "low": False, "charging": True}
        previous = os.getcwd()
        with tempfile.TemporaryDirectory() as directory:
            try:
                os.chdir(directory)
                os.mkdir("assets")
                for stage in ("young", "mature"):
                    with open("assets/nature-" + stage + ".dat", "wb") as f:
                        f.write(b"\x07\xe0" * (FRAME_SIZE // 2))
                driver = Display()
                self.assertTrue(RoundScreen(driver, battery=Charging()).show(0))
                self.assertIn(("solid", (100, 19, 31, 10, 0x05E0)), driver.calls)
            finally:
                os.chdir(previous)


if __name__ == "__main__":
    unittest.main()
