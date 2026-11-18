"""Pocket World simulation core. Compatible with CPython and MicroPython.

All four worlds advance independently, even when a different world is viewed.
No network, display, or filesystem dependency is required by this module.
"""

WORLD_DEFS = (
    ("nature", "自然の世界", "Forest", 13579),
    ("city", "街の世界", "Town", 24681),
    ("hybrid", "自然＋文明", "Harmony", 35791),
    ("fantasy", "ファンタジー", "Arcana", 46801),
)

WEATHERS = ("sunny", "sunny", "cloudy", "rain", "windy")
MAX_OFFLINE_SECONDS = 48 * 3600
TICK_SECONDS = 60
# Sound levels are normalized values from 0 to 100, not raw microphone samples.
# The optional microphone adapter should call observe_sound() once per minute.
SOUND_QUIET_MAX = 24
SOUND_LOUD_MIN = 70


def _clamp(value, bottom=0, top=100):
    return max(bottom, min(top, value))


class PocketWorld:
    VERSION = 1

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
                "residents": self._int(old, "residents", 1 if ident == "city" else 0),
                "houses": self._int(old, "houses", 1 if ident == "city" else 0),
                "magic": self._int(old, "magic", 1 if ident == "fantasy" else 0),
                "sound_activity": _clamp(self._int(old, "sound_activity", 0), 0, 19),
                "sound_projects": _clamp(self._int(old, "sound_projects", 0), 0, 2),
                "sound_sparks": _clamp(self._int(old, "sound_sparks", 0), 0, 7),
                "weather": old.get("weather", "sunny"),
                "events": list(old.get("events", []))[-5:],
            }
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
        The timestamp is not trusted beyond 48 hours of catch-up.
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

    def _step(self, world):
        world["minutes"] += 1
        n = world["minutes"]
        ident = world["id"]
        roll = self._rand(world, 100)

        if ident in ("nature", "hybrid", "fantasy") and n % 9 == 0:
            world["plants"] = _clamp(world["plants"] + 1, 0, 85)
        if ident == "city" and n % 45 == 0:
            world["plants"] = _clamp(world["plants"] + 1, 0, 28)
        if ident in ("nature", "hybrid", "fantasy") and n % 47 == 0:
            world["wildlife"] = min(25, world["wildlife"] + 1)
        if ident in ("city", "hybrid", "fantasy") and n % 70 == 0:
            world["residents"] = min(40, world["residents"] + 1)
        if ident in ("city", "hybrid", "fantasy") and n % 140 == 0:
            world["houses"] = min(16, world["houses"] + 1)
            self._event(world, "新しい建物が完成しました")
        if ident == "hybrid" and n % 110 == 0:
            self._event(world, "森と街をつなぐ道ができました")
        if ident == "fantasy" and n % 55 == 0:
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
        else:
            world["magic"] = min(80, world["magic"] + 1)
            self._event(world, "魔力の粒子が集まりました")
        return True

    def observe_sound(self, level):
        """React to ONE normalized sound-level sample (0..100) for all worlds.

        The hardware-specific adapter is intentionally NOT included until the
        user's external six-pin microphone model and wiring are confirmed.
        Call at most once per minute, to avoid unnaturally fast development.
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

        # Nature and harmony respond through the weather.
        weather = {"quiet": "sunny", "active": "windy", "loud": "rain"}[band]
        for ident in ("nature", "hybrid"):
            world = self.worlds[ident]
            world["weather"] = weather
            if changed:
                messages = {
                    "quiet": "静かな空気に包まれ、空が晴れました",
                    "active": "周りの音に合わせて風が吹き始めました",
                    "loud": "にぎやかな音に誘われて雨が降り始めました",
                }
                self._event(world, messages[band])

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
            worlds.append({key: (value[:] if isinstance(value, list) else value)
                           for key, value in world.items()})
        return {"version": self.VERSION, "worlds": worlds,
                "linked": True, "audio": dict(self.audio),
                "time_source": "phone" if self.clock_reconciled else "uptime"}

    def persistable(self):
        return {
            "version": self.VERSION,
            "last_wall_epoch": self.last_wall_epoch,
            "worlds": self.worlds,
        }
