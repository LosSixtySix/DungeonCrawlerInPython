"""The Dweller Queen's court in a running game (queen.py): her chamber and court in every city, her turn, Royal
Guards on their leash, and guards pupating into Royal Guards.

Integration tests; the rest are in tests/unit/test_queen.py, tests/acceptance/test_queen.py."""
import random
import unittest
from unittest import mock

from cruel.entities import enemies
from cruel.world import dwellers
from cruel.world import metropolis
from cruel.world import occupancy
from cruel.world import queen
from tests.helpers.metropolis import cityGame
from tests.integration.test_city_hostility import CityTest
from tests.support import newGame

ENEMY = 5


class CourtPlacementTests(unittest.TestCase):
    def test_every_city_has_one_queen_in_the_middle_of_her_chamber_with_four_royal_guards(self):
        game = newGame()
        rowLength, rowCount = game.rowLength, game.numberOfSpots // game.rowLength
        for seed in range(12):
            random.seed(seed)
            city = metropolis.buildCity(rowLength, rowCount, rowLength * (rowCount // 2) + rowLength // 2,
                                        metropolis.BUILDING_STYLES[seed % len(metropolis.BUILDING_STYLES)])
            dwellerQueen = city.queen
            self.assertIsNotNone(dwellerQueen, f"seed {seed}")
            body = metropolis.bodyOf(rowLength, dwellerQueen.anchor)
            self.assertTrue(set(body) <= city.chamber.inside)
            self.assertTrue(all(city.grid[tile] == [ENEMY, 0, dwellerQueen] for tile in body))
            self.assertEqual([spot for spot, unit in city.dwellers.items() if unit is dwellerQueen], [dwellerQueen.anchor],
                             "only her anchor is listed")
            royals = [(spot, unit) for spot, unit in city.dwellers.items() if queen.isRoyal(unit)]
            self.assertEqual(len(royals), metropolis.ROYAL_GUARDS)
            for spot, royal in royals:
                self.assertEqual(royal.home, spot)
                self.assertIn(spot, city.chamber.inside)
                self.assertEqual(metropolis.bodyDistance(rowLength, dwellerQueen.anchor, 2, spot), metropolis.ROYAL_POST_REACH)
            self.assertEqual(city.chamber.kind, "chamber")
            self.assertEqual(len(city.chamber.doors), 2, "two doors, like every Dweller building")


class QueenTest(CityTest):
    """An open city floor with the Queen on it, her body at (30, 20) to (31, 21)."""

    def setUp(self):
        super().setUp()
        self.queen = enemies.DwellerQueen()
        self.anchor = self.spot(30, 20)
        self.queen.home = self.anchor
        self.game.putGiant(self.game.grid, self.anchor, self.queen)
        for tile in self.game.footprint(self.anchor, 2):
            self.game.grid[tile][1] = 1
        self.game.EnemyPositions.add(self.anchor)
        self.game.enemyDodge = lambda target, damage, position: damage  # (every hit lands)

    def addGoblin(self, column, row):
        goblin = enemies.Goblin()
        position = self.spot(column, row)
        self.game.grid[position] = [ENEMY, 1, goblin]
        self.game.EnemyPositions.add(position)
        return goblin


class QueenTurnTests(QueenTest):
    def test_she_never_moves(self):
        self.standAt(40, 20)
        dwellers.turnHostile(self.game, self.queen, self.game.playerPositionFlat)
        self.runTurns(10)
        self.assertEqual(queen.courtOf(self.game), (self.anchor, self.queen))
        self.assertTrue(all(self.game.grid[tile][2] is self.queen for tile in self.game.footprint(self.anchor, 2)))

    def test_she_hits_an_enemy_of_the_city_within_her_reach(self):
        goblin = self.addGoblin(33, 20)  # two tiles from her body
        goblin.speed = 0  # (it stays put)
        before = goblin.hp
        queen.queenTurn(self.game, self.anchor, self.queen)
        self.assertLess(goblin.hp, before)

    def test_she_leaves_one_beyond_her_reach(self):
        goblin = self.addGoblin(34, 20)  # three tiles away
        before = goblin.hp
        queen.queenTurn(self.game, self.anchor, self.queen)
        self.assertEqual(goblin.hp, before)

    def test_calm_she_never_hits_you_hostile_she_does(self):
        self.standAt(32, 21)
        self.game.player.damageTaken = 0
        queen.queenTurn(self.game, self.anchor, self.queen)
        self.assertEqual(self.game.player.damageTaken, 0)
        dwellers.turnHostile(self.game, self.queen, self.game.playerPositionFlat)
        queen.queenTurn(self.game, self.anchor, self.queen)
        self.assertGreater(self.game.player.damageTaken, 0)

    def test_hurting_her_turns_her_hostile(self):
        self.standAt(29, 20)
        self.game.player.DealDamage = lambda: 3
        self.game.onInteract()
        self.assertTrue(self.queen.hostile)
        self.assertLess(self.queen.hp, self.queen.maxHp)

    def test_killing_her_clears_her_whole_body(self):
        self.game.killEnemy(self.spot(31, 21), killer=None)
        self.assertIsNone(queen.courtOf(self.game))
        self.assertFalse([tile for tile in metropolis.bodyOf(self.rowLength, self.anchor)
                          if self.game.grid[tile][0] == ENEMY or self.queen in self.game.grid[tile]])

    def test_a_dweller_sharing_one_of_her_spaces_never_lists_her_twice(self):
        citizen = self.addDweller(enemies.DwellerCitizen, 32, 21)
        citizen.goal = citizen.home = self.spot(28, 20)
        with mock.patch.object(dwellers, "IDLE_CHANCE", 0):
            for _ in range(15):
                self.game.enemyTurn()
                listed = [spot for spot in self.game.EnemyPositions if self.game.grid[spot][2] is self.queen]
                self.assertEqual(listed, [self.anchor])
        self.assertEqual(len(dwellers.cityDwellers(self.game)), 2, "nobody lost or doubled")


class RoyalGuardTests(QueenTest):
    def addRoyal(self, column, row):
        royal = self.addDweller(enemies.RoyalGuard, column, row)
        self.queen.royalPosts.append(royal.home)
        return royal

    def test_a_royal_guard_hunts_you_near_the_queen(self):
        royal = self.addRoyal(28, 20)
        self.standAt(28, 25)
        dwellers.turnHostile(self.game, royal, self.game.playerPositionFlat)
        self.game.player.damageTaken = 0
        self.assertTrue(self.runTurns(10, until=lambda: self.game.player.damageTaken > 0))

    def test_it_never_follows_you_past_its_leash(self):
        royal = self.addRoyal(28, 20)
        self.standAt(28, 50)
        dwellers.turnHostile(self.game, royal, self.game.playerPositionFlat)
        self.runTurns(30)
        self.assertLessEqual(dwellers.distance(self.game, self.positionOf(royal), royal.home), royal.leash)

    def test_it_goes_after_an_enemy_near_the_queen_but_not_one_past_its_leash(self):
        royal = self.addRoyal(28, 20)  # its post
        lookingFrom = self.spot(28, 25)  # (it has walked out a way)
        beyond = self.addGoblin(28, 30)  # in sight from there, but 10 from its post
        beyond.speed = 0
        self.assertIsNone(dwellers.enemyInSight(self.game, lookingFrom, royal))
        near = self.addGoblin(28, 27)
        near.speed = 0
        self.assertEqual(dwellers.enemyInSight(self.game, lookingFrom, royal), (self.spot(28, 27), near))
        guard = self.addDweller(enemies.DwellerGuard, 40, 20)
        guard.home = royal.home
        self.assertIsNotNone(dwellers.enemyInSight(self.game, self.spot(28, 29), guard), "an ordinary guard would go")


class PupatingTests(QueenTest):
    def setUp(self):
        super().setUp()
        self.queen.royalPosts = [self.spot(28, 20), self.spot(33, 20), self.spot(28, 23), self.spot(33, 23)]
        self.nearGuard = self.addDweller(enemies.DwellerGuard, 36, 20)
        self.farGuard = self.addDweller(enemies.DwellerGuard, 50, 40)

    def test_short_of_royal_guards_the_guard_nearest_the_queen_pupates(self):
        with mock.patch.object(queen, "PUPATE_CHANCE", 1):
            pupa = queen.stepCourt(self.game)
        self.assertIsNotNone(pupa)
        self.assertIs(self.game.grid[self.spot(36, 20)][2], pupa)
        self.assertIn(pupa.post, self.queen.royalPosts)
        self.assertIs(self.game.grid[self.spot(50, 40)][2], self.farGuard)

    def test_only_one_pupates_at_a_time(self):
        with mock.patch.object(queen, "PUPATE_CHANCE", 1):
            queen.stepCourt(self.game)
            self.assertIsNone(queen.stepCourt(self.game))
        self.assertIs(self.game.grid[self.spot(50, 40)][2], self.farGuard)

    def test_with_a_full_court_nobody_pupates(self):
        for post in self.queen.royalPosts:
            royal = self.addDweller(enemies.RoyalGuard, post % self.rowLength, post // self.rowLength)
            royal.home = post
        with mock.patch.object(queen, "PUPATE_CHANCE", 1):
            self.assertIsNone(queen.stepCourt(self.game))

    def test_a_pupa_comes_out_a_royal_guard_and_goes_to_its_post(self):
        with mock.patch.object(queen, "PUPATE_CHANCE", 1), mock.patch.object(queen, "PUPA_TURNS", 3), \
                mock.patch.object(dwellers, "IDLE_CHANCE", 0):
            pupa = queen.stepCourt(self.game)
            self.runTurns(2)
            self.assertIs(self.game.grid[self.spot(36, 20)][2], pupa, "it doesn't move while it pupates")
            self.runTurns(1)
            royal = self.game.grid[self.spot(36, 20)][2]
            self.assertTrue(queen.isRoyal(royal))
            self.assertEqual(royal.home, pupa.post)
            self.assertTrue(self.runTurns(40, until=lambda: self.positionOf(royal) == royal.home))

    def test_a_pupa_is_never_nudged_aside(self):
        with mock.patch.object(queen, "PUPATE_CHANCE", 1):
            queen.stepCourt(self.game)
        self.assertFalse(dwellers.nudgeAside(self.game, self.spot(36, 20)))


class RealCityTests(unittest.TestCase):
    def test_a_city_with_its_court_runs_without_losing_or_doubling_anyone(self):
        game = cityGame()
        count = len(dwellers.cityDwellers(game))
        anchor, dwellerQueen = queen.courtOf(game)
        for _ in range(40):
            game.enemyTurn()
        self.assertEqual(queen.courtOf(game), (anchor, dwellerQueen))
        self.assertEqual(len(dwellers.cityDwellers(game)), count)
        self.assertEqual(sum(1 for spot in game.EnemyPositions if occupancy.primaryAt(game, spot) is dwellerQueen), 1)


if __name__ == "__main__":
    unittest.main()
