"""Pocket World simulation core. Compatible with CPython and MicroPython.

All worlds advance independently, even when a different world is viewed.
No network, display, or filesystem dependency is required by this module.
"""

from scene_events import (VISITORS, VISITOR_INFO, active_visit,
                          visitor_choices, visitor_frames)

WORLD_DEFS = (
    ("nature", "自然の世界", "Island", 13579),
    ("city", "街の世界", "Town", 24681),
    ("hybrid", "自然＋文明", "Harmony", 35791),
    ("fantasy", "ファンタジー", "Arcana", 46801),
    ("forest", "森のテラリウム", "Woodland", 57913),
    ("aquarium", "水の世界", "Aquarium", 68021),
    ("jellyfish", "一匹のクラゲ", "Moon Jelly", 79133),
)

WEATHERS = ("sunny", "sunny", "cloudy", "rain", "windy")
# The two marine areas remain distinct from freshwater; creatures never mix.
WATER_AREAS = ("river", "ocean", "deepsea")
WATER_UNLOCK_MINUTES = {"ocean": 1440, "deepsea": 4320}
FOREST_SEASONS = ("spring", "summer", "autumn", "winter")
# A long weekend (Fri evening -> Tue morning) must not truncate growth.
# Still cap untrusted phone-clock recovery to a week per boot.
MAX_OFFLINE_SECONDS = 7 * 24 * 3600
TICK_SECONDS = 60
# Sound levels are normalized values from 0 to 100, not raw microphone samples.
# The optional microphone adapter should call observe_sound() once per minute.
SOUND_QUIET_MAX = 24
SOUND_LOUD_MIN = 70
MATURITY_MINUTES = 30 * 1440
# A first-session discovery happens quickly; later changes stay interesting
# over weeks, in step with the 30-day illustrated maturation timeline.
HOUSE_MILESTONES = (180, 720, 1440, 2880, 4320, 5760, 8640, 10080,
                    14400, 20160, 28800, 36000, MATURITY_MINUTES)
MAX_JOURNAL = 24


def _clamp(value, bottom=0, top=100):
    return max(bottom, min(top, value))


def _growth_due(minute, early_step, mature_step, early_until=180, begins=0):
    """Allow early discoveries, then gradually paced background progress."""
    elapsed = minute - begins
    if elapsed <= 0:
        return False
    if elapsed <= early_until:
        return minute % early_step == 0
    return minute % mature_step == 0


def _starting_water_area(ident):
    if ident == "river":
        return {"unlocked": True, "plants": 6, "fish": 2, "shrimp": 1,
                "coral": 0, "glow": 0, "visitors": 0}
    if ident == "ocean":
        return {"unlocked": False, "plants": 2, "fish": 2, "shrimp": 0,
                "coral": 1, "glow": 0, "visitors": 0}
    return {"unlocked": False, "plants": 0, "fish": 1, "shrimp": 0,
            "coral": 0, "glow": 2, "visitors": 0}


