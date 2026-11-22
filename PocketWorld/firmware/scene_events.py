"""Small visitors shared by the simulation, round LCD and phone viewer."""

VISIT_SECONDS = 32
VISITORS = {
    "nature": (("swallow", "渡り鳥", "bird"), ("butterfly", "チョウ", "butterfly"),
               ("golden_bird", "金色の渡り鳥", "bird")),
    "city": (("traveler", "旅人", "person"), ("courier", "配達屋さん", "person"),
             ("parade", "小さなパレード", "person")),
    "hybrid": (("seed_spirit", "種の精", "fairy"), ("gardener", "庭師", "person"),
               ("white_deer", "白いシカ", "deer")),
    "fantasy": (("fairy", "妖精", "fairy"), ("shooting_star", "流れ星", "meteor"),
                ("comet", "ほうき星", "meteor")),
    "forest": (("rabbit", "森のウサギ", "rabbit"), ("fox", "キツネ", "fox"),
               ("firefly_swarm", "ホタルの集まり", "glow")),
    "river": (("river_school", "小魚の群れ", "fish"), ("shrimp", "川エビ", "shrimp"),
              ("turtle", "小さなカメ", "turtle")),
    "ocean": (("ocean_school", "熱帯魚の群れ", "fish"), ("jellyfish", "クラゲ", "jelly"),
              ("manta", "マンタ", "manta")),
    "deepsea": (("lantern_fish", "発光魚", "fish"), ("deep_jelly", "深海クラゲ", "jelly"),
                ("giant_squid", "深海の大イカ", "squid")),
}
VISITOR_INFO = {
    ident: (source, name, shape, index == 2)
    for source, choices in VISITORS.items()
    for index, (ident, name, shape) in enumerate(choices)
}


def visitor_choices(world_id):
    if world_id == "aquarium":
        return VISITORS["river"] + VISITORS["ocean"] + VISITORS["deepsea"]
    return VISITORS[world_id]


def active_visit(world, water_area=None):
    event = world.get("visit", {})
    info = VISITOR_INFO.get(event.get("kind")) if isinstance(event, dict) else None
    if info is None:
        return None
    if not isinstance(event.get("minute"), int):
        return None
    source, name, shape, rare = info
    if source != world["id"] and not (world["id"] == "aquarium" and source in ("river", "ocean", "deepsea")):
        return None
    if water_area is not None and source != water_area:
        return None
    age = (world["minutes"] - event["minute"]) * 60 + world.get("remainder", 0)
    if not 0 <= age < VISIT_SECONDS:
        return None
    return {"id": event["kind"], "name": name, "area": source,
            "age": age, "duration": VISIT_SECONDS, "rare": rare, "shape": shape}


