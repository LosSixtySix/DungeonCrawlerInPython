"""Ropes (ropes.py): made by hand from Fibrous Cloth, tied to a hole by facing it and pressing interact. A roped hole
is a two-way path: Enter on it climbs down (no fall damage) onto the rope's end, and Enter on the rope's end climbs
back up. Ropes are only tied from above.

Integration tests."""
import unittest

import pygame

from cruel.core import gamemanager
from cruel.graphics import sprites
from cruel.inventory import recipes
from cruel.world import expansion, ropes
from tests.helpers.gamemanager import FLOOR, LEFT, keyDown, standInOpenFloor
from tests.support import newGame, placePlayer


def interact(game):
    keyDown(game, game.settings.hotkeys["interact"])


def enter(game):
    keyDown(game, pygame.K_RETURN)


def tileColors(game, spot):
    """Every color drawn on the screen over the tile at spot, after drawing a frame."""
    for message in game.messageBools:  # (the big "Floor N" message darkens the screen at first)
        game.messageBools[message] = False
    game.painter.fade = 0
    game.setPositionsVisible()
    game.draw()
    tile = game.painter.tileOnScreen(spot)
    return {tuple(game.win.get_at((pixelX, pixelY)))[:3] for pixelX in range(tile.left, tile.right)
            for pixelY in range(tile.top, tile.bottom)}


class RopeRecipeTests(unittest.TestCase):
    def test_rope_is_made_by_hand_from_three_fibrous_cloth(self):
        recipe = recipes.RECIPES_BY_ID["rope"]
        self.assertEqual((recipe.station, recipe.kind, recipe.makes), ("hand", "material", "rope"))
        self.assertEqual(recipe.needs, {"fibrous_cloth": 3})

    def test_crafting_it_turns_cloth_into_rope(self):
        game = newGame()
        game.player.addMaterial("fibrous_cloth", 4)
        game.finishCraft(recipes.RECIPES_BY_ID["rope"])
        self.assertEqual(game.player.materials, {"fibrous_cloth": 1, "rope": 1})


class RopeTestCase(unittest.TestCase):
    """You stand on cleared floor on floor 0 facing a hole to your left."""

    def setUp(self):
        self.game = newGame()
        self.playerSpot = standInOpenFloor(self.game, facing=LEFT)
        self.holeSpot = self.game.PlayerLookPosition
        self.game.grid[self.holeSpot] = [expansion.HOLE, 1]

    def tieRope(self):
        self.game.player.addMaterial(ropes.ROPE, 1)
        interact(self.game)

    def standOnRopedHole(self):
        self.tieRope()
        self.game.enemyMove = False
        placePlayer(self.game, self.holeSpot)


class TyingTests(RopeTestCase):
    def test_without_a_rope_you_are_told_you_could_use_one(self):
        interact(self.game)
        self.assertEqual(self.game.grid[self.holeSpot][0], expansion.HOLE)
        self.assertIn(ropes.NO_ROPE_MESSAGE, [popup[0] for popup in self.game.popups])
        self.assertFalse(self.game.enemyMove, "no rope: no turn spent")

    def test_with_a_rope_interact_ties_it_to_the_hole(self):
        self.tieRope()
        self.assertEqual(self.game.grid[self.holeSpot][0], ropes.ROPED_HOLE)
        self.assertEqual(self.game.player.materials.get(ropes.ROPE, 0), 0, "the rope is used up")
        self.assertTrue(self.game.enemyMove)

    def test_no_rope_can_be_tied_on_the_scorched_depths(self):
        self.game.proportion = gamemanager.SCORCHED
        self.tieRope()
        self.assertEqual(self.game.grid[self.holeSpot][0], expansion.HOLE)
        self.assertEqual(self.game.player.materials[ropes.ROPE], 1, "the rope is kept")

    def test_a_bomb_leaves_a_roped_hole_alone(self):
        self.tieRope()
        self.game.collapseFloor(self.holeSpot, 1)
        self.assertEqual(self.game.grid[self.holeSpot][0], ropes.ROPED_HOLE)


class ClimbingTests(RopeTestCase):
    def test_standing_on_a_roped_hole_you_do_not_fall(self):
        self.standOnRopedHole()
        self.assertNotEqual(self.game.currentLocation[0], expansion.HOLE)
        self.assertEqual(self.game.level, 0)

    def test_enter_climbs_down_without_fall_damage_onto_the_ropes_end(self):
        self.standOnRopedHole()
        enter(self.game)
        self.assertEqual(self.game.level, 1)
        self.assertEqual(self.game.player.damageTaken, 0)
        self.assertEqual(self.game.currentLocation[0], ropes.HANGING_ROPE)
        self.assertEqual(self.game.currentLocation[2].hole, self.holeSpot)

    def test_enter_on_the_ropes_end_climbs_back_up_to_the_roped_hole(self):
        self.standOnRopedHole()
        enter(self.game)
        enter(self.game)
        self.assertEqual(self.game.level, 0)
        self.assertEqual(self.game.playerPositionFlat, self.holeSpot)
        self.assertEqual(self.game.currentLocation[0], ropes.ROPED_HOLE)

    def test_climbing_down_again_lands_on_the_same_ropes_end(self):
        self.standOnRopedHole()
        enter(self.game)
        ropeEnd = self.game.playerPositionFlat
        enter(self.game)
        enter(self.game)
        self.assertEqual(self.game.level, 1)
        self.assertEqual(self.game.playerPositionFlat, ropeEnd)
        ropeEnds = [spot for spot, tile in self.game.grid.items() if tile[0] == ropes.HANGING_ROPE]
        self.assertEqual(ropeEnds, [ropeEnd], "no second rope's end was laid")
        self.assertEqual(self.game.currentLocation[0], ropes.HANGING_ROPE)

    def test_a_ropes_end_with_no_rope_above_goes_nowhere(self):
        self.standOnRopedHole()
        enter(self.game)
        self.game.levelGrids[0][0][self.holeSpot] = [FLOOR, 1]  # (the hole above is gone)
        enter(self.game)
        self.assertEqual(self.game.level, 1)


class FromBelowTests(RopeTestCase):
    def test_a_rope_cannot_be_tied_from_below(self):
        self.standOnRopedHole()
        enter(self.game)
        self.game.player.addMaterial(ropes.ROPE, 1)
        for spot in self.game.neighbors(self.game.playerPositionFlat):  # nothing down here to tie a rope to
            self.game.PlayerLookPosition = spot
            interact(self.game)
        self.assertEqual(self.game.player.materials[ropes.ROPE], 1)


class DrawingTests(RopeTestCase):
    def test_a_roped_hole_shows_its_rope(self):
        self.tieRope()
        ropeColors = {sprites.ROPE_COLORS[letter] for letter in "rRdnN"}
        self.assertTrue(tileColors(self.game, self.holeSpot) & ropeColors)

    def test_the_ropes_end_shows_its_rope(self):
        self.standOnRopedHole()
        enter(self.game)
        ropeEnd = self.game.playerPositionFlat
        placePlayer(self.game, self.game.neighbors(ropeEnd)[0])
        ropeColors = {sprites.ROPE_COLORS[letter] for letter in "rRd"}
        self.assertTrue(tileColors(self.game, ropeEnd) & ropeColors)


if __name__ == "__main__":
    unittest.main()
