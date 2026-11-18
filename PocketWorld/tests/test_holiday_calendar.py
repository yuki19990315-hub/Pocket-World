"""Check the official holiday snapshot bundled for future sleep scheduling.

This test validates source data only; it does not claim that device scheduling
or deep sleep is implemented.
"""
import datetime
import json
import os
import unittest

DATA_FILE = os.path.join(os.path.dirname(__file__), "..", "firmware", "assets", "jp_holidays.json")


class TestOfficialHolidayData(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(DATA_FILE, encoding="utf-8") as handle:
            cls.data = json.load(handle)

    def test_coverage_is_explicit(self):
        self.assertEqual(self.data["country"], "JP")
        self.assertEqual(self.data["timezone"], "Asia/Tokyo")
        self.assertEqual(self.data["years"], [2026, 2027])
        self.assertEqual(set(self.data["dates"]), {"2026", "2027"})

    def test_official_2026_2027_counts(self):
        self.assertEqual(len(self.data["dates"]["2026"]), 18)
        self.assertEqual(len(self.data["dates"]["2027"]), 17)

    def test_all_dates_are_valid_and_in_correct_year(self):
        for year, entries in self.data["dates"].items():
            for day, name in entries.items():
                with self.subTest(day=day):
                    self.assertEqual(datetime.date.fromisoformat(day).year, int(year))
                    self.assertTrue(name)

    def test_substitute_and_between_holidays(self):
        self.assertIn("2026-05-06", self.data["dates"]["2026"])
        self.assertIn("2026-09-22", self.data["dates"]["2026"])
        self.assertIn("2027-03-22", self.data["dates"]["2027"])
        self.assertNotIn("2028", self.data["dates"])

if __name__ == "__main__":
    unittest.main()
