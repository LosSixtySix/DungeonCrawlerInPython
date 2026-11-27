"""The Metropolis's shops (cityshops.py): eight kinds of shop, each with its own stock and its own buying rules,
traded with through the Peddler's shop window; signs by their doors; and a dead merchant's stock left behind.

Acceptance tests; the rest are in tests/unit/test_city_shops.py."""
import random
import unittest
from unittest import mock
import pygame
from cruel.entities import enemies
from cruel.inventory import items
from cruel.inventory import recipes
from cruel.world import cityshops
from cruel.world import dwellers
from cruel.world import metropolis
from tests import support
from tests.helpers.expansion import blankFloor
from tests.helpers.city_shops import CHEST, ENEMY, FACING_RIGHT, FLOOR


class ShopWindowTests(unittest.TestCase):
    """Trading at a city shop."""

    def setUp(self):
        random.seed(6)
        self.game = support.newGame()
        blankFloor(self.game)
        self.game.proportion = metropolis.METROPOLIS
        self.rowLength = self.game.rowLength
        self.merchantSpot = self.spot(30, 20)
        self.merchant = enemies.DwellerMerchant()
        self.merchant.shopKind = "ore"
        self.merchant.home = self.merchantSpot
        self.merchant.wares = [cityshops.materialLot("iron_ore", 5), cityshops.materialLot("coal", 5)]
        self.game.grid[self.merchantSpot] = [ENEMY, 1, self.merchant]
        self.game.EnemyPositions.add(self.merchantSpot)
        support.placePlayer(self.game, self.merchantSpot - 1)
        self.game.currentLocation = [FLOOR, 1]
        self.game.player.playerDirection = FACING_RIGHT
        self.game.setLookPosition()

    def spot(self, column, row):
        return column + row * self.rowLength

    def test_interacting_with_a_merchant_opens_its_shop(self):
        self.game.onInteract()
        self.assertEqual(self.game.focus, "shop")
        self.assertEqual(self.game.windowSpec("shop")["title"], "Ore Exchange")
        self.assertEqual(self.merchant.hp, self.merchant.maxHp)

    def test_buying_a_lot_puts_it_in_your_pouch(self):
        self.game.player.gold = 100
        self.game.onInteract()
        price = self.merchant.wares[0].price
        self.game.shopEnter()
        self.assertEqual(self.game.player.materials.get("iron_ore"), 5)
        self.assertEqual(self.game.player.gold, 100 - price)

    def test_a_full_pouch_cannot_take_a_lot(self):
        self.game.player.gold = 100
        self.game.player.materials["iron_ore"] = self.game.player.pouchLimit - 2
        self.game.onInteract()
        self.game.shopEnter()
        self.assertEqual(self.game.shopMessage, "No room in your pouch")

    def test_the_sell_tab_only_lists_what_the_shop_buys_at_its_rate(self):
        self.game.player.addItemToInventory(recipes.RECIPES_BY_ID["iron_sword"].build("Common"))
        self.game.player.materials = {"iron_ore": 13, "wood": 40}
        self.game.onInteract()
        self.game.toggleShopTab()
        self.assertEqual(self.game.shopEntries(), [("material", "iron_ore")])
        self.game.shopEnter(everything=True)
        self.assertEqual(self.game.player.materials["iron_ore"], 1, "two lots of 6")

    def pressInteract(self, modifierKeys=0):
        key = self.game.settings.hotkeys["interact"]
        self.game.onKeyDown(pygame.event.Event(pygame.KEYDOWN, key=key, mod=modifierKeys, unicode="e", scancode=0))
        self.game.onKeyUp(pygame.event.Event(pygame.KEYUP, key=key, mod=modifierKeys))

    def test_the_interact_key_opens_the_shop_and_then_buys(self):
        self.game.player.gold = 100
        self.pressInteract()
        self.assertEqual(self.game.focus, "shop")
        self.assertEqual(self.game.player.materials.get("iron_ore"), None, "opening the shop buys nothing")
        self.pressInteract()
        self.assertEqual(self.game.player.materials.get("iron_ore"), 5)

    def test_ctrl_interact_sells_every_whole_lot(self):
        self.game.player.materials = {"iron_ore": 20}
        self.pressInteract()
        self.game.toggleShopTab()
        self.pressInteract(pygame.KMOD_LCTRL)
        self.assertEqual(self.game.player.materials["iron_ore"], 2, "three lots of 6")

    def test_the_hints_name_the_interact_key(self):
        self.pressInteract()
        hints = [text for style, text, _ in self.game.windowSpec("shop")["detail"] if style == "hint"]
        self.assertEqual(hints, [f"{self.game.interactKeyName()}  buy      Tab  sell"])

    def test_attacking_a_merchant_turns_it_hostile_and_closes_its_shop(self):
        self.game.enemyDodge = lambda target, damage, position: damage
        self.game.player.DealDamage = lambda: 3
        self.game.onInteract()
        self.game.onInteract(forceAttack=True)
        self.assertTrue(self.merchant.hostile)
        self.game.enemyTurn()
        self.assertNotIn("shop", self.game.openWindows)
        self.assertFalse(cityshops.isTrader(self.merchant))

    def test_a_dead_merchants_stock_stays_in_a_city_chest(self):
        self.game.killEnemy(self.merchantSpot)
        tile = self.game.grid[self.merchantSpot]
        self.assertEqual(tile[0], CHEST)
        self.assertIsInstance(tile[2], items.CityChest)
        self.assertEqual(sorted((stack.materialId, stack.amount) for stack in tile[2]), [("coal", 5), ("iron_ore", 5)])

    def test_taking_a_dead_merchants_stock_in_sight_of_someone_is_stealing(self):
        self.game.killEnemy(self.merchantSpot)
        watching = enemies.DwellerCitizen()
        watching.home = self.spot(33, 21)
        self.game.grid[self.spot(33, 21)] = [ENEMY, 1, watching]
        self.game.EnemyPositions.add(self.spot(33, 21))
        self.game.roomItems = self.game.getItemsFromGrid()
        self.game.windowSel["items"] = 0
        self.game.pickUpItem()
        self.assertTrue(watching.hostile)

    def test_looking_at_a_merchant_names_its_shop(self):
        self.assertEqual(self.game.lookingAt(), "Dweller Merchant (Ore Exchange)")

    def test_with_nothing_to_sell_the_message_is_beside_the_buy_and_sell_tabs(self):
        self.game.player.materials = {}
        self.game.onInteract()
        self.game.toggleShopTab()
        emptyText = self.game.windowSpec("shop")["emptyText"]
        self.assertEqual(self.game.windowSpec("shop")["slots"], [], "nothing to sell")
        drawn = []
        original = self.game.painter.blitText

        def recordText(surface, message, font, color, x, centerY, align="left"):
            drawn.append((str(message), x, centerY))
            return original(surface, message, font, color, x, centerY, align)

        with mock.patch.object(self.game.painter, "blitText", side_effect=recordText):
            self.game.change = True
            self.game.draw()
        sellTab = next((x, centerY) for message, x, centerY in drawn if message == "Sell")
        messages = [(x, centerY) for message, x, centerY in drawn if message == emptyText]
        beside = [(x, centerY) for x, centerY in messages if centerY == sellTab[1]]
        self.assertTrue(beside, "on the tabs' row")
        self.assertGreater(beside[0][0], sellTab[0] + self.game.painter.windowSmallFont.size("Sell")[0], "to the right of them")
        buyTabX = next(x for message, x, centerY in drawn if message == "Buy")
        slotsRight = buyTabX + 5 * self.game.painter.BOX_W  # (the slots start under the Buy tab)
        self.assertFalse([x for x, centerY in messages if centerY != sellTab[1] and x < slotsRight], "not over the empty slots")


