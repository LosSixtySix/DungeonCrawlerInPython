"""Floors near you keep going while you're not on them (livingfloors.py), and floors you can never get back to are
dropped."""
import random
import unittest
from unittest import mock

from cruel.entities import enemies
from cruel.world import livingfloors
from cruel.world import metropolis
from cruel.world import mineshafts
from cruel.world import occupancy
from cruel.world import plants
from tests import support
from tests.test_mineshafts import cityGame, climbDown, shaftSpot

FLOOR, WALL, ENEMY = 0, 2, 5
BLOOD_FIELD = livingfloors.FLOOR_FIELDS.index("blood")


def unitsOn(data):
    """The units on a saved floor: {unit: spot}."""
    grid = data[0]
    return {tile[2]: spot for spot, tile in grid.items() if tile[0] == ENEMY and len(tile) > 2}


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
        game = self.game
        landing = self.awayFloorSpot()
        with mock.patch.object(game.sound, "playExplosion") as playExplosion:
            with livingfloors.awayFloor(game, 1):
                game.land({"effect": "Explosive", "power": 1, "path": [landing], "landing": landing, "turns": 0, "flight": 0})
        self.assertEqual(game.explosions, [])
        playExplosion.assert_not_called()

    def test_a_floor_you_are_not_on_changing_does_not_redraw_yours(self):
        game = self.game
        data = game.levelGrids[1]
        spot = self.awayFloorSpot()
        rat = enemies.DireRat()
        rat.lastPlayerPosition = spot + 3
        data[0][spot] = [ENEMY, 0, rat]
        data[3].add(spot)
        game.change = False
        livingfloors.simulate(game)
        self.assertNotEqual(unitsOn(game.levelGrids[1]).get(rat), spot, "it took its turn")
        self.assertFalse(game.change)


class CityTests(unittest.TestCase):
    def test_a_city_brings_its_mine_and_farm_along_made_even_if_you_have_never_been_down(self):
        random.seed(5)
        game = cityGame()
        game.enemyTurn()
        level = game.level
        keys = [key for key in livingfloors.floorsInReach(game) if isinstance(key, tuple)]
        self.assertEqual(sorted(keys), sorted((level, shaftSpot(game, kind)) for kind in metropolis.WORKS))
        self.assertTrue(all(key in game.floorsAside for key in keys))

    def test_going_down_finds_the_floor_that_has_been_going_on_without_you(self):
        random.seed(5)
        game = cityGame()
        game.enemyTurn()
        madeBefore = game.floorsAside[(game.level, shaftSpot(game, "farm"))]["levelGrid"][0]
        climbDown(game, "farm")
        self.assertIs(game.grid, madeBefore)

    def test_on_a_works_floor_its_city_and_the_other_works_floor_keep_going(self):
        random.seed(5)
        game = cityGame()
        level = game.level
        mineShaft = shaftSpot(game, "mine")
        climbDown(game, "farm")
        keys = livingfloors.floorsInReach(game)
        self.assertIn(level, keys, "the city")
        self.assertIn((level, mineShaft), keys, "the mine")
        self.assertNotIn(mineshafts.floorKey(game), keys, "not where you are")
        game.enemyTurn()  # (and they can take a turn without trouble)
        game.onEnter()  # back up: the city is there as it was
        self.assertEqual(game.proportion, metropolis.METROPOLIS)


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
