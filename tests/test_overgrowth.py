"""During the Overgrowth event plants can sprout on the player's tile. They hurt, and a plant that blocks the way
pushes the player to an empty tile beside them, or traps them if there's none (Ctrl + interact breaks free)."""
import unittest

import pygame

from tests import support
from cruel.core import gamemanager
from cruel.world import plants

FLOOR, PLAYER, PLANT = 0, 1, 8


def overgrowthGame():
    """Floor 1 during the Overgrowth event, with bare floor all around the player and no enemies."""
    game = support.newGame(level=1)
    game.floorEvents[game.level] = {"id": "overgrowth", "turnsLeft": 0, "active": True}
    playerSpot = game.playerPositionFlat
    game.currentLocation = [FLOOR, 1]
    for besidePlayer in game.neighbors(playerSpot):
        game.grid[besidePlayer] = [FLOOR, 1]
    game.EnemyPositions.clear()
    game.player.damageTaken = 0
    game.grid[playerSpot] = [PLAYER, 1]  # the game loop marks the player's tile every frame
    return game


def growPlantOnPlayer(game, plantKind):
    """Run a real enemy turn whose plant growth step sprouts `plantKind` on the player's tile.
    Returns the tile type the growth step saw where the player stands."""
    realGrowthStep = plants.step
    playerSpot = game.playerPositionFlat
    seen = {}

    def sproutOnThePlayer(grid, *args, **kwargs):
        seen["tileUnderPlayer"] = grid[playerSpot][0]
        grid[playerSpot] = [PLANT, grid[playerSpot][1], plants.Plant.grown(plantKind)]
        return True

    plants.step = sproutOnThePlayer
    game.turnCount = -1  # the next enemy turn is turn 0, which is a growth turn
    try:
        game.enemyTurn()
    finally:
        plants.step = realGrowthStep
    return seen.get("tileUnderPlayer")


class OvergrowthTest(unittest.TestCase):
    """Plants growing onto the player during Overgrowth."""

    def test_the_growth_step_sees_bare_floor_under_the_player(self):
        game = overgrowthGame()
        self.assertEqual(growPlantOnPlayer(game, "hearthmoss"), FLOOR)

    def test_a_walkable_plant_hurts_you_and_grows_around_you(self):
        game = overgrowthGame()
        playerSpot = game.playerPositionFlat
        growPlantOnPlayer(game, "hearthmoss")
        self.assertGreaterEqual(game.player.damageTaken, gamemanager.OVERGROWTH_DAMAGE)
        self.assertEqual(game.playerPositionFlat, playerSpot, "you aren't moved")
        self.assertEqual(game.currentLocation[0], PLANT, "you're standing in the plant")
        self.assertIsNone(game.stuckIn(), "a walkable plant doesn't trap you")

    def test_a_blocking_plant_pushes_you_to_an_empty_tile_beside_you(self):
        game = overgrowthGame()
        oldSpot = game.playerPositionFlat
        growPlantOnPlayer(game, "bloodcap")
        self.assertIn(game.playerPositionFlat, game.neighbors(oldSpot))
        plantTile = game.grid[oldSpot]
        self.assertEqual(plantTile[0], PLANT)
        self.assertEqual(plantTile[2].kind, "bloodcap")
        self.assertEqual(game.currentLocation[0], FLOOR, "you land on bare floor")

    def test_walled_in_by_plants_you_are_stuck_until_ctrl_interact(self):
        game = overgrowthGame()
        playerSpot = game.playerPositionFlat
        for besidePlayer in game.neighbors(playerSpot):
            game.grid[besidePlayer] = [PLANT, 1, plants.Plant.grown("emberroot")]
        growPlantOnPlayer(game, "emberroot")
        self.assertEqual(game.playerPositionFlat, playerSpot)
        self.assertIsNotNone(game.stuckIn())
        game.updateDoors()
        self.assertIn("(stuck)", game.currentPosition, "the tile description says you're stuck")

        for besidePlayer in game.neighbors(playerSpot):
            game.grid[besidePlayer] = [FLOOR, 1]
        game.movePlayer(game.neighbors(playerSpot)[0])
        self.assertEqual(game.playerPositionFlat, playerSpot, "you can't walk out, even with room beside you")

        ctrlInteract = pygame.event.Event(pygame.KEYDOWN, key=game.settings.hotkeys["interact"],
                                          mod=pygame.KMOD_LCTRL, unicode="e", scancode=0)
        game.onKeyDown(ctrlInteract)
        self.assertIsNone(game.stuckIn(), "breaking the plant frees you")
        self.assertEqual(game.currentLocation[0], FLOOR)

        game.enemyMove = False
        game.movePlayer(game.neighbors(playerSpot)[0])
        self.assertNotEqual(game.playerPositionFlat, playerSpot, "you can walk again")

    def test_without_the_event_plants_never_grow_on_you(self):
        game = overgrowthGame()
        game.floorEvents.pop(game.level)
        self.assertEqual(growPlantOnPlayer(game, "hearthmoss"), PLAYER, "your tile isn't offered to the plants")
        self.assertEqual(game.player.damageTaken, 0)


if __name__ == "__main__":
    unittest.main()
