"""GC9A01A round LCD + CST816S touch for Waveshare ESP32-S3-Touch-LCD-1.28.

Device RGB565 artwork uses native blending and up to eight cached frames
when MicroPython and memory are available. A scanline path supports smaller
heaps and PC tests. Display orientation and touch require device validation.

Pin map: https://docs.waveshare.com/ESP32-S3-Touch-LCD-1.28
GC9A01A initialization command data adapted from Adafruit_GC9A01A (BSD).
See THIRD_PARTY_NOTICES.md for attribution.
"""

import time
from scene_events import active_visit, visitor_frames, visitor_position

try:
    import micropython
except ImportError:
    micropython = None


_compose_pixels = None
_copy_region = None
_fill_region = None
if micropython is not None:
    @micropython.viper
    def _copy_region(destination, frame, left: int, top: int, width: int, height: int):
        output = ptr8(destination)
        source = ptr8(frame)
        stride = width * 2
        for row in range(height):
            origin = ((top + row) * 240 + left) * 2
            offset = row * stride
            for column in range(stride):
                output[offset + column] = source[origin + column]

    @micropython.viper
    def _fill_region(destination, stride: int, x: int, y: int,
                     width: int, height: int, color: int):
        output = ptr8(destination)
        for row in range(height):
            offset = ((y + row) * stride + x) * 2
            for column in range(width):
                output[offset + column * 2] = color >> 8
                output[offset + column * 2 + 1] = color & 255

    @micropython.viper
    def _compose_pixels(destination, early, late, settings):
        """Blend and light RGB565 pixels using native integer arithmetic."""
        output = ptr8(destination)
        first = ptr8(early)
        second = ptr8(late)
        length = int(len(destination))
        alpha = int(settings[0])
        phase = int(settings[1])
        for offset in range(0, length, 2):
            a = (first[offset] << 8) | first[offset + 1]
            b = (second[offset] << 8) | second[offset + 1]
            red = (((a >> 11) & 31) * (255 - alpha) +
                   ((b >> 11) & 31) * alpha + 127) // 255
            green = (((a >> 5) & 63) * (255 - alpha) +
                     ((b >> 5) & 63) * alpha + 127) // 255
            blue = ((a & 31) * (255 - alpha) + (b & 31) * alpha + 127) // 255
            if phase == 1:
                red = red * 108 // 100 + 1
                green = green * 93 // 100
                blue = blue * 79 // 100
            elif phase == 2:
                red = red * 105 // 100 + 2
                green = green * 72 // 100
                blue = blue * 65 // 100
            elif phase == 3:
                red = red * 36 // 100
                green = green * 40 // 100
                blue = blue * 65 // 100 + 1
            elif phase == 4:
                red = red * 17 // 100
                green = green * 18 // 100
                blue = blue * 27 // 100
            if red > 31:
                red = 31
            color = (red << 11) | (green << 5) | blue
            output[offset] = color >> 8
            output[offset + 1] = color & 255

WIDTH = 240
HEIGHT = 240
WORLD_IDS = ("nature", "city", "hybrid", "fantasy", "forest", "aquarium")
WATER_AREAS = ("river", "ocean", "deepsea")
FRAME_SIZE = WIDTH * HEIGHT * 2
TOWN_FULL_HOUSES = 14  # 1 starter home + the 13 scheduled construction events.
TOWN_VISIBLE_RESIDENTS = 18
HYBRID_MID_MINUTES = 10 * 1440
HYBRID_MATURE_MINUTES = 30 * 1440
# Landmark pixels shared by all three matched hybrid backgrounds.
# These are inside the circular LCD and on the same land/water features.
HYBRID_LEAVES = ((54, 45), (72, 51), (84, 61))
HYBRID_LAKE = ((150, 161), (177, 169), (190, 183), (165, 197))
HYBRID_FALLS = ((132, 119), (140, 138))
# Landmarks checked against the matching 240x240 young/mature illustrations.
# Ripples drift sideways; waterfall drops move downward. Aquarium zones are
# entirely underwater and use rising bubbles instead of surface ripples.
WATER_RIPPLES = {
    "nature": ((176, 113), (186, 137)),
    "city": ((174, 195), (177, 202), (181, 189)),
    "hybrid": HYBRID_LAKE,
    "fantasy": ((112, 130), (154, 127)),
    "forest": ((104, 210), (140, 219)),
}
WATER_FALLS = {
    "nature": ((189, 174), (194, 188)),
    "city": ((181, 161),),
    "hybrid": HYBRID_FALLS,
    "fantasy": ((131, 162), (131, 188), (128, 209)),
    "forest": ((120, 137), (125, 164), (121, 185)),
}
UNDERWATER_BUBBLES = ((75, 110), (103, 169), (158, 142), (184, 94),
                       (123, 195), (52, 137))


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


