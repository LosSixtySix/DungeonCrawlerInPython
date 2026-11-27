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

WALL = 2
BLOOD_FIELD = livingfloors.FLOOR_FIELDS.index("blood")


class ReachTests(unittest.TestCase):
    def setUp(self):
        random.seed(2)
        self.game = support.newGame(level=5)

    def test_two_floors_above_and_two_below_nearest_first(self):
        self.game.changeLevel(2)
        self.assertEqual(livingfloors.floorsInReach(self.game), [1, 3, 0, 4])

    def test_only_floors_that_exist(self):
        self.assertEqual(livingfloors.floorsInReach(self.game), [4, 3], "nothing below the deepest floor yet")
        self.game.changeLevel(0)
        self.assertEqual(livingfloors.floorsInReach(self.game), [1, 2])


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
        data = self.game.levelGrids[1]
        grid = data[0]
        spot = next(spot for spot, tile in grid.items()
                    if tile[0] == FLOOR and all(grid[near][0] == FLOOR for near in self.game.neighbors(spot)))
        rat = enemies.DireRat()
        rat.lastPlayerPosition = spot + 3
        grid[spot] = [ENEMY, 0, rat]
        data[3].add(spot)
        for _ in range(4):
            self.game.enemyTurn()
        self.assertIn(rat, unitsOn(self.game.levelGrids[1]))
        self.assertNotEqual(unitsOn(self.game.levelGrids[1])[rat], spot, "it moved")
        self.assertIs(self.game.grid, self.yourGrid)

    def test_nothing_on_a_floor_you_are_not_on_ever_touches_you(self):
        data = self.game.levelGrids[1]
        for near in self.game.neighbors(self.game.playerPositionFlat):  # Organizers after you, right where you'd be on the floor above
            organizer = enemies.SquareOrganizer()
            organizer.aggro, organizer.rest = "player", 0
            data[0][near] = [ENEMY, 1, organizer]
            data[3].add(near)
        before = self.game.player.damageTaken
        for _ in range(10):
            self.game.enemyTurn()
        self.assertEqual(self.game.player.damageTaken, before)

    def test_your_floor_is_just_as_it_was_after_the_others_take_their_turn(self):
        level, theme, peaceful = self.game.level, self.game.theme, self.game.peaceful
        self.game.enemyTurn()
        self.assertIs(self.game.grid, self.yourGrid)
        self.assertEqual((self.game.level, self.game.theme, self.game.peaceful, self.game.simulatingAway), (level, theme, peaceful, False))

    def test_an_event_starting_on_another_floor_shows_you_nothing(self):
        self.game.floorEvents[1] = {"id": "overgrowth", "turnsLeft": 1, "active": False}
        self.game.messageBools["eventMessage"] = False
        self.game.enemyTurn()
        self.assertTrue(self.game.floorEvents[1]["active"], "it started there")
        self.assertFalse(self.game.messageBools["eventMessage"])


class NothingShownFromAwayTests(unittest.TestCase):
    """A floor you're not on keeps going but is never drawn or heard: nothing that happens there plays on yours."""

    def setUp(self):
        random.seed(2)
        self.game = support.newGame(level=3)
        self.game.changeLevel(2)
        self.awayGrid = self.game.levelGrids[1][0]

    def awayFloorSpot(self):
        """Open floor on the floor above, far from where you stand, with open floor all round it."""
        game, grid = self.game, self.awayGrid
        return next(spot for spot, tile in grid.items() if tile[0] == FLOOR
                    and all(grid[near][0] == FLOOR for near in game.neighbors(spot))
                    and abs(spot % game.rowLength - game.playerPositionFlat % game.rowLength) > 8)

    def test_a_hit_there_leaves_its_blood_there_but_no_spurt_or_flecks_play_here(self):
        game, grid = self.game, self.awayGrid
        wallSpot = next(spot for spot, tile in grid.items() if tile[0] == WALL and len(tile) > 2
                        and any(grid[near][0] == FLOOR for near in game.neighbors(spot)))
        hitFrom = next(near for near in game.neighbors(wallSpot) if grid[near][0] == FLOOR)
        with mock.patch.object(game.painter, "wallColor") as wallColor,                 mock.patch.object(game.painter, "roomWallColor") as roomWallColor:
            with livingfloors.awayFloor(game, 1):
                game.bleed(hitFrom)
                game.chip(wallSpot, hitFrom)
        self.assertEqual((game.spurts, game.flecks), ([], []))
        self.assertGreater(game.levelGrids[1][BLOOD_FIELD].get(hitFrom, 0), 0, "its blood stays on its floor")
        wallColor.assert_not_called()  # (nor is the work done to show them)
        roomWallColor.assert_not_called()
        game.bleed(game.playerPositionFlat)
        self.assertEqual(len(game.spurts), 1, "on your own floor a hit does spurt")

    def test_an_explosion_there_is_neither_seen_nor_heard_here(self):
        landing = self.awayFloorSpot()
        with mock.patch.object(self.game.sound, "playExplosion") as playExplosion:
            with livingfloors.awayFloor(self.game, 1):
                self.game.land({"effect": "Explosive", "power": 1, "path": [landing], "landing": landing, "turns": 0, "flight": 0})
        self.assertEqual(self.game.explosions, [])
        playExplosion.assert_not_called()

    def test_a_floor_you_are_not_on_changing_does_not_redraw_yours(self):
        data = self.game.levelGrids[1]
        spot = self.awayFloorSpot()
        rat = enemies.DireRat()
        rat.lastPlayerPosition = spot + 3
        data[0][spot] = [ENEMY, 0, rat]
        data[3].add(spot)
        self.game.change = False
        livingfloors.simulate(self.game)
        self.assertNotEqual(unitsOn(self.game.levelGrids[1]).get(rat), spot, "it took its turn")
        self.assertFalse(self.game.change)


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
