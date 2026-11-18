import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "firmware"))
from world_model import MAX_OFFLINE_SECONDS, PocketWorld


class TestPocketWorld(unittest.TestCase):
    def test_four_worlds_exist(self):
        engine = PocketWorld()
        self.assertEqual(set(engine.worlds), {"nature", "city", "hybrid", "fantasy"})

    def test_hidden_worlds_advance(self):
        engine = PocketWorld()
        engine.advance(180 * 60)
        self.assertTrue(all(world["minutes"] == 180 for world in engine.worlds.values()))
        self.assertGreater(engine.worlds["city"]["houses"], 1)
        self.assertGreater(engine.worlds["fantasy"]["magic"], 1)

    def test_terrain_seed_is_stable(self):
        engine = PocketWorld()
        initial = engine.worlds["nature"]["seed"]
        engine.advance(1000)
        self.assertEqual(engine.worlds["nature"]["seed"], initial)

    def test_save_restore_preserves_states(self):
        before = PocketWorld()
        before.advance(3600)
        after = PocketWorld(before.persistable())
        self.assertEqual(before.snapshot()["worlds"], after.snapshot()["worlds"])

    def test_touch_only_modifies_selected_world(self):
        engine = PocketWorld()
        old_nature = engine.worlds["nature"]["plants"]
        old_city = dict(engine.worlds["city"])
        self.assertTrue(engine.tap("nature"))
        self.assertEqual(engine.worlds["nature"]["plants"], old_nature + 1)
        self.assertEqual(engine.worlds["city"], old_city)
        self.assertFalse(engine.tap("unknown"))

    def test_phone_clock_recovers_downtime_once(self):
        engine = PocketWorld({"last_wall_epoch": 1770000000})
        engine.advance(100)
        recovered = engine.reconcile_clock(1770003600)
        self.assertEqual(recovered, 3500)
        self.assertEqual(engine.worlds["nature"]["minutes"], 60)
        self.assertEqual(engine.reconcile_clock(1770003660), 0)

    def test_offline_recovery_is_bounded(self):
        engine = PocketWorld({"last_wall_epoch": 1770000000})
        recovered = engine.reconcile_clock(1770000000 + 10 * MAX_OFFLINE_SECONDS)
        self.assertEqual(recovered, MAX_OFFLINE_SECONDS)
        self.assertEqual(engine.worlds["nature"]["minutes"], MAX_OFFLINE_SECONDS // 60)

    def test_invalid_clock_ignored(self):
        engine = PocketWorld()
        self.assertEqual(engine.reconcile_clock("oops"), 0)
        self.assertFalse(engine.clock_reconciled)


if __name__ == "__main__":
    unittest.main()
