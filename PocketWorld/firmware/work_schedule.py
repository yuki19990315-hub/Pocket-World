"""Pure Japan workday/holiday calculations for the Sanny power controller.

The input timestamps are POSIX/Unix UTC seconds irrespective of MicroPython's
native epoch. No datetime dependency and no network access are required.
"""

JST_SECONDS = 9 * 3600
SECONDS_PER_DAY = 86400
MAX_BACKGROUND_SLEEP = 12 * 3600


class CalendarUnavailable(ValueError):
    """An official holiday table for this year has not been installed."""


def _civil_from_days(day):
    """Gregorian Y-M-D from days relative to 1970-01-01 (integer arithmetic)."""
    z = day + 719468
    era = z // 146097
    doe = z - era * 146097
    yoe = (doe - doe // 1460 + doe // 36524 - doe // 146096) // 365
    y = yoe + era * 400
    doy = doe - (365 * yoe + yoe // 4 - yoe // 100)
    mp = (5 * doy + 2) // 153
    d = doy - (153 * mp + 2) // 5 + 1
    m = mp + (3 if mp < 10 else -9)
    return (y + (1 if m <= 2 else 0), m, d)


def _date_key(day):
    year, month, date = _civil_from_days(day)
    return (year, "%04d-%02d-%02d" % (year, month, date))


def _time_minutes(text):
    if not isinstance(text, str) or len(text) != 5 or text[2] != ":":
        raise ValueError("Time must be HH:MM")
    if not (text[:2].isdigit() and text[3:].isdigit()):
        raise ValueError("Time must be HH:MM")
    hh, mm = int(text[:2]), int(text[3:])
    if hh > 23 or mm > 59:
        raise ValueError("Invalid time")
    return hh * 60 + mm


DEFAULT_SCHEDULE = {"enabled": False, "wake": "08:00", "sleep": "18:00",
                    "exclude_jp_holidays": True, "timezone": "Asia/Tokyo"}


def validate_schedule(value):
    if not isinstance(value, dict):
        raise ValueError("Schedule must be an object")
    keys = set(DEFAULT_SCHEDULE)
    if set(value) != keys:
        raise ValueError("Missing or unknown schedule fields")
    if not isinstance(value["enabled"], bool) or not isinstance(value["exclude_jp_holidays"], bool):
        raise ValueError("Boolean fields must be true/false")
    if value["timezone"] != "Asia/Tokyo":
        raise ValueError("This prototype supports Asia/Tokyo only")
    start = _time_minutes(value["wake"])
    end = _time_minutes(value["sleep"])
    if start >= end:
        raise ValueError("Wake must be earlier than sleep")
    return dict(value)


class WorkSchedule:
    def __init__(self, config=None, holiday_data=None):
        self.config = validate_schedule(config if config is not None else DEFAULT_SCHEDULE)
        self.holidays = holiday_data if isinstance(holiday_data, dict) else {}

    def _is_workday(self, day):
        # 1970-01-01 was Thursday (ISO weekday 4).
        weekday = ((day + 3) % 7) + 1
        if weekday > 5:
            return False
        if not self.config["exclude_jp_holidays"]:
            return True
        year, key = _date_key(day)
        by_year = self.holidays.get("dates", {}).get(str(year))
        if not isinstance(by_year, dict):
            raise CalendarUnavailable("Official holiday data for %d is missing" % year)
        return key not in by_year

    @staticmethod
    def _local_parts(unix_seconds):
        local = int(unix_seconds) + JST_SECONDS
        return divmod(local, SECONDS_PER_DAY)

    def state(self, unix_seconds):
        if not self.config["enabled"]:
            return {"mode": "active", "next_wake": None, "next_sleep": None}
        day, second = self._local_parts(unix_seconds)
        wake = _time_minutes(self.config["wake"]) * 60
        sleep = _time_minutes(self.config["sleep"]) * 60
        try:
            active = self._is_workday(day) and wake <= second < sleep
            next_wake = None
            for offset in range(15):
                candidate_day = day + offset
                if not self._is_workday(candidate_day):
                    continue
                candidate = candidate_day * SECONDS_PER_DAY + wake - JST_SECONDS
                if candidate > int(unix_seconds):
                    next_wake = candidate
                    break
            if next_wake is None:
                raise CalendarUnavailable("Cannot calculate the next workday")
        except CalendarUnavailable:
            # Never arm a deep sleep that could hide the device indefinitely.
            return {"mode": "unknown", "next_wake": None, "next_sleep": None}
        next_sleep = (day * SECONDS_PER_DAY + sleep - JST_SECONDS) if active else None
        return {"mode": "active" if active else "sleep", "next_wake": next_wake,
                "next_sleep": next_sleep}

    def next_timer_seconds(self, unix_seconds):
        state = self.state(unix_seconds)
        if state["mode"] != "sleep":
            return None
        remaining = state["next_wake"] - int(unix_seconds)
        return max(1, min(remaining, MAX_BACKGROUND_SLEEP))
