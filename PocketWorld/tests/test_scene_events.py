import json
import os
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "firmware"))
from scene_events import VISITORS, VISITOR_INFO, active_visit, visitor_frames, visitor_position
from world_model import PocketWorld
from round_screen import FRAME_SIZE, RoundScreen


class SceneEventsTest(unittest.TestCase):
    def test_first_minute_brings_visitors_without_accelerating_growth(self):
        engine = PocketWorld()
        before = {key: (world["houses"], world["plants"], world["residents"])
                  for key, world in engine.worlds.items()}
        engine.advance(60)
        for key, world in engine.worlds.items():
            if key == "jellyfish":
                continue
            visit = active_visit(world)
            self.assertIsNotNone(visit)
            self.assertEqual(sum(world["discoveries"].values()), 1)
            self.assertEqual((world["houses"], world["plants"], world["residents"]), before[key])
            self.assertIn("来訪", world["journal"][-1]["message"])
        self.assertEqual(active_visit(engine.worlds["aquarium"])["area"], "river")

    def test_visits_expire_and_do_not_leak_between_water_areas(self):
        engine = PocketWorld()
        engine.advance(60)
        water = engine.worlds["aquarium"]
        self.assertIsNone(active_visit(water, "ocean"))
        engine.advance(32)
        self.assertTrue(all(active_visit(world) is None for world in engine.worlds.values()))
        self.assertTrue(all(world["discoveries"] for world in engine.worlds.values()
                            if world["id"] != "jellyfish"))

    def test_saved_discoveries_migrate_and_snapshots_are_independent(self):
        engine = PocketWorld()
        engine.advance(60)
        saved = json.loads(json.dumps(engine.persistable()))
        restored = PocketWorld(saved)
        self.assertEqual(restored.persistable(), engine.persistable())
        snapshot = restored.snapshot()
        nature = snapshot["worlds"][0]
        kind = next(iter(nature["discoveries"]))
        nature["discoveries"][kind] = 9999
        nature["visit"]["minute"] = 9000
        self.assertEqual(restored.worlds["nature"]["discoveries"][kind], 1)
        self.assertEqual(restored.worlds["nature"]["visit"]["minute"], 1)
        older = PocketWorld({"version": 3, "worlds": {
            "nature": {"minutes": 345, "houses": 3, "discoveries": ["bad"],
                       "visit": {"kind": "swallow"}}}})
        self.assertEqual(older.worlds["nature"]["minutes"], 345)
        self.assertEqual(older.worlds["nature"]["houses"], 3)
        self.assertEqual(older.worlds["nature"]["discoveries"], {})
        self.assertIsNone(active_visit(older.worlds["nature"]))

    def test_hidden_worlds_record_rare_visits_with_bounded_journals(self):
        engine = PocketWorld()
        engine.advance(4 * 86400)
        for world in engine.worlds.values():
            if world["id"] == "jellyfish":
                continue
            self.assertGreater(sum(world["discoveries"].values()), 100)
            self.assertTrue(any(VISITOR_INFO[kind][3] for kind in world["discoveries"]))
            self.assertLessEqual(len(world["journal"]), 24)
            self.assertLessEqual(len(world["events"]), 5)
        water = engine.worlds["aquarium"]
        self.assertTrue(any(VISITOR_INFO[kind][0] == "ocean" for kind in water["discoveries"]))
        self.assertTrue(any(VISITOR_INFO[kind][0] == "deepsea" for kind in water["discoveries"]))

    def test_large_and_small_time_steps_produce_identical_visits(self):
        first, second = PocketWorld(), PocketWorld()
        first.advance(653)
        for _ in range(10):
            second.advance(60)
        second.advance(53)
        self.assertEqual(first.persistable(), second.persistable())

    def test_all_visitor_pixels_stay_on_the_round_display(self):
        for kind, (source, name, shape, rare) in VISITOR_INFO.items():
            frames = visitor_frames(kind)
            self.assertEqual(len(frames), 2)
            for age in (0, 15, 31):
                for tick in (0, 1):
                    x, y = visitor_position({"id": kind, "area": source, "age": age}, tick)
                    for dx, dy, width, height, color in frames[tick]:
                        self.assertGreater(width * height, 0)
                        self.assertTrue(0 <= color <= 65535)
                        for px, py in ((x + dx, y + dy), (x + dx + width, y + dy + height)):
                            self.assertTrue(0 <= px < 240 and 0 <= py < 240)
                            self.assertLess((px - 120) ** 2 + (py - 120) ** 2, 120 ** 2)


class CanvasDriver:
    def __init__(self):
        self.buffer = bytearray(FRAME_SIZE)

    def window(self, x, y, width, height):
        self.region = (x, y, width, height)
        self.offset = 0

    def start_pixels(self):
        pass

    def stop_pixels(self):
        pass

    def write_pixels(self, data):
        x, y, width, height = self.region
        for offset in range(0, len(data), 2):
            row, column = divmod(self.offset // 2, width)
            destination = ((y + row) * 240 + x + column) * 2
            self.buffer[destination:destination + 2] = data[offset:offset + 2]
            self.offset += 2

    def solid(self, x, y, width, height, color):
        self.window(x, y, width, height)
        self.write_pixels(bytes((color >> 8, color & 255)) * (width * height))


class VisitorRenderingTest(unittest.TestCase):
    def test_departed_visitor_restores_background_without_a_full_redraw(self):
        import round_screen

        def compose(output, early, late, settings):
            output[:] = early

        previous = os.getcwd()
        with tempfile.TemporaryDirectory() as directory:
            try:
                os.chdir(directory)
                os.mkdir("assets")
                background = b"\xf8\x00" * (FRAME_SIZE // 2)
                for phase in ("young", "mature"):
                    with open("assets/nature-" + phase + ".dat", "wb") as file:
                        file.write(background)
                with (patch.object(round_screen, "_compose_pixels", compose),
                      patch.object(round_screen, "nature_ambient_particles", return_value=[])):
                    driver = CanvasDriver()
                    screen = RoundScreen(driver)
                    world = PocketWorld().worlds["nature"]
                    world["minutes"] = 1
                    world["visit"] = {"kind": "swallow", "minute": 1}
                    screen.show(1, world=world)
                    with patch.object(round_screen, "valid_frame",
                                      side_effect=AssertionError("Animation read flash")):
                        screen.animate(1, world=world)
                        self.assertNotEqual(driver.buffer, background)
                        world["remainder"] = 32
                        screen.animate(1, world=world)
                    self.assertEqual(driver.buffer, background)
                    self.assertIsNone(screen.visitor_rect)
            finally:
                os.chdir(previous)


if __name__ == "__main__":
    unittest.main()
