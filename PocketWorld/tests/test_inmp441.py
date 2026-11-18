"""Desktop tests for the uncalibrated INMP441 I2S level detector."""

import os
import struct
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "firmware"))
from inmp441 import INMP441, level_from_pcm


def frame(left, right=0):
    # INMP441: signed 24-bit signal in a 32-bit stereo I2S slot.
    return struct.pack("<ii", left << 8, right << 8)


class FakeI2S:
    def __init__(self, frames):
        self.frames = list(frames)
        self.closed = False

    def readinto(self, buffer):
        if not self.frames:
            return 0
        data = self.frames.pop(0)
        buffer[:len(data)] = data
        return len(data)

    def deinit(self):
        self.closed = True


class INMP441Tests(unittest.TestCase):
    def test_left_channel_level_ranges(self):
        self.assertEqual(level_from_pcm(frame(0) * 8), 0)
        self.assertLessEqual(level_from_pcm(frame(2000) * 8), 24)
        self.assertTrue(25 <= level_from_pcm(frame(8000) * 8) < 70)
        self.assertGreaterEqual(level_from_pcm(frame(100000) * 8), 70)

    def test_signed_audio_and_silence_have_expected_levels(self):
        self.assertEqual(level_from_pcm(frame(-8000) * 8),
                         level_from_pcm(frame(8000) * 8))
        self.assertEqual(level_from_pcm(frame(0) * 8), 0)

    def test_channel_selection(self):
        audio = frame(0, 120000) * 4
        self.assertEqual(level_from_pcm(audio, slot=0), 0)
        self.assertGreaterEqual(level_from_pcm(audio, slot=1), 70)
        with self.assertRaises(ValueError):
            level_from_pcm(audio, slot=2)

    def test_incomplete_block_is_not_treated_as_sound(self):
        self.assertIsNone(level_from_pcm(b"\x00" * 7))

    def test_sampler_averages_without_storing_pcm(self):
        io = FakeI2S([frame(8000) * 8, frame(100000) * 8])
        mic = INMP441(i2s=io)
        self.assertFalse(mic.status()["connected"])
        quiet = mic.poll()
        loud = mic.poll()
        self.assertEqual(mic.status()["level"], loud)
        self.assertEqual(mic.take_average(), (quiet + loud + 1) // 2)
        self.assertIsNone(mic.take_average())
        mic.deinit()
        self.assertTrue(io.closed)

    def test_empty_i2s_read_does_not_claim_microphone(self):
        mic = INMP441(i2s=FakeI2S([]))
        self.assertIsNone(mic.poll())
        self.assertFalse(mic.status()["connected"])


if __name__ == "__main__":
    unittest.main()
