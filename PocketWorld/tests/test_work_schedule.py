import datetime
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "firmware"))
from work_schedule import WorkSchedule, _civil_from_days, validate_schedule


def utc(year, month, day, hh=0, mm=0):
    return int(datetime.datetime(year, month, day, hh, mm,
                 tzinfo=datetime.timezone(datetime.timedelta(hours=9))).timestamp())


class TestWorkSchedule(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        source = os.path.join(os.path.dirname(__file__), "..", "firmware", "assets", "jp_holidays.json")
        with open(source, encoding="utf-8") as handle:
            cls.holidays = json.load(handle)

    def schedule(self, **changes):
        value = {"enabled": True, "wake": "08:00", "sleep": "18:00",
                 "exclude_jp_holidays": True, "timezone": "Asia/Tokyo"}
        value.update(changes)
        return WorkSchedule(value, self.holidays)

    def test_gregorian_conversion_with_leap_and_epoch(self):
        for date in [(1970, 1, 1), (2000, 2, 29), (2026, 11, 18), (2027, 1, 1), (2100, 3, 1)]:
            delta = (datetime.date(*date) - datetime.date(1970, 1, 1)).days
            self.assertEqual(_civil_from_days(delta), date)

    def test_workday_bounds_are_jst(self):
        s = self.schedule()
        self.assertEqual(s.state(utc(2026, 11, 18, 7, 59))["mode"], "sleep")
        self.assertEqual(s.state(utc(2026, 11, 18, 8, 0))["mode"], "active")
        self.assertEqual(s.state(utc(2026, 11, 18, 17, 59))["mode"], "active")
        self.assertEqual(s.state(utc(2026, 11, 18, 18, 0))["mode"], "sleep")

    def test_work_hours_are_a_complete_lit_day(self):
        schedule=self.schedule(wake="08:30",sleep="17:15")
        self.assertEqual(schedule.day_timeline(), {
            "sunrise":"08:30", "daylight":"09:00", "sunset":"15:00",
            "nightfall":"16:00", "lights_out":"17:15"})
        for h,m,phase in ((8,29,"lights_out"),(8,30,"dawn"),
                          (8,59,"dawn"),(9,0,"day"),
                          (14,59,"day"),(15,0,"dusk"),
                          (15,59,"dusk"),(16,0,"night"),
                          (17,14,"night"),(17,15,"lights_out")):
            self.assertEqual(schedule.day_phase(utc(2026,11,18,h,m)),phase)
        self.assertEqual(schedule.day_phase(utc(2026,11,23,12)),"lights_out")
        shifted=self.schedule(wake="09:00",sleep="18:00")
        self.assertEqual(shifted.day_timeline()["sunset"],"15:41")
        self.assertEqual(shifted.day_timeline()["nightfall"],"16:42")
        self.assertEqual(self.schedule(enabled=False).day_phase(utc(2026,11,18,23)),"day")

    def test_weekend_and_public_holiday_stay_dark(self):
        s = self.schedule()
        self.assertEqual(s.state(utc(2026, 11, 21, 12))["mode"], "sleep")
        self.assertEqual(s.state(utc(2026, 11, 22, 12))["mode"], "sleep")
        self.assertEqual(s.state(utc(2026, 11, 23, 12))["mode"], "sleep")
        self.assertEqual(s.state(utc(2026, 11, 24, 9))["mode"], "active")

    def test_monday_holiday_skips_until_tuesday(self):
        s = self.schedule()
        state = s.state(utc(2026, 11, 20, 18))
        self.assertEqual(state["mode"], "sleep")
        self.assertEqual(state["next_wake"], utc(2026, 11, 24, 8))
        self.assertEqual(s.next_timer_seconds(utc(2026, 11, 20, 18)), 12 * 3600)

    def test_substitute_and_between_holidays(self):
        s = self.schedule()
        for date in [(2026, 5, 6), (2026, 9, 22), (2027, 3, 22)]:
            self.assertEqual(s.state(utc(*date, 12))["mode"], "sleep")

    def test_unknown_holiday_year_fails_open(self):
        self.assertEqual(self.schedule().state(utc(2028, 3, 1, 9))["mode"], "unknown")
        self.assertIsNone(self.schedule().next_timer_seconds(utc(2028, 3, 1, 9)))

    def test_can_disable_scheduling(self):
        s = self.schedule(enabled=False)
        self.assertEqual(s.state(utc(2030, 1, 1))["mode"], "active")

    def test_no_overnight_or_broken_values(self):
        base = self.schedule().config
        for changes in ({"wake": "18:00", "sleep": "08:00"},
                        {"wake": "xx:00"}, {"timezone": "UTC"},
                        {"enabled": "yes"}, {"sleep": "24:00"}):
            data = dict(base)
            data.update(changes)
            with self.assertRaises(ValueError):
                validate_schedule(data)


if __name__ == "__main__":
    unittest.main()