SHAPES = {
    "bird": ("1......1", ".11..11.", "..1221..", "...11...", "....3..."),
    "butterfly": ("11...11", "121.121", ".11311.", "..131..", ".11.11."),
    "person": ("..22..", "..22..", ".1111.", "..11..", "..11..", "..33..", ".3..3."),
    "fairy": ("11.22.11", "12122121", ".111111.", "...11...", "..1..1..", "...33..."),
    "deer": ("....1.1..", "....111..", "11111113.", "1111111..", ".1..1....", ".3..3...."),
    "rabbit": ("..1.1..", "..1.1..", "..111..", ".11213.", "111111.", ".1..1.."),
    "fox": ("1.....1..", ".111111..", "11111213.", ".111111..", ".3...3..."),
    "meteor": ("1........", ".11......", "..111....", "...1121..", "....1211.", ".....11.."),
    "glow": ("2......2", "........", "...2....", "........", ".2....2.", "........", "....2..."),
    "fish": ("1....11", ".111121", "1111113", ".111121", "1....11"),
    "shrimp": (".111111..", "11122213.", "..11111..", "...11.1..", "..1...1.."),
    "turtle": ("...1111...", "..122221..", "111221121.", "..122221..", "...1111...", "..1....1.."),
    "jelly": ("...111...", "..12221..", ".1222221.", "111111111", "..1.1.1..", ".1..1..1.", "..1.1.1.."),
    "manta": ("1.........1", "11...1...11", ".111111111.", "..1121311..", "....11.....", "....1......"),
    "squid": ("...11...", "..1221..", ".122221.", ".122221.", "..1111..", ".1.11.1.", "1..11..1", "..1..1.."),
}
PALETTES = {
    "bird": (0x65DF, 0xFFFF, 0x18E3), "butterfly": (0xFCA8, 0xFFE0, 0x18E3),
    "person": (0xE9AA, 0xFFBE, 0x2104), "fairy": (0xA6FC, 0xFFFF, 0x9B5F),
    "deer": (0xF7BC, 0xFFFF, 0x528A), "rabbit": (0xF7BC, 0xFA96, 0x18E3),
    "fox": (0xEBA7, 0xFF59, 0x18E3), "meteor": (0xFE60, 0xFFFF, 0xFFFF),
    "glow": (0xFFE0, 0xFFE0, 0xFFE0), "fish": (0xFD24, 0xFFE0, 0x18E3),
    "turtle": (0x6549, 0x9E2F, 0x18E3), "jelly": (0xC6FF, 0xF7DF, 0xC19F),
    "manta": (0x9D7A, 0xCE7D, 0x18E3), "squid": (0xA4FE, 0xD69F, 0xFFFF),
    "shrimp": (0xFB2F, 0xFE57, 0x18E3),
}
PALETTE_OVERRIDES = {
    "golden_bird": (0xFEA0, 0xFFFF, 0x528A), "gardener": (0x5CEB, 0xFFBE, 0x2104),
    "seed_spirit": (0x9E8F, 0xFFE0, 0x5B46), "comet": (0x7FFF, 0xFFFF, 0xFFFF),
    "river_school": (0x96FF, 0xFFFF, 0x18E3), "lantern_fish": (0x5B6D, 0x96D6, 0xFFE0),
    "deep_jelly": (0xA4FE, 0xE6DF, 0xA4FE),
}


def visitor_frames(kind):
    _, _, shape, rare = VISITOR_INFO[kind]
    palette = PALETTE_OVERRIDES.get(kind, PALETTES[shape])
    school = kind in ("river_school", "ocean_school")
    scale = 1 if school else 2
    copies = ((0, 0), (9, 5), (17, -1)) if school else (
        ((0, 0), (12, 2), (24, 0)) if kind == "parade" else ((0, 0),))
    frames = []
    for phase in range(2):
        pixels = []
        for left, top in copies:
            for y, row in enumerate(SHAPES[shape]):
                x = 0
                while x < len(row):
                    value = row[x]
                    end = x + 1
                    while end < len(row) and row[end] == value:
                        end += 1
                    if value != ".":
                        bob = phase if shape in ("bird", "butterfly", "fairy", "jelly") else 0
                        pixels.append((left + x * scale, top + y * scale + bob,
                                       (end - x) * scale, scale, palette[int(value) - 1]))
                    x = end
        if rare:
            pixels.extend(((1 + phase * 3, -4, 1, 1, 0xFFE0),
                           (17 - phase * 2, -2, 1, 1, 0xFFFF)))
        if kind == "courier":
            pixels.append((10, 6, 5, 5, 0xB3C7))
        elif kind == "gardener":
            pixels.extend(((2, -1, 8, 2, 0x6D48), (11, 6, 1, 9, 0xB3C7)))
        elif kind == "seed_spirit":
            pixels.append((7, -3, 4, 2, 0x67A7))
        elif kind == "lantern_fish":
            pixels.extend(((10, -4, 1, 4, 0x5B6D), (9, -6, 3, 2, 0xFFE0)))
        frames.append(pixels)
    return frames


def visitor_position(visit, tick):
    shape = VISITOR_INFO[visit["id"]][2]
    x = 43 + int(visit["age"] * 125 / VISIT_SECONDS)
    if visit["area"] in ("river", "ocean", "deepsea"):
        y = 112 + tick % 2
    elif shape in ("person", "deer", "rabbit", "fox"):
        y = 151 - (tick % 2 if shape == "rabbit" else 0)
    elif shape == "meteor":
        y = 62 + int(visit["age"] / 2)
    else:
        y = 73 + tick % 2
    return x, y
