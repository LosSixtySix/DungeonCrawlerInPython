"""The Glowrock Pouch (a carried item: playerClass.GLOW_POUCH) and the Drop Glowrock hotkey (G by default:
gameManager.dropGlowrock). The pouch holds recipes.GLOWROCK_POUCH_HOLDS Glowrocks in one inventory slot; new
Glowrocks go in it first. G sets one Glowrock down at your feet, from a pouch if one holds any, else a loose one.

Integration tests."""
import unittest

import pygame

from cruel.core import settings
from cruel.entities import playerClass
from cruel.inventory import items, recipes
from tests.helpers.gamemanager import PILE, keyDown, newGame, standInOpenFloor

HOLDS = recipes.GLOWROCK_POUCH_HOLDS


def glowrock():
    return recipes.RECIPES_BY_ID["glowrock"].makeItem(0, 0)


def pouch(quality="Common"):
    return recipes.RECIPES_BY_ID["glowrock_pouch"].build(quality)


class PouchTest(unittest.TestCase):
    def setUp(self):
        self.game = newGame()
        self.here = standInOpenFloor(self.game)
        self.player = self.game.player
        self.player.inventory = []

    def looseGlowrocks(self):
        return sum(playerClass.countOf(held) for held in self.player.inventory if items.isGlowrock(held))

    def pouchRocks(self):
        return len(playerClass.rocksIn(next(held for held in self.player.inventory if playerClass.isGlowPouch(held))))

    def glowrocksAtFeet(self):
        ground = self.game.groundAt(self.here)
        return sum(1 for item in ground[2].items if items.isGlowrock(item)) if ground[0] == PILE else 0


class RecipeTests(unittest.TestCase):
    def test_it_is_made_at_the_workbench_as_a_carried_item(self):
        recipe = recipes.RECIPES_BY_ID["glowrock_pouch"]
        self.assertEqual((recipe.station, recipe.kind), ("workbench", "item"))
        made = recipe.build("Fine")
        self.assertTrue(playerClass.isGlowPouch(made))
        self.assertEqual(made.bonus, HOLDS, "quality only names it")
        self.assertEqual(made.name, "Fine Glowrock Pouch")
        self.assertEqual(playerClass.rocksIn(made), [])

    def test_crafting_one_puts_it_in_your_inventory(self):
        game = newGame()
        player = game.player
        player.inventory = []
        player.stations.add("workbench")
        player.materials.update({"hide": 2, "wood": 1})
        game.finishCraft(recipes.RECIPES_BY_ID["glowrock_pouch"])
        self.assertEqual(len(player.inventory), 1)
        self.assertTrue(playerClass.isGlowPouch(player.inventory[0]))
        self.assertEqual(player.materials.get("hide", 0), 0)


class CarryingTests(PouchTest):
    def test_new_glowrocks_go_in_the_pouch_first(self):
        player = self.player
        player.addItemToInventory(pouch())
        for _ in range(3):
            self.assertTrue(player.addItemToInventory(glowrock()))
        self.assertEqual(self.pouchRocks(), 3)
        self.assertEqual(len(player.inventory), 1, "still just the pouch's slot")

    def test_a_full_pouch_leaves_the_rest_loose(self):
        player = self.player
        player.addItemToInventory(pouch())
        for _ in range(HOLDS + 2):
            player.addItemToInventory(glowrock())
        self.assertEqual(self.pouchRocks(), HOLDS)
        self.assertEqual(self.looseGlowrocks(), 2)

    def test_getting_a_pouch_gathers_your_loose_glowrocks(self):
        player = self.player
        for _ in range(3):
            player.addItemToInventory(glowrock())
        player.addItemToInventory(items.consumable("Healing Potion", 3, "Heal"))
        self.assertEqual(self.looseGlowrocks(), 3)
        player.addItemToInventory(pouch())
        self.assertEqual(self.pouchRocks(), 3)
        self.assertEqual(self.looseGlowrocks(), 0)
        self.assertEqual([held.name for held in player.inventory], ["Healing Potion", "Glowrock Pouch"])

    def test_room_for_glowrocks_counts_the_pouch(self):
        player = self.player
        player.inventoryLimit = 1
        player.addItemToInventory(pouch())
        self.assertEqual(player.roomFor(glowrock()), HOLDS)
        self.assertEqual(player.roomFor(items.consumable("Healing Potion", 3, "Heal")), 0)

    def test_its_slot_shows_how_full_it_is(self):
        self.player.addItemToInventory(pouch())
        self.player.addItemToInventory(glowrock())
        self.assertEqual(self.game.windowSpec("inventory")["items"], [f"Glowrock Pouch (1/{HOLDS})"])


