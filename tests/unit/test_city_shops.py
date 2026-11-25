"""The Metropolis's shops (cityshops.py): eight kinds of shop, each with its own stock and its own buying rules,
traded with through the Peddler's shop window; signs by their doors; and a dead merchant's stock left behind.

Unit tests; the rest are in tests/acceptance/test_city_shops.py."""
import random
import unittest
from cruel.entities import enemies
from cruel.inventory import recipes
from cruel.inventory import relics
from cruel.inventory import resources
from cruel.world import cityshops
from cruel.world import peddler


class ShopKindTests(unittest.TestCase):
    """What each kind of shop sells and buys."""

    def test_there_are_eight_kinds_and_everything_they_list_exists(self):
        self.assertEqual(len(cityshops.SHOP_KINDS), 8)
        for kind, kindDetails in cityshops.SHOP_KINDS.items():
            self.assertTrue(kindDetails["recipes"] or kindDetails["materials"], kind)
            for recipeId in kindDetails["recipes"]:
                self.assertIn(recipeId, recipes.RECIPES_BY_ID)
            for materialId in list(kindDetails["materials"]) + kindDetails["alsoBuys"]:
                self.assertIn(materialId, resources.MATERIALS)

    def test_a_stock_is_six_to_nine_of_its_own_kind_of_thing_never_a_relic_or_a_station(self):
        random.seed(3)
        for kind, kindDetails in cityshops.SHOP_KINDS.items():
            for _ in range(30):
                stock = cityshops.rollStock(kind)
                self.assertTrue(6 <= len(stock) <= 9)
                for ware in stock:
                    self.assertNotIn(ware.kind, ("relic", "station", "pouch"))
                    if ware.kind == "material":
                        self.assertIn(ware.materialId, kindDetails["materials"])
                        self.assertEqual(ware.amount, kindDetails["materials"][ware.materialId])
                    else:
                        self.assertIn(ware.recipeId, kindDetails["recipes"])
                        self.assertFalse(relics.isRelic(ware.item))

    def test_a_lot_of_materials_costs_like_everything_else(self):
        ironLot = cityshops.materialLot("iron_ore", 5)
        self.assertEqual(ironLot.price, round(peddler.PRICE_MULTIPLIER * peddler.materialWorth("iron_ore") * 5))
        self.assertEqual(ironLot.name, "Iron Ore x5")


class TradingRuleTests(unittest.TestCase):
    """Who trades and what they buy."""

    def setUp(self):
        self.oreMerchant = enemies.DwellerMerchant()
        self.oreMerchant.shopKind = "ore"
        self.weaponsmith = enemies.DwellerMerchant()
        self.weaponsmith.shopKind = "weapons"
        self.grayPeddler = enemies.GrayPeddler()

    def test_calm_merchants_and_the_calm_peddler_trade_hostile_ones_do_not(self):
        self.assertTrue(cityshops.isTrader(self.oreMerchant))
        self.assertTrue(cityshops.isTrader(self.grayPeddler))
        self.oreMerchant.hostile = True
        self.assertFalse(cityshops.isTrader(self.oreMerchant))
        self.assertFalse(cityshops.isTrader(enemies.DwellerCitizen()))

    def test_a_shop_only_buys_its_own_kind_of_thing(self):
        ironSword = recipes.RECIPES_BY_ID["iron_sword"].build("Common")
        self.assertTrue(cityshops.buysItem(self.weaponsmith, ironSword))
        self.assertFalse(cityshops.buysItem(self.oreMerchant, ironSword))
        self.assertTrue(cityshops.buysMaterial(self.oreMerchant, "iron_ore"))
        self.assertTrue(cityshops.buysMaterial(self.oreMerchant, "scrap"), "it buys scrap without selling it")
        self.assertFalse(cityshops.buysMaterial(self.oreMerchant, "wood"))

    def test_the_peddler_still_buys_anything(self):
        self.assertTrue(cityshops.buysItem(self.grayPeddler, relics.make("lantern")))
        self.assertTrue(cityshops.buysMaterial(self.grayPeddler, "wood"))

    def test_a_shop_pays_better_than_the_peddler_for_its_materials(self):
        self.assertEqual(cityshops.materialsPerGold(self.oreMerchant), 6)
        self.assertEqual(cityshops.materialsPerGold(self.grayPeddler), 11)

    def test_the_window_is_titled_with_the_shops_name(self):
        self.assertEqual(cityshops.traderName(self.oreMerchant), "Ore Exchange")
        self.assertEqual(cityshops.traderName(self.grayPeddler), "The Gray Peddler")


if __name__ == "__main__":
    unittest.main()
