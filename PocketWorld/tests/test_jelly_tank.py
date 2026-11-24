import os
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'firmware'))

from jelly_tank import motion_parameters, warp_pixels, warp_reference, swim_state
from pathlib import Path
ASSET = Path(__file__).resolve().parents[1] / "firmware/assets/jellyfish-tank.dat"
from world_model import PocketWorld
from scene_events import active_visit
from test_scene_events import CanvasDriver
import round_screen


class JellyTankTest(unittest.TestCase):
    def test_background_is_black(self):
        source = ASSET.read_bytes()
        self.assertEqual(source[:480], bytes(480))
        output = bytearray(len(source))
        warp_pixels(output,source,motion_parameters(7.2))
        for x,y in ((0,0),(239,0),(0,239),(239,239)):
            offset=(y*240+x)*2
            self.assertEqual(output[offset:offset+2], bytes(2))
        for phase in ('day','dawn','dusk','night','lights_out'):
            tinted = round_screen.ambience_row(bytes(480),phase)*240
            warp_pixels(output,tinted,motion_parameters(7.2))
            self.assertEqual(output,bytes(len(output)),phase)

    def test_propulsion_matches_squeeze_and_oral_arms_follow_later(self):
        self.assertGreater(swim_state(3)[0], .9)
        pulse_step = swim_state(3)[1]-swim_state(2)[1]
        coast_step = swim_state(13)[1]-swim_state(12)[1]
        self.assertGreater(pulse_step, coast_step*3)
        self.assertEqual(swim_state(2)[2], 0)
        self.assertGreater(swim_state(4)[2], 0)
        previous = 0
        for tick in range(400):
            travel = swim_state(tick)[1]
            self.assertGreaterEqual(travel, previous)
            self.assertLess(travel-previous, 1)
            previous = travel

    def test_small_jelly_roams_without_leaving_the_round_display(self):
        centers = []
        for tick in range(0, 2400, 7):
            dx, dy, xs, ys, _, _ = motion_parameters(tick, 5, -5)
            self.assertGreaterEqual(xs, 1840)
            self.assertGreaterEqual(ys, 1776)
            centers.append((120+dx*1024/xs, 96+(24+dy)*1024/ys))
            for x,y in ((24,132),(100,38),(215,104),(155,202)):
                px = 120+(x-120+dx)*1024/xs
                py = 96+(y-96+dy)*1024/ys
                self.assertLess((px-120)**2+(py-120)**2, 119**2)
        self.assertGreater(max(x for x,y in centers)-min(x for x,y in centers), 70)
        self.assertGreater(max(y for x,y in centers)-min(y for x,y in centers), 45)

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
                        screen.jelly_elapsed_ms = 0
                        for _ in range(10):
                            screen.animate(0,world=world,elapsed_ms=100)
                        self.assertEqual(driver.buffer,expected)
                        screen.battery_state = {"low": True}
                        screen.animate(0, world=world)
                        offset = (19*240+100)*2
                        self.assertEqual(driver.buffer[offset:offset+2], b"\xf8\x00")
            finally:
                os.chdir(previous)
