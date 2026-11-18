"""The local AP must remain recoverable when hardware deep-sleep is disabled."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "firmware"))
import main
from world_model import PocketWorld


class FakeScreen:
    selected = "nature"

    def __init__(self):
        self.visible = True
        self.transitions = []

    def set_visible(self, enabled, minutes):
        if self.visible == enabled:
            return False
        self.visible = enabled
        self.transitions.append((enabled, minutes))
        return True


class FakePower:
    def __init__(self, mode="clock_unknown"):
        self.mode = mode

    def status(self):
        return {"mode": self.mode, "sleep_supported": False}


class ScreenScheduleTest(unittest.TestCase):
    def test_night_blanks_screen_without_sleeping_wifi(self):
        engine = PocketWorld()
        engine.advance(600)
        screen, power = FakeScreen(), FakePower()
        self.assertFalse(main.sync_screen_schedule(screen, power, engine))
        power.mode = "sleep"
        self.assertTrue(main.sync_screen_schedule(screen, power, engine))
        self.assertEqual(screen.transitions, [(False, 10)])
        self.assertFalse(main.sync_screen_schedule(screen, power, engine))
        power.mode = "active"
        self.assertTrue(main.sync_screen_schedule(screen, power, engine))
        self.assertEqual(screen.transitions[-1], (True, 10))

    def test_unknown_time_is_failsafe_on(self):
        engine = PocketWorld()
        screen, power = FakeScreen(), FakePower("sleep")
        main.sync_screen_schedule(screen, power, engine)
        power.mode = "unknown"
        self.assertTrue(main.sync_screen_schedule(screen, power, engine))
        self.assertTrue(screen.visible)
        self.assertFalse(main.sync_screen_schedule(None, power, engine))


if __name__ == "__main__":
    unittest.main()
