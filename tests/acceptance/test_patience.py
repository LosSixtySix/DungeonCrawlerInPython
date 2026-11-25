"""The Patience trigger: stand still on floor 0's center tile for 5 minutes and the floor gives way, dropping you
onto an ore floor (always a Motherlode) that has no way back up."""
import collections
import unittest

from tests import support
from cruel.world import wall

FIVE_MINUTES = 300


def waitOnTheCenterTile(game, seconds, startMs=0):
    """Let `seconds` of game time pass, one frame per second, without touching anything."""
    for second in range(seconds + 1):
        game.stepPatience(startMs + second * 1000)


class PatienceTest(unittest.TestCase):
    """Standing still on floor 0's center tile."""

    def test_you_start_on_the_center_tile_and_the_door_down_is_elsewhere(self):
        game = support.newGame()
        self.assertEqual(game.playerPositionFlat, game.centerTile())
        self.assertNotEqual(game.doorPositions[0], game.centerTile())

    def test_five_minutes_drops_you_onto_a_motherlode_with_no_way_up(self):
        game = support.newGame()
        waitOnTheCenterTile(game, FIVE_MINUTES - 1)
        self.assertEqual(game.level, 0, "4:59 isn't long enough")

        game.stepPatience(FIVE_MINUTES * 1000 + 5)
        self.assertEqual(game.level, 1)
        self.assertIn(game.proportion, wall.ORE_FLOORS)
        self.assertIn(1, game.trackStarts, "the ore floor starts a new track")
        self.assertIn(1, game.motherlodes, "it's always a Motherlode")
        upDoors = [tile for tile in game.grid.values() if tile[0] == 6]
        self.assertEqual(upDoors, [], "there is no way back up")
        self.assertGreater(game.player.damageTaken, 0, "the fall hurts")

    def test_the_floor_below_the_ore_floor_is_a_normal_floor(self):
        game = support.newGame()
        waitOnTheCenterTile(game, FIVE_MINUTES + 1)
        game.grid[game.playerPositionFlat] = game.currentLocation
        game.goToNewLevel()
        self.assertEqual(game.level, 2)
        self.assertNotIn(2, game.trackStarts)
        self.assertTrue(any(tile[0] == 6 for tile in game.grid.values()), "floor 2 has a door up")

    def test_clicking_resets_the_clock_and_pausing_only_stops_it(self):
        game = support.newGame()
        waitOnTheCenterTile(game, 200)
        self.assertGreaterEqual(game.patienceMs, 199_000)

        leftClick = type("Click", (), {"button": 1, "pos": (0, 0)})()
        game.onMouseDown(leftClick)
        self.assertEqual(game.patienceMs, 0, "a click resets the clock")

        waitOnTheCenterTile(game, 100, startMs=500_000)
        game.pausePage = "main"
        waitOnTheCenterTile(game, 400, startMs=700_000)
        self.assertEqual(game.level, 0, "time spent paused doesn't count")
        self.assertTrue(90_000 <= game.patienceMs <= 101_000, game.patienceMs)

    def test_stepping_off_the_center_tile_resets_the_clock(self):
        game = support.newGame()
        waitOnTheCenterTile(game, 100)
        game.playerPositionFlat = game.centerTile() + 1
        game.stepPatience(2_000_000)
        self.assertEqual(game.patienceMs, 0)

    def test_deeper_floors_you_already_visited_are_dropped(self):
        game = support.newGame(level=2)
        game.changeLevel(0)
        support.placePlayer(game, game.centerTile())
        waitOnTheCenterTile(game, FIVE_MINUTES + 1)
        self.assertEqual(game.level, 1)
        self.assertIn(game.proportion, wall.ORE_FLOORS)
        self.assertEqual(len(game.doorPositions), 2, "floors 0 and 1 only")
        self.assertEqual(len(game.levelGrids), 1, "only floor 0 is stored")

    def test_it_only_works_on_the_first_floor(self):
        game = support.newGame(level=1)
        game.playerPositionFlat = game.centerTile()
        waitOnTheCenterTile(game, 400)
        self.assertEqual(game.level, 1)
        self.assertEqual(game.patienceMs, 0)

    def test_any_ore_floor_can_be_picked_and_every_one_is_a_motherlode(self):
        game = support.newGame()
        picks = [game.randomOreFloor() for _ in range(20_000)]
        oreFloorsPicked = collections.Counter(oreFloor for oreFloor, isMotherlode in picks)
        self.assertEqual(set(oreFloorsPicked), set(wall.ORE_FLOORS), "the depth limit is ignored")
        self.assertTrue(all(isMotherlode for oreFloor, isMotherlode in picks))

    def test_the_patience_console_command_drops_you_straight_away(self):
        game = support.newGame()
        game.console.cmdPatience([])
        self.assertEqual(game.level, 1)


if __name__ == "__main__":
    unittest.main()
