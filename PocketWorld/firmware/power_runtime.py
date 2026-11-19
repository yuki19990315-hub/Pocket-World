"""Saved schedule, trusted phone clock, and optional timer-deep-sleep planning.

Hardware deep sleep is deliberately gated by settings.ENABLE_DEEP_SLEEP because
the display driver, recovery path and RTC drift have not been hardware-tested.
"""

import json
import os

from work_schedule import DEFAULT_SCHEDULE, WorkSchedule, validate_schedule

SCHEDULE_FILE = "power.json"
WAKE_MARKER = "power_wake.json"
HOLIDAY_FILE = "assets/jp_holidays.json"


def _read_json(filename):
    with open(filename, "r") as handle:
        return json.load(handle)


def _save_json(filename, value):
    temporary = filename + ".tmp"
    backup = filename + ".bak"
    with open(temporary, "w") as handle:
        json.dump(value, handle)
    try:
        os.remove(backup)
    except OSError:
        pass
    try:
        os.rename(filename, backup)
    except OSError:
        pass
    os.rename(temporary, filename)


class PowerRuntime:
    def __init__(self, sleep_supported=False):
        self.sleep_supported = bool(sleep_supported)
        self.unix_anchor = None
        self.elapsed_ms = 0
        holidays = {}
        try:
            holidays = _read_json(HOLIDAY_FILE)
        except (OSError, ValueError):
            pass
        schedule = DEFAULT_SCHEDULE
        for candidate in (SCHEDULE_FILE, SCHEDULE_FILE + ".bak"):
            try:
                schedule = validate_schedule(_read_json(candidate))
                break
            except (OSError, TypeError, ValueError, KeyError):
                pass
        self.work = WorkSchedule(schedule, holidays)

    def sync_clock(self, unix_seconds):
        try:
            epoch = int(unix_seconds)
        except (TypeError, ValueError):
            raise ValueError("Invalid Unix time")
        # Valid modern POSIX timestamps, bounded well before integer overflow.
        if not 1577836800 <= epoch < 4102444800:
            raise ValueError("Clock is outside supported range")
        self.unix_anchor = epoch
        self.elapsed_ms = 0

    def tick(self, milliseconds):
        if self.unix_anchor is not None:
            self.elapsed_ms += max(0, int(milliseconds))

    def now(self):
        if self.unix_anchor is None:
            return None
        return self.unix_anchor + self.elapsed_ms // 1000

    def status(self):
        current = self.now()
        state = self.work.state(current) if current is not None else {
            "mode": "clock_unknown", "next_wake": None, "next_sleep": None}
        return {"schedule": self.work.config, "clock_synced": current is not None,
                "sleep_supported": self.sleep_supported, "now": current,
                "mode": state["mode"], "next_wake": state["next_wake"],
                "next_sleep": state["next_sleep"],
                "day_phase": self.work.day_phase(current),
                "day_timeline": self.work.day_timeline()}

    def update_schedule(self, value):
        clean = validate_schedule(value)
        _save_json(SCHEDULE_FILE, clean)
        self.work.config = clean

    def plan_sleep(self):
        if not self.sleep_supported or self.now() is None:
            return None
        return self.work.next_timer_seconds(self.now())

    def write_wake_marker(self, wake_epoch):
        _save_json(WAKE_MARKER, {"wake_epoch": int(wake_epoch)})

    def restore_timer_wake(self, is_deepsleep_reset):
        if not is_deepsleep_reset:
            return False
        try:
            epoch = _read_json(WAKE_MARKER)["wake_epoch"]
            self.sync_clock(epoch)
        except (OSError, ValueError, KeyError, TypeError):
            return False
        return True
