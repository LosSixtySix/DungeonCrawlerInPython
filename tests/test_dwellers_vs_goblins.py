"""Dwellers against the city's enemies (dwellers.dealWithEnemies): every Dweller is hostile to every monster that
isn't a Dweller or the Gray Peddler, goblins of any faction (neutral ones too) included. Only guards hunt and kill
them; everyone else runs to a guard and tells it where the enemy is, and only fights back when cornered. None of it
turns the city against you."""
import random
import unittest

from cruel.entities import enemies
from cruel.world import dwellers
from cruel.world import expansion
from cruel.world import metropolis
from cruel.world import wall
from tests import support
from tests.test_expansion import blankFloor

FLOOR, WALL, ENEMY = 0, 2, 5


class EnemyTest(unittest.TestCase):
    """An open city floor, you far off in the top-left corner, Dwellers and enemies placed by each test."""

    def setUp(self):
        random.seed(9)
        expansion.PEACE.clear()
        self.game = support.newGame()
        blankFloor(self.game)
        self.game.proportion = metropolis.METROPOLIS
        self.rowLength = self.game.rowLength
        self.game.enemyDodge = lambda target, damage, position: damage  # every hit lands

    def tearDown(self):
        expansion.PEACE.clear()

    def spot(self, column, row):
        return column + row * self.rowLength

    def place(self, unit, column, row):
        if dwellers.isDweller(unit) and unit.home is None:
            unit.home = self.spot(column, row)
        unit.hp = unit.maxHp = 200  # tough enough to last the test
        self.game.grid[self.spot(column, row)] = [ENEMY, 1, unit]
        self.game.EnemyPositions.add(self.spot(column, row))
        return unit

    def factionGoblin(self, neutral=False):
        faction = expansion.newFaction(self.game, "warpaint", neutral=neutral)
        goblin = enemies.Goblin()
        expansion.setFaction(goblin, faction)
        return goblin

    def wall(self, column, row):
        self.game.grid[self.spot(column, row)] = [WALL, 1, wall.HouseWall()]

    def positionOf(self, unit):
        return next(spot for spot in set(self.game.EnemyPositions) if len(self.game.grid[spot]) > 2 and self.game.grid[spot][2] is unit)

    def runTurns(self, count, until):
        for _ in range(count):
            self.game.enemyTurn()
            if until():
                return True
        return False


class GuardTests(EnemyTest):
    """Guards hunt and kill enemies."""

    def test_a_guard_goes_after_a_goblin_it_can_see_and_fights_it(self):
        self.place(enemies.DwellerGuard(), 40, 30)
        goblin = self.place(self.factionGoblin(), 45, 30)
        self.assertTrue(self.runTurns(15, until=lambda: goblin.hp < goblin.maxHp))

    def test_a_neutral_factions_goblin_too(self):
        self.place(enemies.DwellerGuard(), 40, 30)
        goblin = self.place(self.factionGoblin(neutral=True), 45, 30)
        self.assertTrue(self.runTurns(15, until=lambda: goblin.hp < goblin.maxHp))

    def test_a_wild_goblin_too(self):
        self.place(enemies.DwellerGuard(), 40, 30)
        goblin = self.place(enemies.Goblin(), 45, 30)
        self.assertTrue(self.runTurns(15, until=lambda: goblin.hp < goblin.maxHp))

    def test_any_monster_counts_but_not_dwellers_or_the_peddler(self):
        for kind in (enemies.Goblin, enemies.GoblinChief, enemies.GoblinBuilder, enemies.GoblinFarmer, enemies.DireRat, enemies.FireGiant):
            self.assertTrue(dwellers.isCityEnemy(kind()), kind.__name__)
        for kind in (enemies.DwellerCitizen, enemies.DwellerGuard, enemies.GrayPeddler):
            self.assertFalse(dwellers.isCityEnemy(kind()), kind.__name__)

    def test_a_guard_does_not_see_through_walls(self):
        self.place(enemies.DwellerGuard(), 40, 30)
        for row in range(20, 41):
            self.wall(42, row)
        self.place(enemies.Goblin(), 45, 30)
        guard = self.game.grid[self.spot(40, 30)][2]
        self.assertIsNone(dwellers.enemyInSight(self.game, self.spot(40, 30), guard))

    def test_a_guard_hunting_you_puts_you_first(self):
        game = self.game
        support.placePlayer(game, self.spot(39, 30))
        guard = self.place(enemies.DwellerGuard(), 40, 30)
        goblin = self.place(self.factionGoblin(), 41, 30)
        dwellers.turnHostile(game, guard, game.playerPositionFlat)
        game.player.evasion = lambda: 0
        game.player.damageTaken = 0
        dwellers.takeTurn(game, self.spot(40, 30), guard)
        self.assertGreater(game.player.damageTaken, 0)
        self.assertEqual(goblin.hp, goblin.maxHp)


