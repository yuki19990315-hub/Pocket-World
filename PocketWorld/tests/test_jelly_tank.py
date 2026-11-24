import os
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'firmware'))

from jelly_tank import background, jelly_rectangles
from world_model import PocketWorld
from scene_events import active_visit
from test_scene_events import CanvasDriver
import round_screen


class JellyTankTest(unittest.TestCase):
    def test_old_save_keeps_progress_and_adds_exactly_one_jelly(self):
        old = PocketWorld()
        old.advance(3600)
        saved = old.persistable()
        del saved['worlds']['jellyfish']
        restored = PocketWorld(saved)
        for ident, world in saved['worlds'].items():
            self.assertEqual(restored.worlds[ident], world)
        for _ in range(5):
            restored.advance(7 * 86400)
            restored.tap('jellyfish')
            restored.observe_sound(90)
        world = restored.worlds['jellyfish']
        self.assertEqual((world['jellyfish_count'], world['wildlife'], world['plants'],
                          world['residents'], world['houses']), (1, 1, 0, 0, 0))
        self.assertEqual(world['discoveries'], {})
        self.assertIsNone(active_visit(world))
        snapshot = restored.snapshot()['worlds'][-1]
        self.assertEqual(snapshot['visitor_catalog'], [])
        self.assertIsNone(snapshot['visitor'])
        self.assertEqual(PocketWorld(restored.persistable()).worlds['jellyfish'], world)

    def test_bell_and_tentacles_move_inside_round_screen(self):
        self.assertNotEqual(jelly_rectangles(0), jelly_rectangles(8))
        for tick in range(0, 400, 7):
            for tilt in (-8, 8):
                for x, y, w, h, color in jelly_rectangles(tick, tilt, -tilt):
                    self.assertTrue(0 <= color <= 65535)
                    for px, py in ((x, y), (x+w, y+h)):
                        self.assertLess((px-120)**2 + (py-120)**2, 120**2)

    def test_moving_jelly_erases_previous_frame_and_does_not_read_flash(self):
        previous = os.getcwd()
        with tempfile.TemporaryDirectory() as directory:
            try:
                os.chdir(directory)
                os.mkdir('assets')
                frame = background()
                with open('assets/jellyfish-tank.dat', 'wb') as file:
                    file.write(frame)
                def compose(output, early, late, settings):
                    output[:] = early
                with patch.object(round_screen, '_compose_pixels', compose):
                    driver = CanvasDriver()
                    screen = round_screen.RoundScreen(driver)
                    screen.choose('jellyfish')
                    world = PocketWorld().worlds['jellyfish']
                    screen.show(0, world=world)
                    with patch.object(round_screen, 'valid_frame', side_effect=AssertionError('Flash read')):
                        for tick in range(4):
                            screen.animate(0, world=world)
                        actual = bytes(driver.buffer)
                        expected = CanvasDriver()
                        expected.buffer[:] = frame
                        for rectangle in jelly_rectangles(4):
                            expected.solid(*rectangle)
                        self.assertEqual(actual, expected.buffer)
            finally:
                os.chdir(previous)
