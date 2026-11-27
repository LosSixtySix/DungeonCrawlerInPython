"""The Gray Peddler (peddler.py): a trader who turns up unannounced on a new floor, with a signpost by the arrival
spot, a room of Peddler's Stone with one entrance, a shop built like the Inventory, and a fight if you hurt him.

Acceptance tests; the rest are in tests/unit/test_peddler.py, tests/integration/test_peddler.py."""
import os
import tempfile
import unittest
import pygame
from cruel.core import gamemanager
from cruel.inventory import resources
from cruel.world import peddler
from tests import support
from tests.helpers.peddler import keyPress, peddlerFloor, recipeNamed, standFacing


class ShopWindowTests(unittest.TestCase):
    """Opening his shop and using it with the keys."""

    def setUp(self):
        self.game, self.traderSpot, self.trader = peddlerFloor()
        standFacing(self.game, self.traderSpot)

    def test_interacting_with_him_opens_his_shop_without_hurting_him(self):
        self.game.onInteract()
        self.assertEqual(self.game.focus, "shop")
        self.assertEqual(self.trader.hp, self.trader.maxHp)
        self.assertFalse(self.trader.hostile)

    def test_enter_buys_the_selected_ware(self):
        self.game.player.gold = 1000
        self.game.onInteract()
        firstWare = self.trader.wares[0]
        keyPress(self.game, pygame.K_RETURN)
        self.assertNotIn(firstWare, self.trader.wares)
        self.assertEqual(self.game.player.gold, 1000 - firstWare.price)
        self.assertTrue(self.game.shopMessage.startswith("Bought"))

    def test_tab_switches_to_selling_and_ctrl_enter_sells_every_lot(self):
        self.game.player.materials = {"stone": 40}
        self.game.onInteract()
        keyPress(self.game, self.game.settings.hotkeys["cycle"])
        self.assertEqual(self.game.shopTab, 1)
        self.assertEqual(self.game.focus, "shop", "Tab doesn't leave the shop")
        keyPress(self.game, pygame.K_RETURN, pygame.KMOD_LCTRL)
        self.assertEqual(self.game.player.materials["stone"], 7)

    def test_the_sell_tab_lists_your_pack_then_your_pouch(self):
        self.game.player.addItemToInventory(recipeNamed("Iron Sword").build("Fine"))
        self.game.player.materials = {"wood": 23, "stone": 5}
        self.game.onInteract()
        self.game.toggleShopTab()
        self.assertEqual(self.game.shopEntries(), [("item", 0), ("material", "wood"), ("material", "stone")])
        slots = self.game.windowSpec("shop")["slots"]
        self.assertEqual(slots[0], ("Fine Iron Sword", "20", False))
        self.assertEqual(slots[1], ("Wood x23", "2", False))
        self.assertEqual(slots[2], ("Stone x5", "-", True), "fewer than 11: greyed out")

    def test_the_selection_scrolls_into_view_on_a_long_list(self):
        self.game.player.materials = {materialId: 11 for materialId in list(resources.MATERIALS)[:25]}
        self.game.onInteract()
        self.game.toggleShopTab()
        for _ in range(4):
            self.game.moveSelection(0, 1)
        self.assertEqual(self.game.shopScroll, 4 - self.game.painter.SHOP_ROWS + 1)

    def test_walking_away_closes_the_shop(self):
        self.game.onInteract()
        support.placePlayer(self.game, self.traderSpot - 3)
        self.game.enemyTurn()
        self.assertNotIn("shop", self.game.openWindows)

    def test_the_shop_window_draws_on_both_tabs(self):
        self.game.player.materials = {"stone": 40}
        self.game.onInteract()
        for _ in range(2):
            self.game.change = True
            self.game.draw()
            self.game.toggleShopTab()

    def test_its_details_show_the_price_and_hide_the_inventory_keys(self):
        self.game.onInteract()
        detail = self.game.windowSpec("shop")["detail"]
        self.assertIn(("price", "PRICE", f"{self.trader.wares[0].price} gold"), detail)
        hints = [text for style, text, _ in detail if style == "hint"]
        self.assertEqual(hints, [f"{self.game.interactKeyName()}  buy      Tab  sell"])  # (E by default)


class FloorDetailTests(unittest.TestCase):
    """The signpost and his name on the map, and saving."""

    def setUp(self):
        self.game, self.traderSpot, self.trader = peddlerFloor()

    def signpostSpot(self):
        return next(spot for spot, tile in self.game.grid.items() if tile[0] == peddler.SIGNPOST)

    def test_the_signpost_blocks_the_way(self):
        before = self.game.playerPositionFlat
        self.game.movePlayer(self.signpostSpot())
        self.assertEqual(self.game.playerPositionFlat, before)

    def test_looking_at_the_signpost_says_someone_is_trading(self):
        signpostSpot = self.signpostSpot()
        self.game.PlayerLookPosition = signpostSpot
        self.assertIn("someone is trading on this floor", self.game.lookingAt())

    def test_looking_at_him_says_trader_then_hostile(self):
        self.game.PlayerLookPosition = self.traderSpot
        self.assertEqual(self.game.lookingAt(), "The Gray Peddler (trader)")
        peddler.provoke(self.game, self.trader, self.traderSpot)
        self.assertEqual(self.game.lookingAt(), "The Gray Peddler (hostile)")

    def test_saving_keeps_him_and_his_stock(self):
        stockNames = [ware.name for ware in self.trader.wares]
        saveFile = os.path.join(tempfile.mkdtemp(), "peddler-save.pkl")
        gamemanager.gameManager.saveGame(self.game, saveFile)
        loadedGame = support.newGame()
        self.assertTrue(loadedGame.loadGame(saveFile))
        loadedGame.changeLevel(1) if loadedGame.level != 1 else None
        loadedTrader = loadedGame.grid[self.traderSpot][2]
        self.assertTrue(peddler.isPeddler(loadedTrader))
        self.assertEqual([ware.name for ware in loadedTrader.wares], stockNames)

    def test_the_floor_with_him_draws(self):
        for tile in self.game.grid.values():
            tile[1] = 1
        self.game.change = True
        self.game.setPositionsVisible()
        self.game.draw()


if __name__ == "__main__":
    unittest.main()