class ShopSignTests(unittest.TestCase):
    """The signs beside the shop doors."""

    def setUp(self):
        random.seed(2)
        self.game = support.newGame()
        self.game.saveGame = lambda *args, **kwargs: None
        self.game.metropolisNext = True
        self.game.goToNewLevel()

    def signs(self):
        """(position, shop kind) of each shop's sign (not the mine's or the farm's)."""
        return [(spot, tile[2]) for spot, tile in self.game.grid.items()
                if tile[0] == metropolis.SHOP_SIGN and tile[2] not in metropolis.WORKS]

    def test_each_shop_has_a_sign_naming_its_kind(self):
        merchants = [dweller for _, dweller in dwellers.cityDwellers(self.game) if dweller.role == "merchant"]
        self.assertEqual(sorted(kind for _, kind in self.signs()), sorted(merchant.shopKind for merchant in merchants))

    def test_a_sign_blocks_the_way_and_says_the_shop_name(self):
        signSpot, kind = self.signs()[0]
        support.placePlayer(self.game, next(spot for spot in self.game.neighbors(signSpot) if self.game.grid[spot][0] == FLOOR))
        before = self.game.playerPositionFlat
        self.game.movePlayer(signSpot)
        self.assertEqual(self.game.playerPositionFlat, before)
        self.game.PlayerLookPosition = signSpot
        self.assertEqual(self.game.lookingAt(), f"Sign: {cityshops.shopName(kind)}")

    def test_the_city_with_its_signs_draws(self):
        for tile in self.game.grid.values():
            tile[1] = 1
        self.game.change = True
        self.game.setPositionsVisible()
        self.game.draw()


if __name__ == "__main__":
    unittest.main()
