"""The Potion Of Darkvision: Dew brewed into sight that reaches far in the dark, by no light (enemies aren't drawn to
it), and still stops at walls."""
import unittest

from cruel.entities.playerClass import PlayerClass
from cruel.graphics import renderer
from cruel.inventory import items
from cruel.inventory import recipes
from cruel.inventory import relics
from cruel.world import wall
from tests import support
from tests.test_expansion import blankFloor, middleOf

WALL = 2


def recipe(recipeId):
    return next(recipe for recipe in recipes.RECIPES if recipe.id == recipeId)


def darkvisionPotion():
    return recipe("darkvision").makeItem(0, 0)


def drink(player):
    player.inventory.append(darkvisionPotion())
    player.useConsumable(len(player.inventory) - 1)


class PotionTests(unittest.TestCase):
    def test_it_is_brewed_from_dew_at_the_alchemists_set(self):
        brew = recipe("darkvision")
        self.assertEqual(brew.station, "alchemist")
        self.assertIn("dew", brew.needs)
        potion = darkvisionPotion()
        self.assertEqual(potion.name, "Potion Of Darkvision")
        self.assertEqual((potion.effect, potion.bonus), ("Darkvision", recipes.DARKVISION_TURNS))

    def test_drinking_it_gives_darkvision_for_its_turns_then_it_wears_off(self):
        player = PlayerClass()
        drink(player)
        self.assertTrue(player.hasEffect("darkvision"))
        self.assertEqual(player.potionTurns(), [("darkvision", recipes.DARKVISION_TURNS)])
        self.assertNotIn("darkvision", player.gearEffects())
        for _ in range(recipes.DARKVISION_TURNS - 1):
            self.assertEqual(player.stepBuffs(), [])
        self.assertEqual(player.stepBuffs(), ["darkvision"])
        self.assertFalse(player.hasEffect("darkvision"))

    def test_another_one_tops_it_up_and_a_meal_does_not_wash_it_out(self):
        player = PlayerClass()
        drink(player)
        for _ in range(10):
            player.stepBuffs()
        drink(player)
        self.assertEqual(player.potionTurns(), [("darkvision", recipes.DARKVISION_TURNS)])
        meal = next(cooked for cooked in recipes.RECIPES if cooked.kind == "potion" and cooked.station == "cooking_pot").makeItem(0, 0)
        player.eat(meal)
        self.assertTrue(player.hasEffect("darkvision"))


class SightTests(unittest.TestCase):
    def setUp(self):
        self.game = support.newGame()
        blankFloor(self.game)
        self.middle = middleOf(self.game)
        support.placePlayer(self.game, self.middle)
        self.far = self.middle + self.game.player.getVisionRange() + 3  # past your light, in reach of Darkvision

    def test_without_it_you_see_only_as_far_as_your_light(self):
        self.game.setPositionsVisible()
        self.assertNotEqual(self.game.grid[self.far][1], 1)
        self.assertEqual(self.game.darkSight, set())

    def test_with_it_you_see_far_past_your_light(self):
        self.game.player.drinkEffect("darkvision", 50)
        self.game.setPositionsVisible()
        self.assertEqual(self.game.grid[self.far][1], 1)
        self.assertIn(self.far, self.game.darkSight)
        self.assertNotIn(self.far, self.game.ownSight, "it isn't lit")
        self.assertNotIn(self.middle + relics.DARKVISION_RANGE + 2, self.game.darkSight, "only so far")

    def test_walls_still_block_it(self):
        self.game.grid[self.middle + 2] = [WALL, 0, wall.StoneWall()]
        self.game.player.drinkEffect("darkvision", 50)
        self.game.setPositionsVisible()
        self.assertNotEqual(self.game.grid[self.far][1], 1)

    def test_enemies_are_not_drawn_to_it_even_with_a_torch_in_hand(self):
        game = self.game
        game.player.equipment["Right Hand"] = items.equipment("Light", "Torch", "Hands", 2)
        game.player.drinkEffect("darkvision", 50)
        game.setPositionsVisible()
        self.assertTrue(game.torchLight, "the torch's own light is still seen")
        self.assertFalse(game.darkSight & game.torchLight)
        self.assertIsNone(game.torchSpotSeen(set(game.darkSight)))

    def test_from_inside_smoke_it_shows_nothing_more(self):
        game = self.game
        game.smoke[self.middle] = 5
        game.player.drinkEffect("darkvision", 50)
        game.setPositionsVisible()
        self.assertEqual(game.darkSight, set())

    def test_it_is_drawn_dim_and_unlit(self):
        painter = renderer.renderer.__new__(renderer.renderer)
        painter.rowLength = self.game.rowLength
        painter.fireLight, painter.glowLight, painter.darkSight = {}, {}, {self.far}
        lighting = painter.tileLighting(self.far, self.far % painter.rowLength, self.far // painter.rowLength,
                                        self.middle, 4, (0, 0, 1))
        self.assertEqual(lighting, (1, 0, 0, renderer.DARKVISION_DARK))


if __name__ == "__main__":
    unittest.main()
