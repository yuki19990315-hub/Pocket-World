"""GC9A01A round LCD + CST816S touch for Waveshare ESP32-S3-Touch-LCD-1.28.

Device RGB565 artwork is streamed from /assets, one scanline at a time;
no 115KB framebuffer or PNG decoder is required. Only the display controller
has been simulated on CPython so far: actual SPI orientation/colour and touch
must still be checked on the user's board before enabling deep sleep.

Pin map: https://docs.waveshare.com/ESP32-S3-Touch-LCD-1.28
GC9A01A initialization command data adapted from Adafruit_GC9A01A (BSD).
See THIRD_PARTY_NOTICES.md for attribution.
"""

import time

WIDTH = 240
HEIGHT = 240
WORLD_IDS = ("nature", "city", "hybrid", "fantasy", "forest", "aquarium")
FRAME_SIZE = WIDTH * HEIGHT * 2


def blend_row(early, late, alpha):
    """Return one big-endian RGB565 row; alpha 0..255, exact endpoints."""
    if len(early) != len(late) or len(early) % 2:
        raise ValueError("RGB565 row length mismatch")
    if alpha <= 0:
        return early
    if alpha >= 255:
        return late
    result = bytearray(len(early))
    for i in range(0, len(result), 2):
        a = (early[i] << 8) | early[i + 1]
        b = (late[i] << 8) | late[i + 1]
        ar, ag, ab = (a >> 11) & 31, (a >> 5) & 63, a & 31
        br, bg, bb = (b >> 11) & 31, (b >> 5) & 63, b & 31
        value = (((ar * (255 - alpha) + br * alpha + 127) // 255) << 11 |
                 ((ag * (255 - alpha) + bg * alpha + 127) // 255) << 5 |
                 ((ab * (255 - alpha) + bb * alpha + 127) // 255))
        result[i] = value >> 8
        result[i + 1] = value & 255
    return result


def valid_frame(path):
    try:
        import os
        return os.stat(path)[6] == FRAME_SIZE
    except OSError:
        return False


class GC9A01:
    """Pure MicroPython SPI streaming; WaveShare touch-board pin allocation."""
    def __init__(self, machine_module=None, delay_ms=None):
        if machine_module is None:
            import machine as machine_module
        self.machine = machine_module
        self.wait = delay_ms or getattr(time, "sleep_ms", lambda ms: time.sleep(ms / 1000))
        pin = machine_module.Pin
        self.cs = pin(9, pin.OUT, value=1)
        self.dc = pin(8, pin.OUT, value=1)
        self.reset = pin(14, pin.OUT, value=1)
        self.backlight = pin(2, pin.OUT, value=0)
        self.spi = machine_module.SPI(2, baudrate=40_000_000, polarity=0, phase=0,
                                      sck=pin(10), mosi=pin(11))
        self._pwm = None
        self._initialize()
        self.set_brightness(65)

    def command(self, opcode, payload=b""):
        self.cs.value(0)
        self.dc.value(0)
        self.spi.write(bytes((opcode,)))
        if payload:
            self.dc.value(1)
            self.spi.write(payload)
        self.cs.value(1)

    def _initialize(self):
        self.reset.value(1); self.wait(20)
        self.reset.value(0); self.wait(20)
        self.reset.value(1); self.wait(120)
        # Initialization parameters mirror Adafruit's manufacturer-based
        # GC9A01A sequence. Use BGR and 16-bit RGB565, inversion enabled.
        commands = (
            (0xEF, b""), (0xEB, b"\x14"), (0xFE, b""), (0xEF, b""),
            (0xEB, b"\x14"), (0x84, b"\x40"), (0x85, b"\xff"),
            (0x86, b"\xff"), (0x87, b"\xff"), (0x88, b"\x0a"),
            (0x89, b"\x21"), (0x8A, b"\x00"), (0x8B, b"\x80"),
            (0x8C, b"\x01"), (0x8D, b"\x01"), (0x8E, b"\xff"),
            (0x8F, b"\xff"), (0xB6, b"\x00\x00"), (0x36, b"\x48"),
            (0x3A, b"\x05"), (0x90, b"\x08\x08\x08\x08"),
            (0xBD, b"\x06"), (0xBC, b"\x00"), (0xFF, b"\x60\x01\x04"),
            (0xC3, b"\x13"), (0xC4, b"\x13"), (0xC9, b"\x22"),
            (0xBE, b"\x11"), (0xE1, b"\x10\x0e"),
            (0xDF, b"\x21\x0c\x02"),
            (0xF0, b"\x45\x09\x08\x08\x26\x2a"),
            (0xF1, b"\x43\x70\x72\x36\x37\x6f"),
            (0xF2, b"\x45\x09\x08\x08\x26\x2a"),
            (0xF3, b"\x43\x70\x72\x36\x37\x6f"),
            (0xED, b"\x1b\x0b"), (0xAE, b"\x77"),
            (0xCD, b"\x63"), (0xE8, b"\x34"),
            (0x62, b"\x18\x0d\x71\xed\x70\x70\x18\x0f\x71\xef\x70\x70"),
            (0x63, b"\x18\x11\x71\xf1\x70\x70\x18\x13\x71\xf3\x70\x70"),
            (0x64, b"\x28\x29\xf1\x01\xf1\x00\x07"),
            (0x66, b"\x3c\x00\xcd\x67\x45\x45\x10\x00\x00\x00"),
            (0x67, b"\x00\x3c\x00\x00\x00\x01\x54\x10\x32\x98"),
            (0x74, b"\x10\x85\x80\x00\x00\x4e\x00"),
            (0x98, b"\x3e\x07"), (0x35, b""), (0x21, b""),
            (0x11, b"")
        )
        for opcode, payload in commands:
            self.command(opcode, payload)
        self.wait(150)
        self.command(0x29)
        self.wait(150)

    def set_brightness(self, percent):
        percent = max(0, min(100, int(percent)))
        if self._pwm is None:
            try:
                self._pwm = self.machine.PWM(self.backlight, freq=1000, duty_u16=0)
            except (AttributeError, TypeError):
                self._pwm = False
        if self._pwm:
            self._pwm.duty_u16(percent * 65535 // 100)
        else:
            self.backlight.value(1 if percent else 0)

    def window(self, x, y, w, h):
        if min(x, y, w, h) < 0 or x + w > WIDTH or y + h > HEIGHT or not w or not h:
            raise ValueError("Invalid display window")
        self.command(0x2A, bytes((x >> 8, x & 255, (x + w - 1) >> 8, (x + w - 1) & 255)))
        self.command(0x2B, bytes((y >> 8, y & 255, (y + h - 1) >> 8, (y + h - 1) & 255)))
        self.command(0x2C)

    def start_pixels(self):
        self.dc.value(1)
        self.cs.value(0)

    def write_pixels(self, buffer):
        self.spi.write(buffer)

    def stop_pixels(self):
        self.cs.value(1)

    def solid(self, x, y, w, h, color):
        self.window(x, y, w, h)
        row = bytes((color >> 8, color & 255)) * w
        self.start_pixels()
        for _ in range(h):
            self.write_pixels(row)
        self.stop_pixels()

    def sleep(self):
        self.set_brightness(0)
        self.command(0x28)
        self.command(0x10)


class CST816Touch:
    ADDRESS = 0x15

    def __init__(self, i2c, reset_pin=None):
        self.i2c = i2c
        if reset_pin is not None:
            reset_pin.value(0)
            getattr(time, "sleep_ms", lambda ms: time.sleep(ms / 1000))(12)
            reset_pin.value(1)
        if self.ADDRESS not in i2c.scan():
            raise OSError("CST816S not found on I2C")
        self.was_down = False

    def tapped(self):
        """Edge-triggered single touch. Gesture registers must be tested on board."""
        data = self.i2c.readfrom_mem(self.ADDRESS, 0x02, 5)
        down = (data[0] & 0x0f) == 1
        tapped = down and not self.was_down
        self.was_down = down
        if not tapped:
            return None
        x = ((data[1] & 15) << 8) | data[2]
        y = ((data[3] & 15) << 8) | data[4]
        return (x, y) if x < WIDTH and y < HEIGHT else None


class BatteryGauge:
    """GPIO1 3:1 voltage divider. Charging status is NOT exposed to software."""
    def __init__(self, machine_module=None):
        if machine_module is None:
            import machine as machine_module
        self.adc = machine_module.ADC(machine_module.Pin(1))
        try:
            self.adc.atten(self.adc.ATTN_11DB)
        except AttributeError:
            pass

    def voltage(self):
        total = 0
        for _ in range(6):
            if hasattr(self.adc, "read_uv"):
                total += self.adc.read_uv() * 3 / 1_000_000
            else:
                total += self.adc.read_u16() * (3.3 * 3 / 65535)
        return round(total / 6, 2)

    def status(self):
        volts = self.voltage()
        # Rough voltage band only, not accurate state-of-charge under load.
        low = 2.8 < volts < 3.55
        return {"voltage": volts, "low": low, "charging": None,
                "charge_detection": "unavailable"}


class RoundScreen:
    def __init__(self, driver, i2c=None, touch_reset_pin=None, battery=None):
        self.driver = driver
        self.selected = "nature"
        self.touch = None
        if i2c is not None:
            try:
                self.touch = CST816Touch(i2c, touch_reset_pin)
            except (OSError, ValueError):
                pass
        self.battery = battery
        self.battery_state = None
        self.last_draw_at = 0

    def choose(self, ident):
        if ident not in WORLD_IDS:
            raise ValueError("Unknown world ID")
        self.selected = ident

    def next_world(self):
        self.selected = WORLD_IDS[(WORLD_IDS.index(self.selected) + 1) % len(WORLD_IDS)]
        return self.selected

    def poll_touch(self):
        if self.touch is not None and self.touch.tapped() is not None:
            return self.next_world()
        return None

    def show(self, minutes, force=False):
        """Draw once on mode/day changes or scheduled refresh; no frame buffer."""
        ident = self.selected
        early_path = "assets/%s-young.dat" % ident
        mature_path = "assets/%s-mature.dat" % ident
        if not (valid_frame(early_path) and valid_frame(mature_path)):
            return False
        alpha = min(255, max(0, int(minutes) * 255 // (30 * 1440)))
        with open(early_path, "rb") as early, open(mature_path, "rb") as mature:
            self.driver.window(0, 0, WIDTH, HEIGHT)
            self.driver.start_pixels()
            try:
                for _ in range(HEIGHT):
                    a, b = early.read(WIDTH * 2), mature.read(WIDTH * 2)
                    if len(a) != WIDTH * 2 or len(b) != WIDTH * 2:
                        raise OSError("Truncated display asset")
                    self.driver.write_pixels(blend_row(a, b, alpha))
            finally:
                self.driver.stop_pixels()
        if self.battery is not None:
            self.battery_state = self.battery.status()
            if self.battery_state["low"]:
                # Tiny red indicator in a safe central screen area.
                self.driver.solid(97, 16, 43, 16, 0x18C3)
                self.driver.solid(100, 19, 31, 10, 0xF800)
                self.driver.solid(132, 22, 4, 4, 0xF800)
        return True

    def status(self):
        return {"selected": self.selected, "connected": True,
                "touch_connected": self.touch is not None,
                "battery": self.battery_state or {"voltage": None, "low": False,
                                                 "charging": None,
                                                 "charge_detection": "unavailable"}}