class PocketWorld:
    VERSION = 5

    def __init__(self, restored=None):
        restored = restored if isinstance(restored, dict) else {}
        older = restored.get("worlds", {})
        self.worlds = {}
        for ident, name, label, seed in WORLD_DEFS:
            old = older.get(ident, {}) if isinstance(older, dict) else {}
            self.worlds[ident] = {
                "id": ident,
                "name": name,
                "label": label,
                "seed": self._int(old, "seed", seed),
                "rng_state": self._int(old, "rng_state", seed),
                "minutes": self._int(old, "minutes", 0),
                "remainder": self._int(old, "remainder", 0),
                "plants": self._int(old, "plants", 10 if ident != "city" else 4),
                "wildlife": self._int(old, "wildlife", 2 if ident != "city" else 0),
                "residents": self._int(old, "residents", 2 if ident in ("city", "hybrid") else 0),
                "houses": self._int(old, "houses", 1 if ident in ("city", "hybrid") else 0),
                "magic": self._int(old, "magic", 1 if ident == "fantasy" else 0),
                "sound_activity": _clamp(self._int(old, "sound_activity", 0), 0, 19),
                "sound_projects": _clamp(self._int(old, "sound_projects", 0), 0, 2),
                "sound_sparks": _clamp(self._int(old, "sound_sparks", 0), 0, 7),
                "mushrooms": self._int(old, "mushrooms", 1 if ident == "forest" else 0),
                "fireflies": self._int(old, "fireflies", 1 if ident == "forest" else 0),
                "tree_age": self._int(old, "tree_age", 0),
                "season": old.get("season", "spring"),
                "weather": old.get("weather", "sunny"),
                "events": list(old.get("events", []))[-5:],
                "journal": [dict(item) for item in
                            (old.get("journal", []) if isinstance(old.get("journal", []), list) else [])
                            if isinstance(item, dict) and
                            isinstance(item.get("minute"), int) and
                            isinstance(item.get("message"), str)][-MAX_JOURNAL:],
            }
            world = self.worlds[ident]
            if ident == "jellyfish":
                world.update(plants=0, wildlife=1, residents=0, houses=0,
                             magic=0, jellyfish_count=1, weather="sunny")
            allowed = {entry[0] for entry in visitor_choices(ident)}
            discoveries = old.get("discoveries", {})
            if not isinstance(discoveries, dict):
                discoveries = {}
            world["discoveries"] = {
                key: min(9999, self._int(discoveries, key, 0))
                for key in allowed if self._int(discoveries, key, 0) > 0
            }
            visit = old.get("visit", {})
            world["visit"] = {}
            if (isinstance(visit, dict) and visit.get("kind") in allowed and
                    isinstance(visit.get("minute"), int) and
                    0 <= visit["minute"] <= world["minutes"]):
                world["visit"] = {"kind": visit["kind"], "minute": visit["minute"]}
            if ident == "hybrid":
                # Older hybrid worlds were born empty; give their saved village
                # the same starter cottage and two residents without resetting age.
                self.worlds[ident]["houses"] = max(1, self.worlds[ident]["houses"])
                self.worlds[ident]["residents"] = max(2, self.worlds[ident]["residents"])
            if ident == "aquarium":
                saved_areas = old.get("water_areas", {})
                if not isinstance(saved_areas, dict):
                    saved_areas = {}
                areas = {}
                for area_id in WATER_AREAS:
                    area_old = saved_areas.get(area_id, {})
                    if not isinstance(area_old, dict):
                        area_old = {}
                    start = _starting_water_area(area_id)
                    area = {field: self._int(area_old, field, start[field])
                            for field in ("plants", "fish", "shrimp", "coral", "glow", "visitors")}
                    area["unlocked"] = (area_id == "river" or
                        bool(area_old.get("unlocked", False)) or
                        self.worlds[ident]["minutes"] >= WATER_UNLOCK_MINUTES[area_id])
                    areas[area_id] = area
                self.worlds[ident]["water_areas"] = areas
                self._sync_aquarium(self.worlds[ident])
        self.last_wall_epoch = self._int(restored, "last_wall_epoch", 0)
        self.runtime_since_boot = 0
        self.clock_reconciled = False
        # Runtime-only status: a saved world never implies that a mic is plugged in.
        # No audio recordings or raw samples are retained.
        self.audio = {"connected": False, "level": None, "band": None}

    @staticmethod
    def _int(obj, key, default):
        try:
            return int(obj.get(key, default))
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _rand(world, limit):
        # Small deterministic PRNG; avoid Python and MicroPython random differences.
        world["rng_state"] = (1103515245 * world["rng_state"] + 12345) & 0x7fffffff
        return world["rng_state"] % limit

    def advance(self, seconds, runtime=True):
        """Advance all worlds by elapsed real seconds (no accelerated demo clock)."""
        seconds = max(0, min(int(seconds), MAX_OFFLINE_SECONDS))
        if runtime:
            self.runtime_since_boot += seconds
        for world in self.worlds.values():
            total = world["remainder"] + seconds
            steps, world["remainder"] = divmod(total, TICK_SECONDS)
            for _ in range(steps):
                self._step(world)

    def reconcile_clock(self, unix_seconds):
        """Recover downtime from the phone clock once per boot.

        Already simulated uptime is subtracted to avoid counting time twice.
        The timestamp is not trusted beyond one week of catch-up.
        """
        try:
            unix_seconds = int(unix_seconds)
        except (TypeError, ValueError):
            return 0
        if not 1577836800 <= unix_seconds <= 4102444800:
            return 0
        recovered = 0
        if not self.clock_reconciled and self.last_wall_epoch:
            recovered = _clamp(
                unix_seconds - self.last_wall_epoch - self.runtime_since_boot,
                0, MAX_OFFLINE_SECONDS,
            )
            if recovered:
                self.advance(recovered, runtime=False)
        self.clock_reconciled = True
        self.last_wall_epoch = unix_seconds
        self.runtime_since_boot = 0
        return recovered

    def _event(self, world, message):
        world["events"].append(message)
        world["events"] = world["events"][-5:]
        world["journal"].append({"minute": world["minutes"], "message": message})
        world["journal"] = world["journal"][-MAX_JOURNAL:]

    @staticmethod
    def _sync_aquarium(world):
        active = [area for area in world["water_areas"].values() if area["unlocked"]]
        world["plants"] = sum(area["plants"] + area["coral"] for area in active)
        world["wildlife"] = sum(area["fish"] + area["shrimp"] for area in active)

    def _step_forest(self, world, n):
        if _growth_due(n, 24, 720):
            world["plants"] = min(85, world["plants"] + 1)
        if _growth_due(n, 97, 2880):
            world["wildlife"] = min(25, world["wildlife"] + 1)
        if _growth_due(n, 180, 1440):
            world["tree_age"] = min(1000, world["tree_age"] + 1)
        if world["weather"] == "rain" and _growth_due(n, 45, 1440):
            world["mushrooms"] = min(25, world["mushrooms"] + 1)
        if _growth_due(n, 360, 2880, early_until=720):
            world["fireflies"] = min(18, world["fireflies"] + 1)
            self._event(world, "日が暮れて、ホタルが光り始めました")
        season = FOREST_SEASONS[(n // (3 * 1440)) % len(FOREST_SEASONS)]
        if season != world["season"]:
            world["season"] = season
            self._event(world, "森の季節が移り変わりました")

    def _step_aquarium(self, world, n):
        areas = world["water_areas"]
        for area_id in ("ocean", "deepsea"):
            if not areas[area_id]["unlocked"] and n >= WATER_UNLOCK_MINUTES[area_id]:
                areas[area_id]["unlocked"] = True
                self._event(world, "新しい水域「%s」が解放されました" %
                            ("海" if area_id == "ocean" else "深海"))
        river = areas["river"]
        if _growth_due(n, 45, 1440):
            river["plants"] = min(35, river["plants"] + 1)
        if _growth_due(n, 190, 2880, early_until=380):
            river["fish"] = min(18, river["fish"] + 1)
        if _growth_due(n, 245, 4320, early_until=490):
            river["shrimp"] = min(12, river["shrimp"] + 1)
        ocean = areas["ocean"]
        if ocean["unlocked"]:
            if _growth_due(n, 100, 1440, early_until=350,
                           begins=WATER_UNLOCK_MINUTES["ocean"]):
                ocean["coral"] = min(24, ocean["coral"] + 1)
            if _growth_due(n, 220, 2880, early_until=500,
                           begins=WATER_UNLOCK_MINUTES["ocean"]):
                ocean["fish"] = min(20, ocean["fish"] + 1)
            if n % 10080 == 0:
                ocean["visitors"] = min(5, ocean["visitors"] + 1)
                self._event(world, "海にウミガメが遊びに来ました")
        deep = areas["deepsea"]
        if deep["unlocked"]:
            if _growth_due(n, 170, 1440, early_until=350,
                           begins=WATER_UNLOCK_MINUTES["deepsea"]):
                deep["glow"] = min(22, deep["glow"] + 1)
            if _growth_due(n, 310, 2880, early_until=620,
                           begins=WATER_UNLOCK_MINUTES["deepsea"]):
                deep["fish"] = min(16, deep["fish"] + 1)
            if n % 14400 == 0:
                deep["visitors"] = min(4, deep["visitors"] + 1)
                self._event(world, "深海に見たことのない生き物が現れました")
        self._sync_aquarium(world)

    def _step(self, world):
        world["minutes"] += 1
        n = world["minutes"]
        ident = world["id"]
        if ident == "jellyfish":
            return  # A quiet single-animal tank never spawns visitors or fish.
        roll = self._rand(world, 100)
        self._visit(world, n, roll)

        if ident == "aquarium":
            self._step_aquarium(world, n)
            return
        if ident == "forest":
            if n % 90 == 0:
                world["weather"] = WEATHERS[roll % len(WEATHERS)]
            self._step_forest(world, n)
            return

        if ident in ("nature", "hybrid", "fantasy") and _growth_due(n, 9, 720):
            world["plants"] = _clamp(world["plants"] + 1, 0, 85)
        if ident == "city" and _growth_due(n, 45, 1440):
            world["plants"] = _clamp(world["plants"] + 1, 0, 28)
        if ident in ("nature", "hybrid", "fantasy") and _growth_due(n, 47, 2880):
            world["wildlife"] = min(25, world["wildlife"] + 1)
        if ident in ("city", "hybrid", "fantasy") and _growth_due(n, 70, 1440):
            world["residents"] = min(40, world["residents"] + 1)
        if ident in ("city", "hybrid", "fantasy") and n in HOUSE_MILESTONES:
            world["houses"] = min(16, world["houses"] + 1)
            self._event(world, "新しい建物が完成しました")
        if ident == "hybrid" and _growth_due(n, 110, 4320):
            self._event(world, "森と街をつなぐ道ができました")
        if ident == "hybrid" and n == 10 * 1440:
            self._event(world, "段々村が育ち、大樹が村を見守っています")
        if ident == "hybrid" and n == 20 * 1440:
            self._event(world, "大樹の枝と湖畔に新しい家が建ち始めました")
        if ident == "fantasy" and _growth_due(n, 55, 720):
            world["magic"] = min(80, world["magic"] + 1)
        if n % 90 == 0:
            world["weather"] = WEATHERS[roll % len(WEATHERS)]
        if n % 180 == 0:
            labels = {
                "nature": "珍しい渡り鳥が立ち寄りました",
                "city": "広場で小さなお祭りが開催されました",
                "hybrid": "村人が森で新しい植物を発見しました",
                "fantasy": "夜空に魔法の流れ星が現れました",
            }
            self._event(world, labels[ident])
        if n == MATURITY_MINUTES:
            self._event(world, "30日を迎え、小さな世界が成熟しました")

    def _visit(self, world, minute, roll):
        discoveries = world["discoveries"]
        if discoveries and minute % 3 != world["seed"] % 3:
            return
        source = world["id"]
        if source == "aquarium":
            areas = [area for area in WATER_AREAS if world["water_areas"][area]["unlocked"]]
            source = areas[(minute // 3 + world["seed"]) % len(areas)]
        total = sum(discoveries.values())
        rare = roll < 8 or total % 10 == 9
        index = 2 if rare else (0 if roll < 55 else 1)
        kind, name, _ = VISITORS[source][index]
        first = discoveries.get(kind, 0) == 0
        discoveries[kind] = min(9999, discoveries.get(kind, 0) + 1)
        world["visit"] = {"kind": kind, "minute": minute}
        if first or rare:
            self._event(world, ("珍しい来訪：%s" if rare else "初めての来訪：%s") % name)

    def tap(self, ident):
        world = self.worlds.get(ident)
        if world is None:
            return False
        if ident == "nature":
            world["plants"] = min(85, world["plants"] + 1)
            self._event(world, "小さな芽を見つけました")
        elif ident == "city":
            self._event(world, "住民があなたに手を振りました")
        elif ident == "hybrid":
            self._event(world, "小鳥が村の広場に飛んできました")
        elif ident == "fantasy":
            world["magic"] = min(80, world["magic"] + 1)
            self._event(world, "魔力の粒子が集まりました")
        elif ident == "forest":
            self._event(world, "落ち葉の下で小さな虫を見つけました")
        elif ident == "aquarium":
            self._event(world, "水面に波紋が広がり、魚が近寄ってきました")
        elif ident == "jellyfish":
            self._event(world, "一匹のクラゲが、ゆっくり傘をひらいています")
        return True

    def observe_sound(self, level):
        """React to ONE normalized sound-level sample (0..100) for all worlds.

        The optional INMP441 adapter feeds this no more than once per minute,
        to avoid unnaturally fast development. It is disabled until wired.
        This method processes a volume number only, never speech or PCM audio.
        """
        if isinstance(level, bool):
            return False
        try:
            level = int(level)
        except (TypeError, ValueError, OverflowError):
            return False
        if not 0 <= level <= 100:
            return False

        band = ("quiet" if level <= SOUND_QUIET_MAX
                else "loud" if level >= SOUND_LOUD_MIN else "active")
        changed = band != self.audio["band"]
        self.audio = {"connected": True, "level": level, "band": band}

        # Nature, woodland and harmony respond through the weather.
        weather = {"quiet": "sunny", "active": "windy", "loud": "rain"}[band]
        for ident in ("nature", "hybrid", "forest"):
            world = self.worlds[ident]
            world["weather"] = weather
            if changed:
                messages = {
                    "quiet": "静かな空気に包まれ、空が晴れました",
                    "active": "周りの音に合わせて風が吹き始めました",
                    "loud": "にぎやかな音に誘われて雨が降り始めました",
                }
                self._event(world, messages[band])

        if changed:
            self._event(self.worlds["aquarium"],
                        "水が静かに揺れています" if band == "quiet" else
                        "水面に大きな波紋が広がりました" if band == "loud" else
                        "周囲の音で水面に小さな泡が生まれました")

        # Town and harmony use sustained activity to grow; a single loud sound
        # cannot instantly spawn many houses or residents.
        if band != "quiet":
            for ident, threshold in (("city", 8), ("hybrid", 12)):
                world = self.worlds[ident]
                world["sound_activity"] += 2 if band == "loud" else 1
                if world["sound_activity"] >= threshold:
                    world["sound_activity"] = 0
                    world["residents"] = min(40, world["residents"] + 1)
                    world["sound_projects"] += 1
                    self._event(world, "周囲の活気につられて新しい住民がやってきました")
                    if world["sound_projects"] >= 3:
                        world["sound_projects"] = 0
                        world["houses"] = min(16, world["houses"] + 1)
                        self._event(world, "にぎやかな街に新しい建物が完成しました")

        # Powerful sound fills the magic world with energy. Only after several
        # strong observations does a rare shooting-star event appear.
        if band == "loud":
            fantasy = self.worlds["fantasy"]
            fantasy["magic"] = min(80, fantasy["magic"] + 1)
            fantasy["sound_sparks"] += 1
            if fantasy["sound_sparks"] >= 8:
                fantasy["sound_sparks"] = 0
                fantasy["magic"] = min(80, fantasy["magic"] + 5)
                self._event(fantasy, "音の魔力が満ち、珍しい流れ星が降りました")
        return True

    def disconnect_sound(self):
        """Mark the optional mic as disconnected without altering the worlds."""
        self.audio = {"connected": False, "level": None, "band": None}

    def snapshot(self):
        worlds = []
        for ident, _, _, _ in WORLD_DEFS:
            world = self.worlds[ident]
            # Copy each world; API users must not mutate internal state.
            data = {key: (value[:] if isinstance(value, list) else value)
                    for key, value in world.items() if key != "water_areas"}
            data["journal"] = [dict(item) for item in world["journal"]]
            data["discoveries"] = dict(world["discoveries"])
            data["visit"] = dict(world["visit"])
            data["visitor_catalog"] = [
                {"id": kind, "name": name, "rare": VISITOR_INFO[kind][3],
                 "visits": world["discoveries"].get(kind, 0)}
                for kind, name, _ in visitor_choices(ident)
            ]
            data["visitor"] = active_visit(world)
            if data["visitor"] is not None:
                data["visitor"]["frames"] = visitor_frames(data["visitor"]["id"])
            if "water_areas" in world:
                data["water_areas"] = {key: dict(value)
                                       for key, value in world["water_areas"].items()}
            worlds.append(data)
        return {"version": self.VERSION, "worlds": worlds,
                "linked": True, "audio": dict(self.audio),
                "time_source": "phone" if self.clock_reconciled else "uptime"}

    def persistable(self):
        return {
            "version": self.VERSION,
            "last_wall_epoch": self.last_wall_epoch,
            "worlds": self.worlds,
        }
