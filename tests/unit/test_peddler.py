"""The Gray Peddler (peddler.py): a trader who turns up unannounced on a new floor, with a signpost by the arrival
spot, a room of Peddler's Stone with one entrance, a shop built like the Inventory, and a fight if you hurt him.

Unit tests; the rest are in tests/integration/test_peddler.py, tests/acceptance/test_peddler.py."""
import unittest
from cruel.inventory import items
from cruel.inventory import relics
from cruel.world import peddler
from tests.helpers.peddler import SHEET_PRICES, recipeNamed


class PriceTests(unittest.TestCase):
    """What he charges and what he pays."""

    def test_every_price_matches_the_design_sheet(self):
        for name, sheetPrice in SHEET_PRICES.items():
            with self.subTest(name):
                self.assertEqual(peddler.recipePrice(recipeNamed(name)), sheetPrice)

    def test_a_made_material_is_worth_what_goes_into_it(self):
        self.assertEqual(peddler.materialWorth("wood"), 1)
        self.assertEqual(peddler.materialWorth("copper_ore"), 2)
        self.assertEqual(peddler.materialWorth("handle"), 2)  # 2 Wood
        self.assertEqual(peddler.materialWorth("glass"), 4)   # 2 Sand and a Coal

    def test_better_quality_gear_costs_more(self):
        ironSword = recipeNamed("Iron Sword")
        prices = [peddler.recipePrice(ironSword, quality) for quality in ("Common", "Fine", "Masterwork")]
        self.assertEqual(prices, [66, 82, 99])

    def test_he_pays_a_quarter_for_your_items(self):
        fineIronSword = recipeNamed("Iron Sword").build("Fine")
        self.assertEqual(peddler.offerFor(fineIronSword), 82 // 4)
        self.assertEqual(peddler.offerFor(relics.make("lantern")), peddler.RELIC_PRICE // 4)

    def test_he_pays_at_least_one_gold_for_anything(self):
        strangeTrinket = items.equipment("Damage", "Strange Trinket", "Hands", 1)
        self.assertEqual(peddler.offerFor(strangeTrinket), 1)

    def test_materials_sell_eleven_for_one_gold(self):
        self.assertEqual(peddler.offerForMaterial(40), (3, 33))
        self.assertEqual(peddler.offerForMaterial(11), (1, 11))
        self.assertEqual(peddler.offerForMaterial(10), (0, 0))


if __name__ == "__main__":
    unittest.main()
