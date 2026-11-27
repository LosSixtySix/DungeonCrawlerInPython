"""Fibrous Cloth: made by hand from Shadowfern and Emberroot, it stands in for Hide, FIBROUS_CLOTH_PER_HIDE of it for
each Hide a recipe is short (resources.STAND_INS, PlayerClass.have and spendMaterials).

Integration tests."""
import unittest

from cruel.entities.playerClass import PlayerClass
from cruel.inventory import recipes, resources
from tests.support import newGame

PER_HIDE = resources.FIBROUS_CLOTH_PER_HIDE


class RecipeTests(unittest.TestCase):
    def test_it_is_made_by_hand_from_shadowfern_and_emberroot(self):
        recipe = recipes.RECIPES_BY_ID["fibrous_cloth"]
        self.assertEqual((recipe.station, recipe.kind, recipe.makes), ("hand", "material", "fibrous_cloth"))
        self.assertEqual(recipe.needs, {"shadowfern": 1, "emberroot": 1})
        self.assertEqual(resources.materialName("fibrous_cloth"), "Fibrous Cloth")

    def test_three_cloth_for_every_hide(self):
        self.assertEqual(PER_HIDE, 3)

    def test_crafting_it_turns_the_plants_into_cloth(self):
        game = newGame()
        game.player.addMaterial("shadowfern", 2)
        game.player.addMaterial("emberroot", 1)
        game.finishCraft(recipes.RECIPES_BY_ID["fibrous_cloth"])
        self.assertEqual(game.player.materials, {"shadowfern": 1, "fibrous_cloth": 1})


class StandInTests(unittest.TestCase):
    def test_have_counts_every_three_cloth_as_a_hide(self):
        player = PlayerClass()
        player.addMaterial("hide", 1)
        player.addMaterial("fibrous_cloth", 7)
        self.assertEqual(player.have("hide"), 1 + 7 // PER_HIDE)
        self.assertEqual(player.have("fibrous_cloth"), 7)

    def test_spending_hide_uses_real_hide_before_cloth(self):
        player = PlayerClass()
        player.addMaterial("hide", 1)
        player.addMaterial("fibrous_cloth", 7)
        player.spendMaterials({"hide": 2})
        self.assertEqual(player.materials, {"fibrous_cloth": 7 - PER_HIDE})

    def test_charcoal_still_stands_in_for_coal(self):
        player = PlayerClass()
        player.addMaterial("charcoal", 6)
        self.assertEqual(player.have("coal"), 2)
        player.spendMaterials({"coal": 1})
        self.assertEqual(player.materials, {"charcoal": 3})

    def test_cloth_does_not_count_for_anything_else(self):
        player = PlayerClass()
        player.addMaterial("fibrous_cloth", 9)
        self.assertEqual(player.have("coal"), 0)
        self.assertEqual(player.have("wood"), 0)


class CraftingWithClothTests(unittest.TestCase):
    def setUp(self):
        self.game = newGame()
        self.player = self.game.player
        self.player.stations.add("workbench")
        self.leatherPouch = recipes.RECIPES_BY_ID["leather_pouch"]  # needs 3 Hide

    def test_a_hide_recipe_can_be_made_with_cloth_alone(self):
        self.player.addMaterial("fibrous_cloth", 3 * PER_HIDE)
        self.assertTrue(self.player.hasMaterials(self.leatherPouch.needs))
        self.assertEqual(self.game.craftableCount(self.leatherPouch), 1)
        self.game.finishCraft(self.leatherPouch)
        self.assertEqual(self.player.pouchLimit, resources.BIG_POUCH_LIMIT)
        self.assertEqual(self.player.materials, {})

    def test_too_little_cloth_is_not_enough(self):
        self.player.addMaterial("fibrous_cloth", 3 * PER_HIDE - 1)
        self.assertFalse(self.player.hasMaterials(self.leatherPouch.needs))

    def test_the_crafting_window_says_cloth_can_stand_in(self):
        self.player.addMaterial("fibrous_cloth", 4)
        self.game.openWindow("crafting")
        self.game.craftTab = recipes.STATIONS.index("workbench")
        recipesShown = recipes.forStation("workbench")
        self.game.windowSel["crafting"] = [recipe.id for recipe in recipesShown].index("leather_pouch")
        detail = self.game.windowSpec("crafting")["detail"]
        hideRow = next(row for row in detail if row[1].startswith("Hide"))
        self.assertEqual(hideRow[1], f"Hide (or {PER_HIDE} Fibrous Cloth each)")
        self.assertEqual(hideRow[2], "1 / 3")


if __name__ == "__main__":
    unittest.main()
