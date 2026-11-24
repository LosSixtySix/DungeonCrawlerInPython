"""The game's version number, which release.ps1 bumps and the updater compares."""
import unittest

import tests  # noqa: F401
from cruel.core import updater, version


class VersionNumberTests(unittest.TestCase):
    """VERSION must stay a plain x.y.z the updater can compare."""

    def test_the_version_is_three_numbers_separated_by_dots(self):
        self.assertRegex(version.VERSION, r"^\d+\.\d+\.\d+$")

    def test_the_updater_reads_the_version_as_three_numbers(self):
        versionParts = updater.parseVersion(version.VERSION)
        self.assertEqual(len(versionParts), 3)
        self.assertEqual(".".join(map(str, versionParts)), version.VERSION)


if __name__ == "__main__":
    unittest.main()