class AlarmTests(EnemyTest):
    """Everyone else runs to a guard and tells it."""

    def test_a_citizen_does_not_fight_an_enemy_it_can_run_from(self):
        citizen = self.place(enemies.DwellerCitizen(), 40, 30)
        goblin = self.place(enemies.Goblin(), 41, 30)
        self.place(enemies.DwellerGuard(), 10, 60)
        dwellers.takeTurn(self.game, self.spot(40, 30), citizen)
        self.assertEqual(goblin.hp, goblin.maxHp)

    def test_nobles_and_merchants_do_not_either(self):
        for kind in (enemies.DwellerNoble, enemies.DwellerMerchant):
            self.setUp()
            dweller = self.place(kind(), 40, 30)
            goblin = self.place(enemies.Goblin(), 41, 30)
            self.place(enemies.DwellerGuard(), 10, 60)
            dwellers.takeTurn(self.game, self.spot(40, 30), dweller)
            self.assertEqual(goblin.hp, goblin.maxHp, kind.__name__)

    def test_a_cornered_citizen_fights_back(self):
        citizen = self.place(enemies.DwellerCitizen(), 40, 30)
        goblin = self.place(enemies.Goblin(), 41, 30)
        for column, row in ((39, 30), (40, 29), (40, 31), (39, 29), (39, 31)):  # walls behind it: nowhere to run
            self.wall(column, row)
        self.assertTrue(dwellers.corneredBy(self.game, self.spot(40, 30), self.spot(41, 30)))
        dwellers.takeTurn(self.game, self.spot(40, 30), citizen)
        self.assertEqual(goblin.hp, goblin.maxHp - citizen.damage)

    def test_a_citizen_that_sees_an_enemy_tells_a_guard_and_the_guard_goes_after_it(self):
        game = self.game
        guard = self.place(enemies.DwellerGuard(), 20, 30)
        for row in range(20, 41):  # the guard can't see the goblin from its post
            self.wall(30, row)
        citizen = self.place(enemies.DwellerCitizen(), 34, 30)
        goblin = self.place(enemies.Goblin(), 38, 30)
        self.assertIsNone(dwellers.enemyInSight(game, self.spot(20, 30), guard))
        self.assertTrue(self.runTurns(40, until=lambda: guard.enemyAt is not None or goblin.hp < goblin.maxHp), "the citizen told it")
        self.assertIsNone(citizen.enemyAt, "having told it, it goes back to its day")
        self.assertTrue(self.runTurns(60, until=lambda: goblin.hp < goblin.maxHp), "the guard found the goblin")

    def test_with_no_guard_left_it_runs_from_the_enemy(self):
        citizen = self.place(enemies.DwellerCitizen(), 40, 30)
        self.place(enemies.Goblin(), 43, 30)
        newSpot = dwellers.takeTurn(self.game, self.spot(40, 30), citizen)
        self.assertGreater(dwellers.distance(self.game, newSpot, self.spot(43, 30)), 3)

    def test_the_goblin_still_fights_the_dweller(self):
        citizen = self.place(enemies.DwellerCitizen(), 40, 30)
        self.place(self.factionGoblin(), 41, 30)
        self.assertTrue(self.runTurns(10, until=lambda: citizen.hp < citizen.maxHp))


class YouTests(EnemyTest):
    def test_dealing_with_enemies_never_turns_the_city_on_you(self):
        guard = self.place(enemies.DwellerGuard(), 40, 30)
        citizen = self.place(enemies.DwellerCitizen(), 50, 30)
        self.place(self.factionGoblin(), 45, 30)
        self.place(enemies.Goblin(), 52, 30)
        for _ in range(20):
            self.game.enemyTurn()
        self.assertFalse(guard.hostile)
        self.assertFalse(citizen.hostile)


if __name__ == "__main__":
    unittest.main()
