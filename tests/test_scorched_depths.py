"""The Scorched Depths: breaking 10 gold walls on a Molten Vault floor opens a scorched door. Behind it is a side
track with the Molten Blade in a chest, molten floor that burns, and no way back up."""
import unittest

from tests import support
from cruel.core import gamemanager
from cruel.world import themes, wall

WALL, CHEST, DOWN_DOOR, UP_DOOR = 2, 3, 4, 6


def moltenVaultGame():
    """Floor 2 turned into an All Gold Molten Vault, with floor 3 already visited."""
    game = support.newGame(level=2)
    game.saveGame = lambda *args, **kwargs: None
    game.proportion = "All Gold"
    moltenVault = next(look for look in themes.THEMES["All Gold"] if look["name"] == "Molten Vault")
    game.setTheme(themes.Theme("All Gold", moltenVault))
    game.goToNewLevel()
    game.changeLevel(2)
    return game


def breakGoldWalls(game, howMany):
    for _ in range(howMany):
        spot = support.openTile(game)
        game.grid[spot] = [WALL, 1, wall.GoldWall()]
        game.breakWall(spot)


def goThroughTheScorchedDoor(game):
    breakGoldWalls(game, 10)
    support.placePlayer(game, game.scorchedDoors[game.level])
    game.focus = None
    game.enterScorched()


def moltenBladeChests(game):
    return [tile for tile in game.grid.values()
            if tile[0] == CHEST and tile[2] and tile[2][0].name == "Molten Blade"]


class ScorchedDepthsTest(unittest.TestCase):
    """Opening, entering and leaving the Scorched Depths."""

    def test_ten_gold_walls_open_the_scorched_door(self):
        game = moltenVaultGame()
        breakGoldWalls(game, 9)
        self.assertNotIn(2, game.scorchedDoors, "nine isn't enough")
        breakGoldWalls(game, 1)
        self.assertIn(2, game.scorchedDoors)
        self.assertEqual(game.grid[game.scorchedDoors[2]][0], gamemanager.SCORCHED_DOOR)
        self.assertEqual(game.grid[game.doorPositions[2]][0], DOWN_DOOR, "the normal door down stays")

    def test_entering_starts_a_new_track_with_the_molten_blade(self):
        game = moltenVaultGame()
        goThroughTheScorchedDoor(game)
        self.assertEqual(game.level, 3)
        self.assertEqual(game.proportion, gamemanager.SCORCHED)
        self.assertIn(game.theme.name, ("Cinder Halls", "Ashen Caldera"))
        self.assertIn(3, game.trackStarts)
        self.assertEqual(len(game.levelGrids), 3, "the floor 3 visited before is dropped")
        self.assertFalse(any(tile[0] == UP_DOOR for tile in game.grid.values()), "no door up")
        self.assertEqual(len(moltenBladeChests(game)), 1)

    def test_molten_floor_burns_unless_you_hold_the_molten_blade(self):
        game = moltenVaultGame()
        goThroughTheScorchedDoor(game)
        moltenBlade = moltenBladeChests(game)[0][2][0]
        moltenSpot = next(spot for spot in game.rooms["Molten"]
                          if game.grid[spot][0] == 0 and spot != game.playerPositionFlat)
        support.placePlayer(game, moltenSpot)

        damageBefore = game.player.damageTaken
        game.stepMolten()
        self.assertEqual(game.player.damageTaken, damageBefore + 1)

        game.player.equipment["Hands"] = moltenBlade
        damageBefore = game.player.damageTaken
        game.stepMolten()
        self.assertEqual(game.player.damageTaken, damageBefore, "the blade makes you immune")

    def test_the_door_down_leads_to_a_normal_floor_still_with_no_way_up(self):
        game = moltenVaultGame()
        goThroughTheScorchedDoor(game)
        support.placePlayer(game, game.doorPositions[3])
        game.onOpenDoor()
        self.assertEqual(game.level, 3, "the new track replaces floor 3")
        self.assertNotEqual(game.proportion, gamemanager.SCORCHED)
        self.assertIn(3, game.trackStarts)
        game.updateDoors()
        self.assertFalse(any(tile[0] == UP_DOOR for tile in game.grid.values()))

    def test_you_cant_go_above_the_start_of_the_track(self):
        game = moltenVaultGame()
        goThroughTheScorchedDoor(game)
        support.placePlayer(game, game.doorPositions[3])
        game.onOpenDoor()
        support.placePlayer(game, game.doorPositions[3])
        game.onOpenDoor()
        self.assertEqual(game.level, 4)

        game.onOpenDoor()  # you arrive on floor 4's door up
        self.assertEqual(game.level, 3)
        support.placePlayer(game, game.doorPositions[2])
        game.onOpenDoor()
        self.assertEqual(game.level, 3, "floor 3 is the top of this track")

    def test_a_scorched_floor_can_be_drawn(self):
        game = moltenVaultGame()
        goThroughTheScorchedDoor(game)
        game.change = True
        game.setPositionsVisible()
        game.draw()


if __name__ == "__main__":
    unittest.main()
