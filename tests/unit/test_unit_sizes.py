"""Unit sizes (occupancy.py): small units share a space two at a time, or with a part of a Fire Giant; medium ones
take a whole space.

Unit tests; the rest are in tests/integration/test_unit_sizes.py, tests/acceptance/test_unit_sizes.py."""
import unittest
from cruel.entities import enemies
from cruel.world import occupancy


class SizeTests(unittest.TestCase):
    def test_each_unit_has_its_size(self):
        small = [enemies.DireRat(), enemies.Goblin(), enemies.GoblinBuilder(), enemies.GoblinFarmer(), enemies.DwellerCitizen(),
                 enemies.DwellerNoble(), enemies.DwellerGuard(), enemies.DwellerMerchant(), enemies.DewGrub(grown=False)]
        medium = [enemies.GoblinChief(), enemies.DireMole(), enemies.DewGrub(), enemies.SpiralOrganizer(), enemies.Unsealed()]
        for unit in small:
            self.assertEqual(occupancy.sizeOf(unit), occupancy.SMALL, unit.name)
        for unit in medium:
            self.assertEqual(occupancy.sizeOf(unit), occupancy.MEDIUM, unit.name)
        self.assertEqual(occupancy.sizeOf(enemies.FireGiant()), occupancy.LARGE)

    def test_a_young_grub_grows_out_of_being_small(self):
        grub = enemies.DewGrub(grown=False)
        grub.growUp()
        self.assertEqual(occupancy.sizeOf(grub), occupancy.MEDIUM)


if __name__ == "__main__":
    unittest.main()
