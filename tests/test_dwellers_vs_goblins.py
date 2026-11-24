"""Dwellers against goblins (dwellers.fightGoblins): every Dweller is hostile to every goblin, from a war band, a neutral
faction or the wild. Guards go after any goblin they can see; the others fight one right beside them. None of it
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


class GoblinFightTest(unittest.TestCase):
    """An open city floor, you far off in the top-left corner, Dwellers and goblins placed by each test."""

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
        unit.home = getattr(unit, "home", None) or self.spot(column, row)
        unit.hp = unit.maxHp = 200  # tough enough to last the test
        self.game.grid[self.spot(column, row)] = [ENEMY, 1, unit]
        self.game.EnemyPositions.add(self.spot(column, row))
        return unit

    def factionGoblin(self, neutral=False):
        faction = expansion.newFaction(self.game, "warpaint", neutral=neutral)
        goblin = enemies.Goblin()
        expansion.setFaction(goblin, faction)
        return goblin

    def runTurns(self, count, until):
        for _ in range(count):
            self.game.enemyTurn()
            if until():
                return True
        return False


class GuardTests(GoblinFightTest):
    def test_a_guard_goes_after_a_goblin_it_can_see_and_fights_it(self):
        guard = self.place(enemies.DwellerGuard(), 40, 30)
        goblin = self.place(self.factionGoblin(), 45, 30)
        self.assertTrue(self.runTurns(15, until=lambda: goblin.hp < goblin.maxHp))

    def test_neutral_factions_goblins_too(self):
        self.place(enemies.DwellerGuard(), 40, 30)
        goblin = self.place(self.factionGoblin(neutral=True), 45, 30)
        self.assertTrue(self.runTurns(15, until=lambda: goblin.hp < goblin.maxHp))

    def test_wild_goblins_too(self):
        self.place(enemies.DwellerGuard(), 40, 30)
        goblin = self.place(enemies.Goblin(), 45, 30)
        self.assertTrue(self.runTurns(15, until=lambda: goblin.hp < goblin.maxHp))

    def test_a_guard_does_not_chase_a_goblin_it_cannot_see(self):
        game = self.game
        self.place(enemies.DwellerGuard(), 40, 30)
        for row in range(20, 41):  # a wall between them
            game.grid[self.spot(42, row)] = [WALL, 1, wall.HouseWall()]
        self.place(enemies.Goblin(), 45, 30)
        self.assertIsNone(dwellers.goblinInSight(game, self.spot(40, 30), game.grid[self.spot(40, 30)][2]))

    def test_a_guard_hunting_you_puts_you_before_a_goblin(self):
        game = self.game
        support.placePlayer(game, self.spot(39, 30))
        guard = self.place(enemies.DwellerGuard(), 40, 30)
        goblin = self.place(self.factionGoblin(), 41, 30)
        dwellers.turnHostile(game, guard, game.playerPositionFlat)
        game.player.evasion = lambda: 0
        game.player.damageTaken = 0
        hpBefore = goblin.hp
        dwellers.takeTurn(game, self.spot(40, 30), guard)
        self.assertGreater(game.player.damageTaken, 0)
        self.assertEqual(goblin.hp, hpBefore)


class OtherDwellerTests(GoblinFightTest):
    def test_a_citizen_fights_a_goblin_beside_it(self):
        citizen = self.place(enemies.DwellerCitizen(), 40, 30)
        goblin = self.place(self.factionGoblin(), 41, 30)
        hpBefore = goblin.hp
        dwellers.takeTurn(self.game, self.spot(40, 30), citizen)
        self.assertEqual(goblin.hp, hpBefore - citizen.damage)

    def test_nobles_and_merchants_do_too(self):
        for kind in (enemies.DwellerNoble, enemies.DwellerMerchant):
            dweller = self.place(kind(), 40, 30)
            goblin = self.place(enemies.Goblin(), 41, 30)
            hpBefore = goblin.hp
            dwellers.takeTurn(self.game, self.spot(40, 30), dweller)
            self.assertLess(goblin.hp, hpBefore, kind.__name__)

    def test_a_citizen_does_not_go_looking_for_goblins(self):
        citizen = self.place(enemies.DwellerCitizen(), 40, 30)
        self.place(enemies.Goblin(), 44, 30)
        self.assertIsNone(dwellers.fightGoblins(self.game, self.spot(40, 30), citizen))

    def test_the_goblin_fights_back(self):
        citizen = self.place(enemies.DwellerCitizen(), 40, 30)
        self.place(self.factionGoblin(), 41, 30)
        self.assertTrue(self.runTurns(10, until=lambda: citizen.hp < citizen.maxHp))


class YouTests(GoblinFightTest):
    def test_fighting_goblins_never_turns_the_city_on_you(self):
        guard = self.place(enemies.DwellerGuard(), 40, 30)
        citizen = self.place(enemies.DwellerCitizen(), 50, 30)
        self.place(self.factionGoblin(), 45, 30)
        self.place(enemies.Goblin(), 51, 30)
        for _ in range(20):
            self.game.enemyTurn()
        self.assertFalse(guard.hostile)
        self.assertFalse(citizen.hostile)

    def test_every_kind_of_goblin_counts(self):
        for kind in (enemies.Goblin, enemies.GoblinChief, enemies.GoblinBuilder, enemies.GoblinFarmer):
            self.assertTrue(dwellers.isGoblin(kind()), kind.__name__)
        for kind in (enemies.DwellerCitizen, enemies.GrayPeddler, enemies.FireGiant):
            self.assertFalse(dwellers.isGoblin(kind()), kind.__name__)


if __name__ == "__main__":
    unittest.main()
