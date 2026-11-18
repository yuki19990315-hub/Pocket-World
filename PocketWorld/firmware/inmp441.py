"""Optional INMP441 I2S sound-level adapter for ESP32-S3 MicroPython.

No audio is recorded, sent over Wi-Fi, or written to flash. Only a normalized
0..100 level is retained. The mapping is experimental until hardware testing.

INMP441 is a 24-bit microphone transmitting in 32-bit stereo I2S slots.
Connect the L/R pad to GND for the left slot (offset 0). If channel capture
is different on a particular firmware build, adjust the slot setting.
"""

import math
import struct


def level_from_pcm(data, length=None, slot=0):
    """Extract the selected channel's signed 24-bit samples from 32-bit I2S.

    Returns None for an incomplete block. A fixed logarithmic mapping prevents
    loud transients from dominating, but is not a calibrated sound meter.
    """
    if slot not in (0, 1):
        raise ValueError("I2S slot must be 0 (left) or 1 (right)")
    if length is None:
        length = len(data)
    if length < 8:
        return None
    count = 0
    squared = 0
    for offset in range(slot * 4, length - 3, 8):
        sample = struct.unpack_from("<i", data, offset)[0] >> 8
        squared += sample * sample
        count += 1
    if count == 0:
        return None
    rms = math.sqrt(squared / count)
    # Uncalibrated curve; after testing, tune to the user's office noise floor.
    if rms <= 600:
        return 0
    return max(0, min(100, int(100 * math.log(rms / 600) / math.log(1000))))


class INMP441:
    """Polling level detector; no speech recognition and no PCM persistence."""

    def __init__(self, sck_pin=15, ws_pin=16, sd_pin=17, slot=0, i2s=None):
        if slot not in (0, 1):
            raise ValueError("Invalid microphone channel")
        if i2s is None:
            from machine import I2S, Pin
            i2s = I2S(0, sck=Pin(sck_pin), ws=Pin(ws_pin), sd=Pin(sd_pin),
                      mode=I2S.RX, bits=32, format=I2S.STEREO,
                      rate=16000, ibuf=8192)
        self.i2s = i2s
        self.slot = slot
        self.buffer = bytearray(1024)
        self.level = None
        self.total = 0
        self.samples = 0

    def poll(self):
        length = self.i2s.readinto(self.buffer)
        if length is None or length <= 0:
            return None
        value = level_from_pcm(self.buffer, min(length, len(self.buffer)), self.slot)
        if value is None:
            return None
        self.level = value
        self.total += value
        self.samples += 1
        return value

    def take_average(self):
        """Consume sampled levels once per minute for world development."""
        if self.samples == 0:
            return None
        value = int(self.total / self.samples + 0.5)
        self.total = 0
        self.samples = 0
        return value

    def status(self):
        value = self.level
        return {"connected": value is not None, "level": value,
                "band": ("quiet" if value <= 24 else
                         "loud" if value >= 70 else "active") if value is not None else None}

    def deinit(self):
        self.i2s.deinit()
