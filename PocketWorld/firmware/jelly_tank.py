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
    """Translucent moon-jelly bell, short fringe and four trailing oral arms."""
    t = tick / 4
    phase = (t % 4.8) / 4.8
    # A short contraction followed by a slower relaxation.
    contraction = math.sin(math.pi * min(1, phase / .28)) if phase < .28 else 0
    cx = 120 + int(math.sin(t * .17) * 15) + tilt_x
    cy = 97 + int(math.sin(t * .29) * 8 - contraction * 4) + tilt_y
    radius = 31 - int(contraction * 7)
    height = 18 + int(contraction * 8)
    out = []
    # Four soft oral arms, with delayed motion toward their tips.
    for i in range(4):
        length = 33 + (i * 7) % 14
        for step in range(0, length, 3):
            x = cx + (i - 1.5) * 5 + math.sin(t * .7 - step * .10 + i) * (1 + step * .12)
            out.append((int(x), cy + step, 2, 4, rgb(68 + step//2, 94 + step//2, 119 + step//2)))
    for row in range(height):
        z = 1 - row / height
        half = max(1, int(radius * math.sqrt(max(0, 1-z*z))))
        # A dim transparent center, brighter curved margins, no opaque purple fill.
        out.append((cx-half,cy-height+row,half*2,1,rgb(17+int(z*14),43+int(z*19),62+int(z*24))))
        if half > 3:
            out.extend(((cx-half,cy-height+row,2,1,rgb(113,151,173)),
                        (cx+half-2,cy-height+row,2,1,rgb(113,151,173))))
            inner=max(1,half-3)
            out.extend(((cx-inner,cy-height+row,1,1,rgb(53,87,111)),
                        (cx+inner-1,cy-height+row,1,1,rgb(53,87,111))))
    out.append((cx-radius+1,cy,radius*2-2,1,rgb(169,194,207)))
    # Fine, short marginal tentacles are distinct from the four oral arms.
    for i in range(17):
        x=cx-radius+2+int(i*(radius*2-4)/16)
        out.append((x,cy+1,1,3+(i*3)%5,rgb(70,111,140)))
    for dx,dy in ((-7,-10),(3,-10),(-7,-4),(3,-4)):
        out.extend(((cx+dx,cy+dy,4,1,rgb(161,145,174)),
                    (cx+dx-1,cy+dy+1,1,3,rgb(113,111,146)),
                    (cx+dx+4,cy+dy+1,1,3,rgb(113,111,146)),
                    (cx+dx,cy+dy+4,4,1,rgb(161,145,174))))
    return out
