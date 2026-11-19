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
WATER_AREAS = ("river", "ocean", "deepsea")
FRAME_SIZE = WIDTH * HEIGHT * 2
TOWN_FULL_HOUSES = 14  # 1 starter home + the 13 scheduled construction events.
TOWN_VISIBLE_RESIDENTS = 18
HYBRID_MID_MINUTES = 10 * 1440
HYBRID_MATURE_MINUTES = 30 * 1440


def town_art_alpha(minutes, houses=None):
    """Show exactly the first cottage until another house exists.

    On the device, house growth drives the illustrated town transition.
    Older callers without a world snapshot retain time-based blending.
    """
    if houses is None:
        return min(255, max(0, int(minutes) * 255 // (30 * 1440)))
    return min(255, max(0, (int(houses) - 1) * 255 // (TOWN_FULL_HOUSES - 1)))


def hybrid_art_frames(minutes):
    """Three illustrated ages, streamed as two RGB565 frames at a time."""
    minute = max(0, int(minutes))
    if minute < HYBRID_MID_MINUTES:
        return ("assets/hybrid-young.dat", "assets/hybrid-mid.dat",
                minute * 255 // HYBRID_MID_MINUTES)
    return ("assets/hybrid-mid.dat", "assets/hybrid-mature.dat",
            min(255, (minute - HYBRID_MID_MINUTES) * 255 //
                (HYBRID_MATURE_MINUTES - HYBRID_MID_MINUTES)))


def town_people(count, tick, tilt_x=0, tilt_y=0):
    """Deterministic 1x3 pedestrians along the town's winding central path."""
    positions = []
    for i in range(min(TOWN_VISIBLE_RESIDENTS, max(0, int(count)))):
        phase = (tick + i * 7) % 24
        step = phase if phase < 12 else 24 - phase
        x = 93 + (i * 19) % 45 + step + tilt_x
        y = 157 + (i * 29) % 49 + ((tick // 5 + i) % 3) + tilt_y
        positions.append((x, y))
    return positions


def hybrid_people(count, tick, tilt_x=0, tilt_y=0):
    """Walk on the western terraces; the lake occupies the eastern foreground."""
    positions = []
    for i in range(min(TOWN_VISIBLE_RESIDENTS, max(0, int(count)))):
        phase = (tick + i * 7) % 24
        step = phase if phase < 12 else 24 - phase
        x = 40 + (i * 17) % 50 + step + tilt_x
        y = 108 + (i * 23) % 56 + ((tick // 5 + i) % 3) + tilt_y
        positions.append((x, y))
    return positions


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


def ambience_row(data, phase):
    """Warm dawn/sunset or dim blue night, without an LCD framebuffer."""
    if phase not in ("dawn", "dusk", "night", "lights_out"):
        return data
    output = bytearray(len(data))
    for i in range(0, len(data), 2):
        color = (data[i] << 8) | data[i + 1]
        red, green, blue = (color >> 11) & 31, (color >> 5) & 63, color & 31
        if phase == "dawn":
            red, green, blue = min(31, red * 108 // 100 + 1), green * 93 // 100, blue * 79 // 100
        elif phase == "dusk":
            red, green, blue = min(31, red * 105 // 100 + 2), green * 72 // 100, blue * 65 // 100
        elif phase == "night":
            red, green, blue = red * 36 // 100, green * 40 // 100, min(31, blue * 65 // 100 + 1)
        else:
            red, green, blue = red * 17 // 100, green * 18 // 100, blue * 27 // 100
        value = (red << 11) | (green << 5) | blue
        output[i], output[i + 1] = value >> 8, value & 255
    return output


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
    GESTURES = {1: "swipe_up", 2: "swipe_down", 3: "swipe_left",
                4: "swipe_right", 5: "tap", 11: "double_tap",
                12: "long_press"}

    def __init__(self, i2c, reset_pin=None):
        self.i2c = i2c
        if reset_pin is not None:
            reset_pin.value(0)
            getattr(time, "sleep_ms", lambda ms: time.sleep(ms / 1000))(12)
            reset_pin.value(1)
        if self.ADDRESS not in i2c.scan():
            raise OSError("CST816S not found on I2C")
        self.was_down = False
        self.start = None
        self.last_point = None
        self.reported = False
        self.ignore_late_gesture = False

    def poll_event(self):
        """Read documented gesture/finger/coordinate registers at 0x01..0x06.

        Fallback swipe detection uses finger-down/move/up positions. A touch is
        not treated as a tap at press time, so swiping cannot switch a world
        accidentally before it is recognized. Physical tuning is pending.
        """
        data = self.i2c.readfrom_mem(self.ADDRESS, 0x01, 6)
        gesture = self.GESTURES.get(data[0])
        down = (data[1] & 0x0f) == 1
        x = ((data[2] & 15) << 8) | data[3]
        y = ((data[4] & 15) << 8) | data[5]
        valid = x < WIDTH and y < HEIGHT
        if down:
            if not self.was_down:
                self.start = (x, y) if valid else None
                self.reported = False
                self.ignore_late_gesture = False
            if valid:
                self.last_point = (x, y)
            self.was_down = True
            if gesture and not self.reported:
                self.reported = True
                return gesture
            return None
        if self.was_down:
            self.was_down = False
            self.ignore_late_gesture = True
            if self.reported:
                self.reported = False
                return None
            if gesture:
                return gesture
            if self.start is None or self.last_point is None:
                return None
            dx = self.last_point[0] - self.start[0]
            dy = self.last_point[1] - self.start[1]
            if abs(dx) >= 36 and abs(dx) > abs(dy) * 1.3:
                return "swipe_left" if dx < 0 else "swipe_right"
            if abs(dy) >= 36 and abs(dy) > abs(dx) * 1.3:
                return "swipe_up" if dy < 0 else "swipe_down"
            return "tap"
        if gesture and not self.ignore_late_gesture:
            self.ignore_late_gesture = True
            return gesture
        if not gesture:
            self.ignore_late_gesture = False
        return None


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
        self.water_area = "river"
        self.touch = None
        if i2c is not None:
            try:
                self.touch = CST816Touch(i2c, touch_reset_pin)
            except (OSError, ValueError):
                pass
        self.battery = battery
        self.battery_state = None
        self.last_draw_at = 0
        self.visible = True
        self.brightness_setting = 65
        self.animation_tick = 0
        self.particles = []
        self.people = []
        self.info_frames = 0
        self.shake_last_id = None
        self.shake_frames = 0
        self.lighting_phase = "day"

    def choose(self, ident):
        if ident not in WORLD_IDS:
            raise ValueError("Unknown world ID")
        self.selected = ident

    def choose_water_area(self, ident):
        if ident not in WATER_AREAS:
            raise ValueError("Unknown water area")
        self.water_area = ident

    def next_world(self):
        self.selected = WORLD_IDS[(WORLD_IDS.index(self.selected) + 1) % len(WORLD_IDS)]
        return self.selected

    def poll_touch(self, engine=None):
        """Return an action describing the touch; engine remains single owner."""
        if self.touch is None:
            return None
        event = self.touch.poll_event()
        if event == "swipe_left":
            return ("world", self.next_world())
        if event == "swipe_right":
            self.selected = WORLD_IDS[(WORLD_IDS.index(self.selected) - 1) % len(WORLD_IDS)]
            return ("world", self.selected)
        if event in ("swipe_up", "swipe_down") and self.selected == "aquarium":
            direction = 1 if event == "swipe_up" else -1
            target = WATER_AREAS[(WATER_AREAS.index(self.water_area) + direction) % len(WATER_AREAS)]
            if (engine is not None and
                engine.worlds["aquarium"]["water_areas"][target]["unlocked"]):
                self.choose_water_area(target)
                return ("area", target)
            return None
        if event in ("tap", "double_tap"):
            return ("tap", self.selected)
        if event == "long_press":
            return ("info", self.selected)
        return None

    def show(self, minutes, force=False, world=None):
        """Draw once on mode/day changes or scheduled refresh; no frame buffer."""
        if not self.visible:
            return False
        early_path, mature_path, alpha = self._art_frames(minutes, world)
        if not (valid_frame(early_path) and valid_frame(mature_path)):
            return False
        with open(early_path, "rb") as early, open(mature_path, "rb") as mature:
            self.driver.window(0, 0, WIDTH, HEIGHT)
            self.driver.start_pixels()
            try:
                for _ in range(HEIGHT):
                    a, b = early.read(WIDTH * 2), mature.read(WIDTH * 2)
                    if len(a) != WIDTH * 2 or len(b) != WIDTH * 2:
                        raise OSError("Truncated display asset")
                    self.driver.write_pixels(ambience_row(blend_row(a, b, alpha),
                                                         self.lighting_phase))
            finally:
                self.driver.stop_pixels()
        self.particles = []
        self.people = []
        self.info_frames = 0
        self.last_draw_at = int(minutes)
        if self.selected == "city" and self.lighting_phase == "night":
            self._town_lamps(world)
        if self.battery is not None:
            self.battery_state = self.battery.status()
            if self.battery_state["low"]:
                # Tiny red indicator in a safe central screen area.
                self.driver.solid(97, 16, 43, 16, 0x18C3)
                self.driver.solid(100, 19, 31, 10, 0xF800)
                self.driver.solid(132, 22, 4, 4, 0xF800)
            elif self.battery_state.get("charging") is True:
                # The motif appears only when a real charge detector is fitted.
                self.driver.solid(97, 16, 43, 16, 0x0427)
                self.driver.solid(100, 19, 31, 10, 0x05E0)
                self.driver.solid(132, 22, 4, 4, 0x05E0)
        return True

    def _town_lamps(self, world):
        """Light the starter cottage and more streetlamps as the town grows."""
        homes = world.get("houses", 1) if world else 1
        # The only home at birth gets two warmly lit windows.
        for x, y in ((49, 119), (77, 119)):
            self.driver.solid(x, y, 2, 2, 0xFD20)
            self.driver.solid(x, y, 1, 1, 0xFFDE)
        # More windows gradually light up with each saved house milestone.
        windows = ((35, 91), (77, 96), (111, 110), (162, 111),
                   (211, 101), (218, 124), (153, 89), (130, 132),
                   (60, 112), (190, 138), (102, 150), (145, 150))
        for x, y in windows[:max(0, min(12, homes - 1))]:
            self.driver.solid(x, y, 2, 2, 0xFDE0)
            self.driver.solid(x, y, 1, 1, 0xFFFF)
        for x, y in ((119, 158), (141, 171), (93, 192),
                     (156, 192), (124, 215), (79, 174))[:max(0, min(6, homes - 1))]:
            self.driver.solid(x, y, 1, 7, 0x3186)   # slender lamppost
            self.driver.solid(x - 1, y - 2, 3, 2, 0xFCA0)
            self.driver.solid(x, y - 2, 1, 1, 0xFFE0)

    def set_lighting(self, phase, minutes, world=None):
        if phase not in ("dawn", "day", "dusk", "night", "lights_out"):
            raise ValueError("Unknown day phase")
        if phase == self.lighting_phase:
            return False
        self.lighting_phase = phase
        if self.visible:
            self.show(minutes, force=True, world=world)
        return True

    def set_visible(self, enabled, minutes, world=None):
        """Safe scheduled screen blanking without disabling Wi-Fi or USB.

        Deep sleep uses a separate opt-in hardware path. The backlight can
        always recover on a new trusted daytime clock sync.
        """
        enabled = bool(enabled)
        if enabled == self.visible:
            return False
        if enabled:
            self.visible = True
            self.driver.set_brightness(self.brightness_setting)
            self.show(minutes, force=True, world=world)
        else:
            # A short, reversible dusk transition before backlight-off.
            for brightness in (40, 20, 8, 0):
                self.driver.set_brightness(brightness)
                getattr(time, "sleep_ms", lambda ms: time.sleep(ms / 1000))(35)
            self.visible = False
            self.particles = []
            self.people = []
        return True

    def set_brightness(self, percent):
        # Never allow a remotely persisted 0% backlight to hide the only UI.
        if isinstance(percent, bool) or not isinstance(percent, int) or not 10 <= percent <= 100:
            raise ValueError("Brightness must be 10..100 percent")
        self.brightness_setting = percent
        if self.visible:
            self.driver.set_brightness(percent)

    def _art_frames(self, minutes, world=None):
        if self.selected == "hybrid":
            return hybrid_art_frames(minutes)
        ident = ("aquarium" if self.water_area == "ocean" else self.water_area) \
            if self.selected == "aquarium" else self.selected
        return ("assets/%s-young.dat" % ident,
                "assets/%s-mature.dat" % ident,
                town_art_alpha(minutes, world.get("houses") if world and self.selected == "city" else None))

    def _restore_patch(self, young, mature, rect, alpha):
        x, y, size, _ = rect
        self.driver.window(x, y, size, size)
        self.driver.start_pixels()
        try:
            for line in range(size):
                offset = ((y + line) * WIDTH + x) * 2
                young.seek(offset)
                mature.seek(offset)
                self.driver.write_pixels(ambience_row(blend_row(young.read(size * 2),
                                                                mature.read(size * 2), alpha),
                                                     self.lighting_phase))
        finally:
            self.driver.stop_pixels()

    def _restore_person(self, young, mature, point, alpha):
        """Restore the exact three underlying RGB565 pixels after a step."""
        x, y = point
        self.driver.window(x, y, 1, 3)
        self.driver.start_pixels()
        try:
            for line in range(3):
                offset = ((y + line) * WIDTH + x) * 2
                young.seek(offset)
                mature.seek(offset)
                self.driver.write_pixels(ambience_row(blend_row(young.read(2),
                                                                mature.read(2), alpha),
                                                     self.lighting_phase))
        finally:
            self.driver.stop_pixels()

    def animate(self, minutes, motion=None, world=None):
        """Animate town pedestrians or ambient particles with small patch restores.

        Motion is intentionally decorative: no changes to simulation state.
        A few hundred SPI bytes per tick are much cheaper than a fresh frame.
        """
        if not self.visible:
            return False
        if self.info_frames:
            self.info_frames -= 1
            if not self.info_frames:
                self.show(minutes, force=True)
            return True
        early_path, mature_path, alpha = self._art_frames(minutes, world)
        if not (valid_frame(early_path) and valid_frame(mature_path)):
            return False
        with open(early_path, "rb") as early, open(mature_path, "rb") as mature:
            for rect in self.particles:
                self._restore_patch(early, mature, rect, alpha)
            for point in self.people:
                self._restore_person(early, mature, point, alpha)
        self.animation_tick += 1
        tilt_x, tilt_y = 0, 0
        if motion is not None:
            effect = motion.snapshot()
            if effect.get("connected"):
                tilt_x = int(max(-1, min(1, effect.get("tilt_x", 0))) * 8)
                tilt_y = int(max(-1, min(1, effect.get("tilt_y", 0))) * 8)
                shake_id = effect.get("shake_id", 0)
                if (effect.get("shake_enabled") and self.shake_last_id is not None
                    and shake_id > self.shake_last_id):
                    self.shake_frames = 4
                self.shake_last_id = shake_id
        if self.selected == "city":
            # Actual town population is the source of truth; a visual cap keeps
            # the display legible as the population grows toward 40 residents.
            self.particles = []
            count = world.get("residents", 2) if world else 2
            self.people = town_people(count, self.animation_tick, tilt_x, tilt_y)
            shirts = (0x19A7, 0xC1E6, 0x3A2E, 0x89A4)
            for i, (x, y) in enumerate(self.people):
                self.driver.solid(x, y, 1, 1, 0xFFBE)  # head
                self.driver.solid(x, y + 1, 1, 1, shirts[i % len(shirts)])
                self.driver.solid(x, y + 2, 1, 1, 0x2104)  # feet
            if self.lighting_phase == "night":
                self._town_lamps(world)
            return True
        self.people = []
        watery = self.selected == "aquarium"
        colour = (0xC7DF if watery else 0xFFDF if self.selected == "fantasy"
                  else 0xF6A4 if self.selected == "forest" else 0xE7B1)
        if self.shake_frames:
            colour = 0xFFFF
            self.shake_frames -= 1
        # Keep all 4×4 sprites away from circular screen corners.
        self.particles = [
            (72 + (i * 31) % 95 + tilt_x,
             65 + ((i * 43 - self.animation_tick * (4 if watery else 1)) % 125) + tilt_y,
             4, colour)
            for i in range(4)
        ]
        for x, y, size, value in self.particles:
            self.driver.solid(x, y, size, size, value)
        if self.selected in ("hybrid", "fantasy"):
            count = world.get("residents", 0) if world else 0
            self.people = hybrid_people(count, self.animation_tick, tilt_x, tilt_y) \
                if self.selected == "hybrid" else town_people(count, self.animation_tick, tilt_x, tilt_y)
            shirts = (0x19A7, 0xC1E6, 0x3A2E, 0x89A4)
            for i, (x, y) in enumerate(self.people):
                self.driver.solid(x, y, 1, 1, 0xFFBE)
                self.driver.solid(x, y + 1, 1, 1, shirts[i % len(shirts)])
                self.driver.solid(x, y + 2, 1, 1, 0x2104)
        return True

    def show_info(self, minutes, world=None):
        """Long-press displays a compact, approximate four-segment gauge."""
        if not self.show(minutes, force=True, world=world):
            return False
        voltage = self.battery_state.get("voltage") if self.battery_state else None
        bars = sum(voltage >= cutoff for cutoff in (3.5, 3.65, 3.85, 4.05)) \
            if isinstance(voltage, (int, float)) else 0
        self.driver.solid(65, 91, 110, 58, 0x18E3)
        self.driver.solid(81, 103, 80, 35, 0xFFFF)
        self.driver.solid(161, 113, 7, 16, 0xFFFF)
        for i in range(4):
            self.driver.solid(85 + i * 18, 107, 14, 27,
                              0x05E0 if i < bars else 0x4208)
        self.info_frames = 3
        return True

    def status(self):
        return {"selected": self.selected, "connected": True,
                "water_area": self.water_area,
                "screen_on": self.visible,
                "brightness": self.brightness_setting,
                "animation_tick": self.animation_tick,
                "day_phase": self.lighting_phase,
                "touch_connected": self.touch is not None,
                "battery": self.battery_state or {"voltage": None, "low": False,
                                                 "charging": None,
                                                 "charge_detection": "unavailable"}}
