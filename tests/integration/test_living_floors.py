"""Floors near you keep going while you're not on them (livingfloors.py), and floors you can never get back to are
dropped.

Integration tests; the rest are in tests/acceptance/test_living_floors.py."""
import random
import unittest
from unittest import mock
from cruel.entities import enemies
from cruel.world import livingfloors
from cruel.world import plants
from tests import support
from tests.helpers.living_floors import ENEMY, FLOOR, unitsOn


class ReachTests(unittest.TestCase):
    def setUp(self):
        random.seed(2)
        self.game = support.newGame(level=5)

    def test_two_floors_above_and_two_below_nearest_first(self):
        game = self.game
        game.changeLevel(2)
        self.assertEqual(livingfloors.floorsInReach(game), [1, 3, 0, 4])

    def test_only_floors_that_exist(self):
        game = self.game
        self.assertEqual(livingfloors.floorsInReach(game), [4, 3], "nothing below the deepest floor yet")
        game.changeLevel(0)
        self.assertEqual(livingfloors.floorsInReach(game), [1, 2])


class StaggeredGrowthTests(unittest.TestCase):
    def test_the_floors_near_you_grow_their_plants_on_different_turns(self):
        random.seed(2)
        game = support.newGame(level=4)
        game.changeLevel(2)
        grown = []  # (turn, the floor that grew)
        realStep = plants.step

        def step(grid, *args, **kwargs):
            grown.append((game.turnCount, game.level))
            return realStep(grid, *args, **kwargs)
        with mock.patch.object(plants, "step", step):
            for _ in range(plants.GROW_TURNS):
                game.enemyTurn()
        floors = sorted(level for _, level in grown)
        self.assertEqual(floors, [0, 1, 2, 3, 4], "each floor grew once")
        turns = [turn for turn, _ in grown]
        self.assertEqual(len(set(turns)), len(turns), "never two on the same turn")


class AwayTurnTests(unittest.TestCase):
    def setUp(self):
        random.seed(2)
        self.game = support.newGame(level=3)
        self.game.changeLevel(2)
        self.yourGrid = self.game.grid

    def test_units_on_a_floor_you_are_not_on_take_their_turns(self):
        game = self.game
        data = game.levelGrids[1]
        grid = data[0]
        spot = next(spot for spot, tile in grid.items() if tile[0] == FLOOR and all(grid[near][0] == FLOOR for near in game.neighbors(spot)))
        rat = enemies.DireRat()
        rat.lastPlayerPosition = spot + 3
        grid[spot] = [ENEMY, 0, rat]
        data[3].add(spot)
        for _ in range(4):
            game.enemyTurn()
        self.assertIn(rat, unitsOn(game.levelGrids[1]))
        self.assertNotEqual(unitsOn(game.levelGrids[1])[rat], spot, "it moved")
        self.assertIs(game.grid, self.yourGrid)

    def test_nothing_on_a_floor_you_are_not_on_ever_touches_you(self):
        game = self.game
        data = game.levelGrids[1]
        for near in game.neighbors(game.playerPositionFlat):  # Organizers after you, right where you'd be on the floor above
            organizer = enemies.SquareOrganizer()
            organizer.aggro, organizer.rest = "player", 0
            data[0][near] = [ENEMY, 1, organizer]
            data[3].add(near)
        before = game.player.damageTaken
        for _ in range(10):
            game.enemyTurn()
        self.assertEqual(game.player.damageTaken, before)

    def test_your_floor_is_just_as_it_was_after_the_others_take_their_turn(self):
        game = self.game
        level, theme, peaceful = game.level, game.theme, game.peaceful
        game.enemyTurn()
        self.assertIs(game.grid, self.yourGrid)
        self.assertEqual((game.level, game.theme, game.peaceful, game.simulatingAway), (level, theme, peaceful, False))

    def test_an_event_starting_on_another_floor_shows_you_nothing(self):
        game = self.game
        game.floorEvents[1] = {"id": "overgrowth", "turnsLeft": 1, "active": False}
        game.messageBools["eventMessage"] = False
        game.enemyTurn()
        self.assertTrue(game.floorEvents[1]["active"], "it started there")
        self.assertFalse(game.messageBools["eventMessage"])


class NewTrackTests(unittest.TestCase):
    def test_floors_above_a_new_track_are_dropped_and_never_simulated(self):
        random.seed(2)
        game = support.newGame(level=3)
        game.trackStarts.add(3)  # (floor 3 has no door back up)
        game.floorsAside[(1, 99)] = {"levelGrid": game.levelGrids[1], "dicts": {}, "sets": {}}
        game.player.stationPlaced["anvil"] = (1, 50)
        game.floorEvents[2] = {"id": "overgrowth", "turnsLeft": 5, "active": False}
        dropped = livingfloors.dropUnreachable(game)
        self.assertEqual(dropped, 3)
        self.assertEqual(game.levelGrids[:3], [None, None, None])
        self.assertNotIn((1, 99), game.floorsAside)
        self.assertNotIn("anvil", game.player.stationPlaced)
        self.assertNotIn(2, game.floorEvents)
        self.assertEqual(livingfloors.floorsInReach(game), [])

    def test_landing_on_a_new_track_drops_the_floors_above(self):
        random.seed(2)
        game = support.newGame(level=1)
        game.goToNewLevel(upDoor=False)
        self.assertEqual(game.levelGrids[:2], [None, None])


if __name__ == "__main__":
    unittest.main()
