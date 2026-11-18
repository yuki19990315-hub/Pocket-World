"""Render the shared simulation on Sanny's round LCD."""

from round_lcd import RoundLCD, rgb
from world_model import WORLD_DEFS, WATER_AREAS

WHITE = rgb(245, 249, 236)
INK = rgb(13, 28, 45)
GOLD = rgb(255, 201, 96)
GREEN = rgb(79, 163, 108)
PINE = rgb(24, 88, 79)
SOIL = rgb(97, 61, 48)
SKY = rgb(90, 178, 205)


def tree(canvas, x, y, color, height=26):
    canvas.fill_rect(x - 2, y - 8, 5, 10, SOIL)
    canvas.ellipse(x, y - height // 2, height // 3, height // 2, color, True)


def stars(canvas, count, tick, color):
    for index in range(count):
        x = 39 + (index * 61 + tick * 7) % 162
        y = 55 + (index * 29 + tick * 5) % 103
        canvas.hline(x - 2, y, 5, color)
        canvas.vline(x, y - 2, 5, color)


class WorldDisplay:
    def __init__(self):
        self.lcd = RoundLCD()
        self.canvas = self.lcd.canvas
        self.world_index = 0
        self.water_index = 0
        self.visible = False

    @property
    def world_id(self):
        return WORLD_DEFS[self.world_index][0]

    def select(self, step):
        self.world_index = (self.world_index + step) % len(WORLD_DEFS)

    def select_water(self, world):
        unlocked = [area for area in WATER_AREAS if world["water_areas"][area]["unlocked"]]
        self.water_index = (self.water_index + 1) % len(unlocked)

    def blank(self):
        if self.visible:
            self.lcd.backlight.off()
            self.visible = False

    def render(self, engine, motion, now_ms, battery_low=False):
        world = engine.worlds[self.world_id]
        canvas = self.canvas
        tick = now_ms // 250
        x = int(motion.tilt_x * 10)
        y = int(motion.tilt_y * 7)
        ident = self.world_id
        detail = ""
        if ident in ("nature", "city", "hybrid"):
            self.landscape(world, tick, x, y)
        elif ident == "fantasy":
            self.fantasy(world, tick, x, y)
        elif ident == "forest":
            detail = self.forest(world, tick, x)
        else:
            detail = self.aquarium(world, tick, x)

        if motion.last_shake_ms is not None and now_ms - motion.last_shake_ms < 1800:
            stars(canvas, 9, tick, WHITE)
        if engine.audio["connected"]:
            level = engine.audio["level"]
            if level is not None:
                canvas.fill_rect(90, 202, 60 * level // 100, 2, WHITE)
        label = world["label"]
        canvas.fill_rect(64, 25, 112, 18, INK)
        canvas.text(label, 120 - len(label) * 4, 30, WHITE)
        if detail:
            canvas.fill_rect(72, 184, 96, 13, INK)
            canvas.text(detail, 120 - len(detail) * 4, 187, WHITE)
        canvas.fill_rect(82, 211, 76, 12, INK)
        for index in range(len(WORLD_DEFS)):
            canvas.ellipse(90 + index * 12, 217, 3, 3,
                           GOLD if index == self.world_index else WHITE, True)
        canvas.text("<", 62, 202, WHITE)
        canvas.text(">", 170, 202, WHITE)
        if battery_low:
            canvas.fill_rect(88, 46, 64, 12, INK)
            canvas.text("LOW BATT", 88, 48, GOLD)
        self.lcd.show()
        if not self.visible:
            self.lcd.backlight.on()
            self.visible = True

    def landscape(self, world, tick, x, y):
        c = self.canvas
        weather = world["weather"]
        town = world["id"] == "city"
        c.fill(SKY if weather == "sunny" else rgb(79, 119, 149))
        c.ellipse(154 + x, 77 + y, 21, 21, GOLD, True)
        c.ellipse(64 - x, 132, 111, 39, rgb(83, 125, 128), True)
        c.fill_rect(0, 138, 240, 102, rgb(49, 124, 156))
        c.ellipse(120, 154, 105, 41, rgb(183, 145, 87), True)
        c.ellipse(120, 147, 102, 34, GREEN, True)
        for index in range(min(13, max(0, world["plants"] // 2))):
            tree(c, 39 + index * 47 % 164, 128 + index * 17 % 39, PINE, 20)
        if town or world["id"] == "hybrid":
            c.fill_rect(34, 155, 172, 8, rgb(87, 101, 109))
            count = min(8, max(2 if town else 1, world["houses"] + 1))
            for index in range(count):
                left = 45 + index * 20
                height = 14 + (index * 13 + (9 if town else 0)) % 31
                c.fill_rect(left, 154 - height, 16, height, rgb(166, 94, 83))
                c.fill_rect(left - 1, 152 - height, 18, 4, INK)
                c.fill_rect(left + 5, 158 - height, 5, 6, GOLD)
        for index in range(min(6, max(0, world["wildlife"]))):
            px = 55 + (index * 37 + tick * 2) % 130
            py = 77 + index * 23 % 37
            c.line(px - 3, py, px, py + 2, WHITE)
            c.line(px, py + 2, px + 3, py, WHITE)
        if weather == "rain":
            for index in range(18):
                px = (index * 47) % 240
                py = 56 + (tick * 7 + index * 19) % 121
                c.line(px, py, px - 3, py + 7, WHITE)
        elif weather in ("cloudy", "windy"):
            for index in range(3):
                drift = tick % 45 if weather == "windy" else 0
                c.ellipse(46 + index * 47 + drift, 72 + index % 2 * 15, 22, 7, WHITE, True)

    def fantasy(self, world, tick, x, y):
        c = self.canvas
        c.fill(rgb(40, 28, 81))
        c.ellipse(163 + x, 77 + y, 26, 26, rgb(193, 156, 236), True)
        c.ellipse(173 + x, 69 + y, 23, 23, rgb(40, 28, 81), True)
        c.ellipse(120, 163, 93, 26, rgb(89, 64, 138), True)
        height = 31 + min(31, max(0, world["magic"]))
        for px, offset in ((87, 14), (112, 0), (137, 14)):
            top = 150 - height + offset
            c.fill_rect(px, top, 16, 150 - top, rgb(151, 115, 194))
            c.ellipse(px + 8, top, 12, 6, WHITE, True)
            c.fill_rect(px + 6, top + 14, 4, 7, GOLD)
        stars(c, 5 + min(9, max(0, world["magic"])), tick, GOLD)

    def forest(self, world, tick, x):
        c = self.canvas
        season = world["season"]
        canopy = {"autumn": rgb(190, 112, 63), "winter": rgb(132, 173, 172)}.get(season, GREEN)
        c.fill(rgb(20, 62, 65))
        c.fill_rect(0, 146, 240, 94, SOIL)
        c.fill_rect(0, 143, 240, 8, PINE)
        for index in range(min(11, 5 + max(0, world["plants"]) // 5)):
            px = 33 + index * 43 % 175 + x
            height = 26 + (index * 19 + world["tree_age"]) % 37
            tree(c, px, 145, canopy if index % 2 else PINE, height)
            c.line(px, 151, px + 7, 165, rgb(174, 122, 79))
        for index in range(min(6, max(0, world["mushrooms"]))):
            px = 49 + index * 27
            c.fill_rect(px, 144, 3, 7, WHITE)
            c.ellipse(px + 1, 143, 7, 4, rgb(227, 121, 110), True)
        stars(c, min(12, max(0, world["fireflies"])), tick, GOLD)
        return season.upper()

    def aquarium(self, world, tick, x):
        c = self.canvas
        unlocked = [area for area in WATER_AREAS if world["water_areas"][area]["unlocked"]]
        area_id = unlocked[self.water_index % len(unlocked)]
        area = world["water_areas"][area_id]
        colors = {"river": (rgb(38, 128, 139), GREEN),
                  "ocean": (rgb(32, 94, 159), rgb(227, 122, 127)),
                  "deepsea": (rgb(29, 39, 88), rgb(112, 196, 208))}
        water, plants = colors[area_id]
        c.fill(water)
        c.ellipse(120, 184, 112, 37, rgb(112, 111, 105), True)
        for index in range(min(14, 2 + max(0, area["plants"] + area["coral"] + area["glow"]))):
            px = 34 + index * 47 % 171
            height = 8 + index * 13 % 29
            c.line(px, 177, px + x // 2, 177 - height, plants)
            c.ellipse(px + x // 2, 177 - height, 4, 7, plants, True)
        for index in range(min(14, max(0, area["fish"]))):
            px = 32 + (index * 57 + tick * 4) % 174
            py = 70 + index * 37 % 87
            c.ellipse(px, py, 11, 5, GOLD if index % 2 == 0 else WHITE, True)
            c.vline(px - 13, py - 5, 11, GOLD)
            c.pixel(px + 5, py - 1, INK)
        for index in range(7):
            c.ellipse(56 + index * 19, 60 + (index * 29 - tick * 3) % 105, 2, 2, WHITE)
        return {"river": "RIVER", "ocean": "OCEAN", "deepsea": "DEEP SEA"}[area_id]
