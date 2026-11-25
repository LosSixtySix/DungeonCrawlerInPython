"""The Dwellers at work on their city's works floors (dwellerwork.py): miners breaking seams, farmers tending crops
and Dew Grubs, and everything they get taken to the storehouse chests.

Unit tests; the rest are in tests/integration/test_dweller_work.py, tests/acceptance/test_dweller_work.py."""
import unittest
from cruel.graphics import sprites
from cruel.inventory import resources
from cruel.world import cityshops


class DewTests(unittest.TestCase):
    def test_dew_is_a_material_the_grocer_deals_in(self):
        self.assertEqual(resources.materialName("dew"), "Dew")
        self.assertIn("dew", cityshops.SHOP_KINDS["food"]["materials"])

    def test_the_grub_has_a_picture(self):
        self.assertIn("Dew Grub", sprites.ENEMY_SPRITES)


if __name__ == "__main__":
    unittest.main()