def hybrid_ambient_particles(tick, phase="day", weather="sunny",
                             tilt_x=0, tilt_y=0, shaking=False):
    """Subtle leaf sway and water shimmer, without repainting the scenery.

    Each result is (x, y, square size, RGB565). Animate() restores the
    underlying RGB565 pixels before redrawing the next positions.
    """
    if phase == "lights_out":
        return []
    windy = weather in ("windy", "rain")
    pace = 2 if windy else 4
    bright = phase in ("day", "dawn")
    leaf_color = 0xB6D4 if bright else 0x3349
    water_color = 0xD7FE if bright else 0x42B5
    falls_color = 0xBFFF if bright else 0x3A53
    if shaking:
        leaf_color = water_color = falls_color = 0xFFFF
    particles = []
    for index, (base_x, base_y) in enumerate(HYBRID_LEAVES):
        sway = ((tick // pace + index) % 3) - 1
        particles.append((base_x + sway * (2 if windy else 1) + tilt_x,
                          base_y + tilt_y, 2, leaf_color))
    for index, (base_x, base_y) in enumerate(HYBRID_LAKE):
        shimmer = ((tick + 2 * index) % 3) - 1
        particles.append((base_x + shimmer + tilt_x,
                          base_y + (tick + index) % 2 + tilt_y, 2, water_color))
    for index, (base_x, base_y) in enumerate(HYBRID_FALLS):
        particles.append((base_x + tilt_x,
                          base_y + (tick + index * 3) % 3 + tilt_y,
                          1, falls_color))
    return particles


def water_ambient_particles(art_id, tick, phase="day", weather="sunny",
                            tilt_x=0, tilt_y=0, shaking=False, growth=1):
    """Move tiny highlights along the painted water, not over arbitrary land.

    `growth` is the illustrated background cross-fade (0..1). Nature's
    youngest meadow has a brown stream bed, so blue water emerges gradually.
    """
    if phase == "lights_out" or (art_id == "nature" and growth < .3):
        return []
    bright = phase in ("day", "dawn")
    ripple = 0xD7FE if bright else 0x42B5
    falls = 0xBFFF if bright else 0x3A53
    if art_id == "deepsea":
        ripple = 0x6558 if bright else 0x3254
    if shaking:
        ripple = falls = 0xFFFF
    pace = 2 if weather in ("rain", "windy") else 1
    particles = []
    if art_id in ("aquarium", "river", "deepsea"):
        # The whole canvas is water. Rise within six narrow bubble columns.
        for i, (x, y) in enumerate(UNDERWATER_BUBBLES):
            particles.append((x + (tick + i) % 3 - 1 + tilt_x,
                              y - (tick * pace * 2 + i * 3) % 22 + tilt_y,
                              1 if i % 2 else 2, ripple))
        for i, (x, y) in enumerate(((105, 35), (152, 46), (178, 63))):
            particles.append((x + (tick + i * 2) % 5 - 2 + tilt_x,
                              y + tilt_y, 1, ripple))
        return particles
    for i, (x, y) in enumerate(WATER_RIPPLES.get(art_id, ())):
        particles.append((x + (tick * pace + i * 2) % 5 - 2 + tilt_x,
                          y + (tick + i) % 2 + tilt_y, 2, ripple))
    if art_id != "nature" or growth >= .55:
        for i, (x, y) in enumerate(WATER_FALLS.get(art_id, ())):
            particles.append((x + tilt_x,
                              y + (tick * pace + i * 3) % 6 + tilt_y,
                              1, falls))
    return particles


def nature_ambient_particles(tick, phase="day", weather="sunny",
                             tilt_x=0, tilt_y=0, shaking=False, growth=1):
    """Leaves, butterflies, distant birds, fireflies and the growing river."""
    if phase == "lights_out":
        return []
    windy = weather in ("windy", "rain")
    bright = phase in ("day", "dawn")
    color_leaf = 0xC706 if bright else 0x4389
    color_butterfly = 0xFDF1 if bright else 0xB3B7
    color_bird = 0xFFFF if bright else 0x9D3D
    if shaking:
        color_leaf = color_butterfly = color_bird = 0xFFFF
    # The young illustration contains one small sapling at this coordinate.
    particles = [(111 + ((tick // (2 if windy else 4)) % 3 - 1) + tilt_x,
                  66 + tilt_y, 1, color_leaf)]
    if growth >= .2:
        for i, (x, y) in enumerate(((68, 54), (103, 39), (149, 69))):
            sway = (tick // (2 if windy else 4) + i) % 3 - 1
            particles.append((x + sway * (2 if windy else 1) + tilt_x,
                              y + tilt_y, 2, color_leaf))
        for i, (x, y) in enumerate(((67, 70), (97, 75), (138, 84))):
            # A few leaves float down from the canopy toward the meadow.
            particles.append((x + (tick * (2 if windy else 1) + i) % 7 - 3 + tilt_x,
                              y + (tick + i * 7) % 19 + tilt_y,
                              1, color_leaf))
        for i in range(3):
            # Flower-height butterfly tracks stay on the island's grassy top.
            x = 58 + i * 40 + (tick * (2 if windy else 1) + i * 5) % 19
            y = 116 + i * 8 + (tick + i * 3) % 5 - 2
            particles.append((x + tilt_x, y + tilt_y, 2, color_butterfly))
        for i in range(2):
            x = 37 + i * 105 + (tick + i * 3) % 23
            y = 34 + i * 5 + (tick + i) % 3 - 1
            particles.append((x + tilt_x, y + tilt_y, 1, color_bird))
    if phase in ("night", "dusk"):
        for i, (x, y) in enumerate(((77, 146), (127, 114), (163, 124),
                                    (111, 153))):
            firefly = 0xFFE0 if (tick + i) % 3 else 0x8B60
            particles.append((x + (tick + i) % 3 - 1 + tilt_x,
                              y + (tick + 2 * i) % 3 - 1 + tilt_y,
                              1, 0xFFFF if shaking else firefly))
    particles.extend(water_ambient_particles("nature", tick, phase, weather,
                                              tilt_x, tilt_y, shaking, growth))
    return particles


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
            (0x8F, b"\xff"), (0xB6, b"\x00\x00"), (0x36, b"\x40"),
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

    def __init__(self, i2c, reset_pin=None, irq_pin=None, clock_ms=None):
        self.i2c = i2c
        if reset_pin is not None:
            reset_pin.value(0)
            getattr(time, "sleep_ms", lambda ms: time.sleep(ms / 1000))(12)
            reset_pin.value(1)
            getattr(time, "sleep_ms", lambda ms: time.sleep(ms / 1000))(50)
        if self.ADDRESS not in i2c.scan():
            raise OSError("CST816S not found on I2C")
        i2c.writeto_mem(self.ADDRESS, 0xFE, b"\x01")

        i2c.writeto_mem(self.ADDRESS, 0xFA, b"\x41")
        self.was_down = False
        self.start = None
        self.last_point = None
        self.started_at = 0
        self.start_gesture = 0
        self.ignore_late_gesture = True
        self.irq_sequence = 0
        self.polled_irq_sequence = 0
        self.irq_pin = irq_pin
        self.last_event_at = None
        self.now_ms = clock_ms or getattr(time, "ticks_ms", lambda: int(time.time() * 1000))
        self.diff_ms = getattr(time, "ticks_diff", lambda end, start: end - start)
        if irq_pin is not None:
            irq_pin.irq(trigger=2, handler=self._on_touch_irq)

    def _on_touch_irq(self, _pin):
        self.irq_sequence = (self.irq_sequence + 1) & 0xffff

    def poll_event(self):
        """Emit one event after release, using movement before the gesture latch."""
        sequence = self.irq_sequence
        pending = sequence != self.polled_irq_sequence
        self.polled_irq_sequence = sequence
        data = self.i2c.readfrom_mem(self.ADDRESS, 0x01, 6)
        code = data[0]
        gesture = self.GESTURES.get(code)
        down = (data[1] & 0x0f) == 1
        x = ((data[2] & 15) << 8) | data[3]
        y = ((data[4] & 15) << 8) | data[5]
        valid = x < WIDTH and y < HEIGHT
        now = self.now_ms()
        if down:
            if not self.was_down:
                self.start = (x, y) if valid else None
                self.start_gesture = code
                self.started_at = now
            if valid:
                self.last_point = (x, y)
            self.was_down = True
            return None
        if self.was_down:
            self.was_down = False
            self.ignore_late_gesture = True
            self.last_event_at = now
            if self.start is None or self.last_point is None:
                return None
            # Only use the release coordinate when the controller marks it UP.
            # An all-zero idle report contains no endpoint.
            if valid and (data[2] >> 6) == 1:
                self.last_point = (x, y)
            dx = self.last_point[0] - self.start[0]
            dy = self.last_point[1] - self.start[1]
            if abs(dx) >= 36 and abs(dx) > abs(dy) * 1.3:
                return "swipe_left" if dx < 0 else "swipe_right"
            if abs(dy) >= 36 and abs(dy) > abs(dx) * 1.3:
                return "swipe_up" if dy < 0 else "swipe_down"
            elapsed = self.diff_ms(now, self.started_at)
            if max(abs(dx), abs(dy)) < 18:
                if elapsed >= 650:
                    return "long_press"
                if gesture and code != self.start_gesture:
                    return gesture
                return "tap"
            return None
        # Fast gestures can finish between polls. An IRQ distinguishes a new
        # contact from the unchanged direction code left in the IC's register.
        if self.irq_pin is not None:
            if not pending:
                return None
            if self.last_event_at is not None and self.diff_ms(now, self.last_event_at) < 250:
                return None
            self.last_event_at = now
            return gesture
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
    def __init__(self, driver, i2c=None, touch_reset_pin=None, battery=None,
                 touch_irq_pin=None):
        self.driver = driver
        self.selected = "nature"
        self.water_area = "river"
        self.touch = None
        if i2c is not None:
            try:
                self.touch = CST816Touch(i2c, touch_reset_pin, touch_irq_pin)
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
        self.frame_cache = {} if _compose_pixels is not None else None
        self.visitor_rect = None
        self.visitor_kind = None
        self.visitor_frames = None
        self.animation_buffer = bytearray()

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
        """Draw the current world, using a native full-frame path when available."""
        if not self.visible:
            return False
        early_path, mature_path, alpha = self._art_frames(minutes, world)
        frame = self._get_frame(early_path, mature_path, alpha)
        if frame is None and not (valid_frame(early_path) and valid_frame(mature_path)):
            return False
        self.driver.window(0, 0, WIDTH, HEIGHT)
        self.driver.start_pixels()
        try:
            if frame is not None:
                self.driver.write_pixels(frame)
            else:
                with open(early_path, "rb") as early, open(mature_path, "rb") as mature:
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
        self.visitor_rect = None
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

    def invalidate_frames(self):
        if self.frame_cache is not None:
            self.frame_cache.clear()

    def _get_frame(self, early_path, mature_path, alpha):
        if self.frame_cache is None:
            return None
        scene = self.water_area if self.selected == "aquarium" else self.selected
        signature = (early_path, mature_path, alpha, self.lighting_phase)
        cached = self.frame_cache.get(scene)
        if cached is not None and cached[0] == signature:
            return cached[1]
        if not (valid_frame(early_path) and valid_frame(mature_path)):
            return None
        try:
            with open(early_path, "rb") as early, open(mature_path, "rb") as mature:
                a = early.read(FRAME_SIZE)
                b = mature.read(FRAME_SIZE)
            if len(a) != FRAME_SIZE or len(b) != FRAME_SIZE:
                raise OSError("Truncated display asset")
            frame = cached[1] if cached is not None else bytearray(FRAME_SIZE)
            phase = ("day", "dawn", "dusk", "night", "lights_out").index(self.lighting_phase)
            _compose_pixels(frame, a, b, (alpha, phase))
            self.frame_cache[scene] = (signature, frame)
            return frame
        except MemoryError:
            self.frame_cache = None
            return None

    def warm_next_frame(self, engine):
        """Prepare one visible world's background between input/network polls."""
        if self.frame_cache is None or not self.visible:
            return False
        selected, water_area = self.selected, self.water_area
        try:
            for ident in WORLD_IDS:
                world = engine.worlds[ident]
                areas = WATER_AREAS if ident == "aquarium" else (None,)
                for area in areas:
                    if area is not None and not world["water_areas"][area]["unlocked"]:
                        continue
                    self.selected = ident
                    self.water_area = area or water_area
                    early, mature, alpha = self._art_frames(world["minutes"], world)
                    scene = area or ident
                    signature = (early, mature, alpha, self.lighting_phase)
                    cached = self.frame_cache.get(scene)
                    if cached is None or cached[0] != signature:
                        if self._get_frame(early, mature, alpha) is not None:
                            return True
                        if self.frame_cache is None:
                            return False
            return False
        finally:
            self.selected, self.water_area = selected, water_area

    def _lamp_rectangles(self, world):
        homes = world.get("houses", 1) if world else 1
        rectangles = []
        for x, y in ((49, 119), (77, 119)):
            rectangles.extend(((x, y, 2, 2, 0xFD20), (x, y, 1, 1, 0xFFDE)))
        windows = ((35, 91), (77, 96), (111, 110), (162, 111),
                   (211, 101), (218, 124), (153, 89), (130, 132),
                   (60, 112), (190, 138), (102, 150), (145, 150))
        for x, y in windows[:max(0, min(12, homes - 1))]:
            rectangles.extend(((x, y, 2, 2, 0xFDE0), (x, y, 1, 1, 0xFFFF)))
        for x, y in ((119, 158), (141, 171), (93, 192),
                     (156, 192), (124, 215), (79, 174))[:max(0, min(6, homes - 1))]:
            rectangles.extend(((x, y, 1, 7, 0x3186),
                               (x - 1, y - 2, 3, 2, 0xFCA0),
                               (x, y - 2, 1, 1, 0xFFE0)))
        return rectangles

    def _town_lamps(self, world):
        for rectangle in self._lamp_rectangles(world):
            self.driver.solid(*rectangle)

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

    def _restore_patch(self, young, mature, rect, alpha, height=None):
        x, y, size, _ = rect
        height = size if height is None else height
        self.driver.window(x, y, size, height)
        self.driver.start_pixels()
        try:
            for line in range(height):
                offset = ((y + line) * WIDTH + x) * 2
                young.seek(offset)
                mature.seek(offset)
                self.driver.write_pixels(ambience_row(blend_row(young.read(size * 2),
                                                                mature.read(size * 2), alpha),
                                                     self.lighting_phase))
        finally:
            self.driver.stop_pixels()

    def _restore_cached(self, frame, x, y, width, height):
        left, top = max(0, x), max(0, y)
        right, bottom = min(WIDTH, x + width), min(HEIGHT, y + height)
        if left >= right or top >= bottom:
            return
        self.driver.window(left, top, right - left, bottom - top)
        self.driver.start_pixels()
        view = memoryview(frame)
        try:
            for row in range(top, bottom):
                offset = (row * WIDTH + left) * 2
                self.driver.write_pixels(view[offset:offset + (right - left) * 2])
        finally:
            self.driver.stop_pixels()

    def _visitor_rectangles(self, world):
        if world is None:
            return []
        visit = active_visit(world, self.water_area if self.selected == "aquarium" else None)
        if visit is None or self.lighting_phase == "lights_out":
            self.visitor_rect = None
            return []
        if self.visitor_kind != visit["id"]:
            self.visitor_kind = visit["id"]
            self.visitor_frames = visitor_frames(visit["id"])
        pixels = self.visitor_frames[self.animation_tick % 2]
        x, y = visitor_position(visit, self.animation_tick)
        left = min(item[0] for item in pixels)
        top = min(item[1] for item in pixels)
        right = max(item[0] + item[2] for item in pixels)
        bottom = max(item[1] + item[3] for item in pixels)
        self.visitor_rect = (x + left, y + top, right - left, bottom - top)
        return [(x + dx, y + dy, width, height, color)
                for dx, dy, width, height, color in pixels]

    def _paint_animation(self, frame, old_regions, rectangles):
        regions = old_regions + [item[:4] for item in rectangles]
        if not regions:
            return
        left = max(0, min(item[0] for item in regions))
        top = max(0, min(item[1] for item in regions))
        right = min(WIDTH, max(item[0] + item[2] for item in regions))
        bottom = min(HEIGHT, max(item[1] + item[3] for item in regions))
        width, height = right - left, bottom - top
        if width <= 0 or height <= 0:
            return
        length = width * height * 2
        try:
            if len(self.animation_buffer) < length:
                self.animation_buffer = bytearray(length)
            buffer = memoryview(self.animation_buffer)[:length]
        except MemoryError:
            for x, y, w, h in old_regions:
                self._restore_cached(frame, x, y, w, h)
            for rectangle in rectangles:
                self.driver.solid(*rectangle)
            return
        if _copy_region is not None:
            _copy_region(buffer, frame, left, top, width, height)
        else:
            background = memoryview(frame)
            for row in range(height):
                source = ((top + row) * WIDTH + left) * 2
                offset = row * width * 2
                buffer[offset:offset + width * 2] = background[source:source + width * 2]
        for x, y, w, h, color in rectangles:
            x0, y0 = max(left, x), max(top, y)
            x1, y1 = min(right, x + w), min(bottom, y + h)
            if x0 >= x1 or y0 >= y1:
                continue
            if _fill_region is not None:
                _fill_region(buffer, width, x0 - left, y0 - top, x1 - x0, y1 - y0, color)
            else:
                stripe = bytes((color >> 8, color & 255)) * (x1 - x0)
                for row in range(y0, y1):
                    offset = ((row - top) * width + x0 - left) * 2
                    buffer[offset:offset + len(stripe)] = stripe
        self.driver.window(left, top, width, height)
        self.driver.start_pixels()
        try:
            self.driver.write_pixels(buffer)
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
        """Restore and compose moving objects in one dirty rectangle."""
        if not self.visible:
            return False
        if self.info_frames:
            self.info_frames -= 1
            if not self.info_frames:
                self.show(minutes, force=True, world=world)
            return True
        early_path, mature_path, alpha = self._art_frames(minutes, world)
        frame = self._get_frame(early_path, mature_path, alpha)
        old_regions = [(x, y, size, size) for x, y, size, _ in self.particles]
        old_regions.extend((x, y, 1, 3) for x, y in self.people)
        if self.visitor_rect is not None:
            old_regions.append(self.visitor_rect)
        if frame is None:
            if not (valid_frame(early_path) and valid_frame(mature_path)):
                return False
            with open(early_path, "rb") as early, open(mature_path, "rb") as mature:
                for x, y, width, height in old_regions:
                    self._restore_patch(early, mature, (x, y, width, 0), alpha, height)
        self.visitor_rect = None
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
        weather = world.get("weather", "sunny") if world else "sunny"
        if self.selected == "hybrid":
            self.particles = hybrid_ambient_particles(
                self.animation_tick, self.lighting_phase, weather,
                tilt_x, tilt_y, self.shake_frames > 0)
        elif self.selected == "nature":
            self.particles = nature_ambient_particles(
                self.animation_tick, self.lighting_phase, weather,
                tilt_x, tilt_y, self.shake_frames > 0, alpha / 255)
        else:
            art_id = ("aquarium" if self.water_area == "ocean" else self.water_area) \
                if self.selected == "aquarium" else self.selected
            self.particles = water_ambient_particles(
                art_id, self.animation_tick, self.lighting_phase, weather,
                tilt_x, tilt_y, self.shake_frames > 0, alpha / 255)
            if self.selected == "fantasy" and self.lighting_phase != "lights_out":
                self.particles.extend(
                    (53 + (self.animation_tick + i * 5) % 14 + tilt_x,
                     88 + i * 15 + tilt_y, 2, 0xFFFF if self.shake_frames else 0xFFDF)
                    for i in range(2))
        if self.shake_frames:
            self.shake_frames -= 1
        self.people = []
        if self.selected in ("city", "hybrid", "fantasy"):
            count = world.get("residents", 2 if self.selected == "city" else 0) if world else 0
            people = hybrid_people if self.selected == "hybrid" else town_people
            self.people = people(count, self.animation_tick, tilt_x, tilt_y)
        rectangles = [(x, y, size, size, color) for x, y, size, color in self.particles]
        shirts = (0x19A7, 0xC1E6, 0x3A2E, 0x89A4)
        for i, (x, y) in enumerate(self.people):
            rectangles.extend(((x, y, 1, 1, 0xFFBE),
                               (x, y + 1, 1, 1, shirts[i % len(shirts)]),
                               (x, y + 2, 1, 1, 0x2104)))
        if self.selected == "city" and self.lighting_phase == "night":
            rectangles.extend(self._lamp_rectangles(world))
        rectangles.extend(self._visitor_rectangles(world))
        if frame is not None:
            self._paint_animation(frame, old_regions, rectangles)
        else:
            for rectangle in rectangles:
                self.driver.solid(*rectangle)
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
