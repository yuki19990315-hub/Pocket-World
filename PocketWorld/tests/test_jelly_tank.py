import os
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'firmware'))

from jelly_tank import motion_parameters, warp_pixels, warp_reference
from pathlib import Path
ASSET = Path(__file__).resolve().parents[1] / "firmware/assets/jellyfish-tank.dat"
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

    def test_approved_image_warp_moves_without_mutating_the_source(self):
        source = ASSET.read_bytes()
        first, second = bytearray(len(source)), bytearray(len(source))
        warp_pixels(first, source, motion_parameters(1))
        warp_pixels(second, source, motion_parameters(8, 5, -5))
        self.assertNotEqual(first, second)
        self.assertEqual(source, ASSET.read_bytes())
        self.assertEqual(len(first), 240*240*2)
        self.assertGreater(len(set(first)), 32)

    def test_moving_jelly_erases_previous_frame_and_does_not_read_flash(self):
        previous = os.getcwd()
        with tempfile.TemporaryDirectory() as directory:
            try:
                os.chdir(directory)
                os.mkdir('assets')
                frame = ASSET.read_bytes()
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
                        expected = bytearray(len(frame))
                        warp_reference(expected,frame,motion_parameters(4))
                        self.assertEqual(actual, expected)
                        screen.battery_state = {"low": True}
                        screen.animate(0, world=world)
                        offset = (19*240+100)*2
                        self.assertEqual(driver.buffer[offset:offset+2], b"\xf8\x00")
            finally:
                os.chdir(previous)
