"""One moon jelly in a quiet tank; no spawning, growth or other animals."""
import math


def rgb(red, green, blue):
    return (red >> 3) << 11 | (green >> 2) << 5 | (blue >> 3)


def background():
    """Build the static RGB565 asset on the PC, in display byte order."""
    frame = bytearray(240 * 240 * 2)
    for y in range(240):
        for x in range(240):
            glow = max(0, 1 - ((x - 112) / 144) ** 2 - ((y - 93) / 165) ** 2)
            color = rgb(int(3 + glow * 5), int(11 + glow * 21), int(25 + glow * 34))
            # A very faint glass arc and a pool of light on the tank floor.
            radius = ((x - 120) ** 2 + (y - 120) ** 2) ** 0.5
            if 108 < radius < 109 and y < 165:
                color = rgb(13, 38, 58)
            if ((x - 120) / 65) ** 2 + ((y - 204) / 7) ** 2 < 1:
                color = rgb(7, 28, 43)
            offset = (y * 240 + x) * 2
            frame[offset] = color >> 8
            frame[offset + 1] = color & 255
    return frame


def jelly_rectangles(tick, tilt_x=0, tilt_y=0):
    """Breathing bell, four gonads and eight softly trailing tentacles."""
    t = tick / 4
    pulse = (math.sin(t * 1.45) + 1) / 2
    cx = 120 + int(math.sin(t * .23) * 15) + tilt_x
    cy = 93 + int(math.sin(t * .38) * 9) + tilt_y
    radius = 24 + int(pulse * 5)
    height = 18 + int((1 - pulse) * 5)
    rectangles = []
    # Tentacles behind the bell: one connected jellyfish, never a shoal.
    for i in range(8):
        root = cx + int((i - 3.5) * radius / 4.3)
        length = 37 + (i * 11) % 24
        for step in range(0, length, 3):
            sway = int(math.sin(t * .9 + step * .11 + i * .7) * (2 + step / 10))
            color = 0x8CDE if i % 2 else 0x5BD8
            rectangles.append((root + sway, cy + step, 1 if i % 2 else 2, 4, color))
    for row in range(height):
        portion = row / height
        half = max(1, int(radius * math.sqrt(max(0, 1 - (1 - portion) ** 2))))
        color = (0x7C5A if row < height // 3 else 0x6BBA)
        rectangles.append((cx - half, cy - height + row, half * 2, 1, color))
        if half > 3:
            rectangles.extend(((cx - half, cy - height + row, 1, 1, 0xBE7F),
                               (cx + half - 1, cy - height + row, 1, 1, 0xBE7F)))
    rectangles.append((cx - radius + 1, cy, radius * 2 - 2, 2, 0xD6DF))
    for dx, dy in ((-5, -9), (3, -9), (-5, -4), (3, -4)):
        rectangles.extend(((cx + dx, cy + dy, 4, 1, 0xF57F),
                           (cx + dx - 1, cy + dy + 1, 1, 3, 0xF57F),
                           (cx + dx + 4, cy + dy + 1, 1, 3, 0xF57F),
                           (cx + dx, cy + dy + 4, 4, 1, 0xF57F)))
    return rectangles
