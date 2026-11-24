import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "firmware"))
from world_model import (MATURITY_MINUTES, MAX_OFFLINE_SECONDS, PocketWorld,
                         WATER_UNLOCK_MINUTES)


class TestPocketWorld(unittest.TestCase):
    def test_town_starts_with_one_house_and_two_wandering_residents(self):
        engine = PocketWorld()
        city = engine.worlds["city"]
        self.assertEqual((city["houses"], city["residents"]), (1, 2))
        engine.advance(70 * 60)
        self.assertEqual((city["houses"], city["residents"]), (1, 3))
        engine.advance(110 * 60)
        self.assertEqual(city["houses"], 2)
        self.assertGreater(city["residents"], 2)
        self.assertEqual(PocketWorld(engine.persistable()).worlds["city"], city)

    def test_hybrid_grows_from_one_cottage_without_losing_old_saves(self):
        engine = PocketWorld()
        hybrid = engine.worlds["hybrid"]
        self.assertEqual((hybrid["houses"], hybrid["residents"]), (1, 2))
        engine.advance(180 * 60)
        self.assertEqual(hybrid["houses"], 2)
        self.assertGreater(hybrid["residents"], 2)
        restored = PocketWorld({"worlds": {"hybrid": {"houses": 0,
                                                      "residents": 0,
                                                      "minutes": 42}}})
        self.assertEqual(restored.worlds["hybrid"]["minutes"], 42)
        self.assertEqual((restored.worlds["hybrid"]["houses"],
                          restored.worlds["hybrid"]["residents"]), (1, 2))

    def test_seven_worlds_exist(self):
        engine = PocketWorld()
        self.assertEqual(set(engine.worlds), {"nature", "city", "hybrid", "fantasy",
                                             "forest", "aquarium", "jellyfish"})

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

    def test_water_starts_with_river_only(self):
        areas = PocketWorld().worlds["aquarium"]["water_areas"]
        self.assertTrue(areas["river"]["unlocked"])
        self.assertFalse(areas["ocean"]["unlocked"])
        self.assertFalse(areas["deepsea"]["unlocked"])
        self.assertEqual(areas["river"]["fish"], 2)

    def test_sea_and_deep_sea_unlock_with_time(self):
        engine = PocketWorld()
        engine.advance((WATER_UNLOCK_MINUTES["ocean"] - 1) * 60)
        self.assertFalse(engine.worlds["aquarium"]["water_areas"]["ocean"]["unlocked"])
        engine.advance(60)
        self.assertTrue(engine.worlds["aquarium"]["water_areas"]["ocean"]["unlocked"])
        self.assertFalse(engine.worlds["aquarium"]["water_areas"]["deepsea"]["unlocked"])
        engine.advance((WATER_UNLOCK_MINUTES["deepsea"] - WATER_UNLOCK_MINUTES["ocean"]) * 60)
        self.assertTrue(engine.worlds["aquarium"]["water_areas"]["deepsea"]["unlocked"])
        events = engine.worlds["aquarium"]["events"]
        self.assertTrue(any("深海" in entry for entry in events))

    def test_water_areas_progress_without_mixing(self):
        engine = PocketWorld()
        engine.advance(WATER_UNLOCK_MINUTES["ocean"] * 60)
        areas = engine.worlds["aquarium"]["water_areas"]
        river_fish = areas["river"]["fish"]
        ocean_fish = areas["ocean"]["fish"]
        self.assertGreater(river_fish, 2)
        self.assertEqual(ocean_fish, 2)
        engine.advance(220 * 60)
        self.assertGreater(areas["ocean"]["fish"], ocean_fish)
        self.assertGreaterEqual(areas["river"]["fish"], river_fish)

    def test_saving_preserves_new_worlds_and_old_save_migrates(self):
        old = PocketWorld()
        old.advance(3600)
        data = old.persistable()
        data["worlds"].pop("forest")
        data["worlds"].pop("aquarium")
        migrated = PocketWorld(data)
        self.assertEqual(migrated.worlds["nature"], old.worlds["nature"])
        self.assertEqual(migrated.worlds["forest"]["minutes"], 0)
        self.assertTrue(migrated.worlds["aquarium"]["water_areas"]["river"]["unlocked"])
        migrated.advance(240 * 60)
        restored = PocketWorld(migrated.persistable())
        self.assertEqual(restored.worlds, migrated.worlds)

    def test_snapshot_cannot_mutate_water_habitat(self):
        engine = PocketWorld()
        state = engine.snapshot()
        aquarium = next(world for world in state["worlds"] if world["id"] == "aquarium")
        aquarium["water_areas"]["river"]["fish"] = 999
        self.assertEqual(engine.worlds["aquarium"]["water_areas"]["river"]["fish"], 2)

    def test_event_journal_is_bounded_and_snapshot_is_immutable(self):
        engine = PocketWorld()
        for _ in range(40):
            engine.tap("nature")
        self.assertEqual(len(engine.worlds["nature"]["journal"]), 24)
        snapshot = engine.snapshot()
        snapshot["worlds"][0]["journal"][-1]["message"] = "tampered"
        self.assertNotEqual(engine.worlds["nature"]["journal"][-1]["message"], "tampered")
        saved = engine.persistable()
        self.assertEqual(PocketWorld(saved).worlds, engine.worlds)

    def test_town_has_a_month_of_changes(self):
        engine = PocketWorld()
        engine.advance(3 * 3600)
        early = engine.worlds["city"]["houses"]
        self.assertEqual(early, 2)
        engine.advance(4 * 86400)
        day_four = engine.worlds["city"]["houses"]
        self.assertGreater(day_four, early)
        self.assertLess(day_four, 16)
        while engine.worlds["city"]["minutes"] < MATURITY_MINUTES:
            remaining = MATURITY_MINUTES - engine.worlds["city"]["minutes"]
            engine.advance(min(6 * 86400, remaining * 60))
        self.assertGreater(engine.worlds["city"]["houses"], day_four)
        self.assertEqual(engine.worlds["city"]["minutes"], MATURITY_MINUTES)
        self.assertTrue(any("成熟" in event for event in engine.worlds["city"]["events"]) or
                        any("成熟" in item["message"] for item in engine.worlds["city"]["journal"]))

    def test_forest_grows_independently(self):
        engine = PocketWorld()
        before_city = dict(engine.worlds["city"])
        before_plants = engine.worlds["forest"]["plants"]
        engine._step_forest(engine.worlds["forest"], 720)
        self.assertGreater(engine.worlds["forest"]["plants"], before_plants)
        self.assertEqual(engine.worlds["city"], before_city)


if __name__ == "__main__":
    unittest.main()
