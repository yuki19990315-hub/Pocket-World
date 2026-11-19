import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "firmware"))
from world_model import PocketWorld


class TestSoundReactions(unittest.TestCase):
    def test_no_mic_is_assumed_on_boot(self):
        engine = PocketWorld()
        self.assertEqual(engine.snapshot()["audio"], {
            "connected": False, "level": None, "band": None,
        })

    def test_quiet_active_loud_change_nature_and_harmony_weather(self):
        engine = PocketWorld()
        for level, band, weather in ((10, "quiet", "sunny"),
                                     (40, "active", "windy"),
                                     (90, "loud", "rain")):
            self.assertTrue(engine.observe_sound(level))
            self.assertEqual(engine.snapshot()["audio"]["band"], band)
            for ident in ("nature", "hybrid"):
                self.assertEqual(engine.worlds[ident]["weather"], weather)
        self.assertEqual(len(engine.worlds["nature"]["events"]), 3)

    def test_stable_audio_does_not_spam_weather_events(self):
        engine = PocketWorld()
        for _ in range(9):
            engine.observe_sound(0)
        self.assertEqual(len(engine.worlds["nature"]["events"]), 1)

    def test_city_and_harmony_develop_at_different_rates(self):
        engine = PocketWorld()
        for _ in range(4):
            engine.observe_sound(85)
        self.assertEqual(engine.worlds["city"]["residents"], 3)
        self.assertEqual(engine.worlds["hybrid"]["residents"], 2)
        for _ in range(8):
            engine.observe_sound(85)
        self.assertEqual(engine.worlds["city"]["houses"], 2)
        self.assertEqual(engine.worlds["hybrid"]["residents"], 4)

    def test_loud_audio_can_create_rare_magic_event(self):
        engine = PocketWorld()
        for _ in range(7):
            engine.observe_sound(100)
        self.assertEqual(engine.worlds["fantasy"]["sound_sparks"], 7)
        self.assertFalse(any("珍しい流れ星" in event for event in engine.worlds["fantasy"]["events"]))
        engine.observe_sound(100)
        self.assertEqual(engine.worlds["fantasy"]["sound_sparks"], 0)
        self.assertTrue(any("珍しい流れ星" in event for event in engine.worlds["fantasy"]["events"]))

    def test_invalid_levels_have_no_effect(self):
        engine = PocketWorld()
        snapshot = engine.snapshot()
        for value in (-1, 101, None, True, "unknown", float("inf")):
            self.assertFalse(engine.observe_sound(value))
        self.assertEqual(engine.snapshot(), snapshot)

    def test_only_derived_progress_is_persisted(self):
        engine = PocketWorld()
        engine.observe_sound(80)
        saved = engine.persistable()
        self.assertNotIn("audio", saved)
        restored = PocketWorld(saved)
        self.assertEqual(restored.worlds, engine.worlds)
        self.assertFalse(restored.snapshot()["audio"]["connected"])
        engine.disconnect_sound()
        self.assertFalse(engine.snapshot()["audio"]["connected"])


if __name__ == "__main__":
    unittest.main()
