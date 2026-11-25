"""The Metropolis's shops (cityshops.py): eight kinds of shop, each with its own stock and its own buying rules,
traded with through the Peddler's shop window; signs by their doors; and a dead merchant's stock left behind.

Acceptance tests; the rest are in tests/unit/test_city_shops.py."""
import random
import unittest
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
        game = self.game
        game.onInteract()
        self.assertEqual(game.focus, "shop")
        self.assertEqual(game.windowSpec("shop")["title"], "Ore Exchange")
        self.assertEqual(self.merchant.hp, self.merchant.maxHp)

    def test_buying_a_lot_puts_it_in_your_pouch(self):
        game = self.game
        game.player.gold = 100
        game.onInteract()
        price = self.merchant.wares[0].price
        game.shopEnter()
        self.assertEqual(game.player.materials.get("iron_ore"), 5)
        self.assertEqual(game.player.gold, 100 - price)

    def test_a_full_pouch_cannot_take_a_lot(self):
        game = self.game
        game.player.gold = 100
        game.player.materials["iron_ore"] = game.player.pouchLimit - 2
        game.onInteract()
        game.shopEnter()
        self.assertEqual(game.shopMessage, "No room in your pouch")

    def test_the_sell_tab_only_lists_what_the_shop_buys_at_its_rate(self):
        game = self.game
        game.player.addItemToInventory(recipes.RECIPES_BY_ID["iron_sword"].build("Common"))
        game.player.materials = {"iron_ore": 13, "wood": 40}
        game.onInteract()
        game.toggleShopTab()
        self.assertEqual(game.shopEntries(), [("material", "iron_ore")])
        game.shopEnter(everything=True)
        self.assertEqual(game.player.materials["iron_ore"], 1, "two lots of 6")

    def pressInteract(self, modifierKeys=0):
        key = self.game.settings.hotkeys["interact"]
        self.game.onKeyDown(pygame.event.Event(pygame.KEYDOWN, key=key, mod=modifierKeys, unicode="e", scancode=0))
        self.game.onKeyUp(pygame.event.Event(pygame.KEYUP, key=key, mod=modifierKeys))

    def test_the_interact_key_opens_the_shop_and_then_buys(self):
        game = self.game
        game.player.gold = 100
        self.pressInteract()
        self.assertEqual(game.focus, "shop")
        self.assertEqual(game.player.materials.get("iron_ore"), None, "opening the shop buys nothing")
        self.pressInteract()
        self.assertEqual(game.player.materials.get("iron_ore"), 5)

    def test_ctrl_interact_sells_every_whole_lot(self):
        game = self.game
        game.player.materials = {"iron_ore": 20}
        self.pressInteract()
        game.toggleShopTab()
        self.pressInteract(pygame.KMOD_LCTRL)
        self.assertEqual(game.player.materials["iron_ore"], 2, "three lots of 6")

    def test_the_hints_name_the_interact_key(self):
        game = self.game
        self.pressInteract()
        hints = [text for style, text, _ in game.windowSpec("shop")["detail"] if style == "hint"]
        self.assertEqual(hints, [f"{game.interactKeyName()}  buy      Tab  sell"])

    def test_attacking_a_merchant_turns_it_hostile_and_closes_its_shop(self):
        game = self.game
        game.enemyDodge = lambda target, damage, position: damage
        game.player.DealDamage = lambda: 3
        game.onInteract()
        game.onInteract(forceAttack=True)
        self.assertTrue(self.merchant.hostile)
        game.enemyTurn()
        self.assertNotIn("shop", game.openWindows)
        self.assertFalse(cityshops.isTrader(self.merchant))

    def test_a_dead_merchants_stock_stays_in_a_city_chest(self):
        game = self.game
        game.killEnemy(self.merchantSpot)
        tile = game.grid[self.merchantSpot]
        self.assertEqual(tile[0], CHEST)
        self.assertIsInstance(tile[2], items.CityChest)
        self.assertEqual(sorted((stack.materialId, stack.amount) for stack in tile[2]), [("coal", 5), ("iron_ore", 5)])

    def test_taking_a_dead_merchants_stock_in_sight_of_someone_is_stealing(self):
        game = self.game
        game.killEnemy(self.merchantSpot)
        watching = enemies.DwellerCitizen()
        watching.home = self.spot(33, 21)
        game.grid[self.spot(33, 21)] = [ENEMY, 1, watching]
        game.EnemyPositions.add(self.spot(33, 21))
        game.roomItems = game.getItemsFromGrid()
        game.windowSel["items"] = 0
        game.pickUpItem()
        self.assertTrue(watching.hostile)

    def test_looking_at_a_merchant_names_its_shop(self):
        self.assertEqual(self.game.lookingAt(), "Dweller Merchant (Ore Exchange)")


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
        game = self.game
        signSpot, kind = self.signs()[0]
        support.placePlayer(game, next(spot for spot in game.neighbors(signSpot) if game.grid[spot][0] == FLOOR))
        before = game.playerPositionFlat
        game.movePlayer(signSpot)
        self.assertEqual(game.playerPositionFlat, before)
        game.PlayerLookPosition = signSpot
        self.assertEqual(game.lookingAt(), f"Sign: {cityshops.shopName(kind)}")

    def test_the_city_with_its_signs_draws(self):
        game = self.game
        for tile in game.grid.values():
            tile[1] = 1
        game.change = True
        game.setPositionsVisible()
        game.draw()


if __name__ == "__main__":
    unittest.main()