class DropKeyTests(PouchTest):
    def test_g_is_drop_glowrock_by_default_and_in_the_hotkeys_menu(self):
        self.assertEqual(settings.DEFAULT_HOTKEYS["drop_glowrock"], pygame.K_g)
        self.assertEqual(settings.ACTION_LABELS["drop_glowrock"], "Drop Glowrock")
        self.assertEqual(settings.DEFAULT_HOTKEYS["materials"], pygame.K_p, "the Pouch window keeps P")

    def test_g_drops_a_loose_glowrock_at_your_feet_and_it_glows(self):
        self.player.addItemToInventory(glowrock())
        keyDown(self.game, pygame.K_g)
        self.assertEqual(self.looseGlowrocks(), 0)
        self.assertEqual(self.glowrocksAtFeet(), 1)
        self.game.updateGlowLight()
        self.assertIn(self.here, self.game.glowLight)

    def test_g_takes_from_the_pouch_before_a_loose_one(self):
        player = self.player
        player.addItemToInventory(pouch())
        for _ in range(HOLDS + 1):
            player.addItemToInventory(glowrock())
        keyDown(self.game, pygame.K_g)
        self.assertEqual(self.pouchRocks(), HOLDS - 1)
        self.assertEqual(self.looseGlowrocks(), 1)
        self.assertEqual(self.glowrocksAtFeet(), 1)

    def test_an_empty_pouch_lets_g_use_a_loose_one(self):
        player = self.player
        player.inventory = [pouch()]
        player.inventory.append(glowrock())  # (loose: put straight in, past the pouch)
        keyDown(self.game, pygame.K_g)
        self.assertEqual(self.looseGlowrocks(), 0)
        self.assertEqual(self.glowrocksAtFeet(), 1)

    def test_g_with_no_glowrock_does_nothing(self):
        self.player.inventory = [pouch(), items.consumable("Healing Potion", 3, "Heal")]
        keyDown(self.game, pygame.K_g)
        self.assertEqual(self.game.groundAt(self.here)[0], 0)
        self.assertEqual(len(self.player.inventory), 2)

    def test_g_works_with_a_window_open_and_is_a_free_action(self):
        game = self.game
        self.player.addItemToInventory(glowrock())
        keyDown(game, settings.DEFAULT_HOTKEYS["inventory"])
        keyDown(game, pygame.K_g)
        self.assertEqual(self.glowrocksAtFeet(), 1)
        self.assertFalse(game.enemyMove)

    def test_enter_on_the_pouch_sets_one_down(self):
        game = self.game
        self.player.addItemToInventory(pouch())
        self.player.addItemToInventory(glowrock())
        game.focus = "inventory"
        game.windowSel["inventory"] = 0
        game.onWindowEnter("inventory")
        self.assertEqual(self.pouchRocks(), 0)
        self.assertEqual(self.glowrocksAtFeet(), 1)
        self.assertTrue(playerClass.isGlowPouch(self.player.inventory[0]), "the pouch stays")

    def test_rebound_drop_follows_its_new_key(self):
        game = self.game
        game.settings.rebind("drop_glowrock", pygame.K_z)
        try:
            self.player.addItemToInventory(glowrock())
            keyDown(game, pygame.K_g)
            self.assertEqual(self.glowrocksAtFeet(), 0)
            keyDown(game, pygame.K_z)
            self.assertEqual(self.glowrocksAtFeet(), 1)
        finally:
            game.settings.resetHotkeys()


if __name__ == "__main__":
    unittest.main()
