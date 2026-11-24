"""The history of runs that ended in death, kept in attempts.json."""
import datetime
import json
import os
import shutil
import tempfile
import unittest

import tests  # noqa: F401
from cruel.core import attempts


class AttemptHistoryTests(unittest.TestCase):
    """Recording deaths, reading the history back, and ranking it by depth."""

    def setUp(self):
        self.tempFolder = tempfile.mkdtemp()
        self.attemptsFile = os.path.join(self.tempFolder, "attempts.json")

    def tearDown(self):
        shutil.rmtree(self.tempFolder, ignore_errors=True)

    def test_no_file_means_no_attempts(self):
        self.assertEqual(attempts.load(self.attemptsFile), [])

    def test_a_corrupt_file_means_no_attempts(self):
        with open(self.attemptsFile, "w") as attemptsFile:
            attemptsFile.write("[oops")
        self.assertEqual(attempts.load(self.attemptsFile), [])

    def test_recorded_deaths_are_numbered_and_dated(self):
        attempts.record(3, 120, self.attemptsFile)
        attempts.record(7, 5, self.attemptsFile)
        attemptHistory = attempts.load(self.attemptsFile)
        self.assertEqual([attempt["number"] for attempt in attemptHistory], [1, 2])
        self.assertEqual(attemptHistory[1]["deepest"], 7)
        self.assertEqual(attemptHistory[1]["gold"], 5)
        self.assertEqual(attemptHistory[0]["date"], datetime.date.today().isoformat())

    def test_entries_without_a_depth_are_skipped(self):
        with open(self.attemptsFile, "w") as attemptsFile:
            json.dump([{"number": 1, "deepest": 2}, "junk", {"number": 2}], attemptsFile)
        self.assertEqual(attempts.load(self.attemptsFile), [{"number": 1, "deepest": 2}])

    def test_deepest_runs_rank_first_and_ties_go_to_the_earlier_run(self):
        attemptHistory = [{"number": 1, "deepest": 2}, {"number": 2, "deepest": 5},
                          {"number": 3, "deepest": 5}, {"number": 4, "deepest": 1}]
        ranking = attempts.deepestFirst(attemptHistory)
        self.assertEqual([attempt["number"] for attempt in ranking], [2, 3, 1, 4])


if __name__ == "__main__":
    unittest.main()
