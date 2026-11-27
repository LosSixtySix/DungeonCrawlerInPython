"""Hostility in the Metropolis (dwellers.py): only Dwellers who see you steal, break or hurt something turn hostile;
citizens, nobles and merchants run to a guard and tell it; guards hunt you; a cornered Dweller fights back; and the
city calms down after a while (except its guards)."""
import random
import unittest

from cruel.entities import enemies
from cruel.inventory import resources
from cruel.world import dwellers
from cruel.world import metropolis
from cruel.world import wall
from tests import support
from tests.helpers.expansion import blankFloor

FLOOR, PLAYER, WALL, CHEST, ENEMY = 0, 1, 2, 3, 5
FACING_RIGHT = 1


class CityTest(unittest.TestCase):
    """An open city floor with nothing on it: the player in the top-left corner, Dwellers placed by each test."""

    def setUp(self):
        random.seed(8)
        self.game = support.newGame()
        blankFloor(self.game)
        self.game.proportion = metropolis.METROPOLIS
        self.game.player.evasion = lambda: 0  # every hit on you lands
        self.rowLength = self.game.rowLength

    def spot(self, column, row):
        return column + row * self.rowLength

    def addDweller(self, kind, column, row, home=None):
        dweller = kind()
        position = self.spot(column, row)
        dweller.home = home if home is not None else position
        self.game.grid[position] = [ENEMY, 1, dweller]
        self.game.EnemyPositions.add(position)
        return dweller

    def addWall(self, column, row):
        self.game.grid[self.spot(column, row)] = [WALL, 1, wall.HouseWall()]

    def standAt(self, column, row, facing=FACING_RIGHT):
        support.placePlayer(self.game, self.spot(column, row))
        self.game.currentLocation = [FLOOR, 1]
        self.game.player.playerDirection = facing
        self.game.setLookPosition()

    def positionOf(self, dweller):
        return next(spot for spot, found in dwellers.cityDwellers(self.game) if found is dweller)

    def runTurns(self, count, until=None):
        for _ in range(count):
            self.game.enemyTurn()
            if until is not None and until():
                return True
        return False


class WitnessTests(CityTest):
    """Who sees a hostile act."""

    def test_only_dwellers_who_see_a_wall_break_turn_hostile(self):
        self.standAt(30, 20)
        self.addWall(31, 20)
        watching = self.addDweller(enemies.DwellerCitizen, 34, 20)
        self.addWall(31, 23)
        self.addWall(32, 23)
        self.addWall(30, 23)
        behindAWall = self.addDweller(enemies.DwellerCitizen, 31, 25)
        for column in range(29, 34):  # a wall between it and the broken one
            self.addWall(column, 22)
        tooFar = self.addDweller(enemies.DwellerCitizen, 45, 20)
        self.game.breakWall(self.spot(31, 20))
        self.assertTrue(watching.hostile)
        self.assertFalse(behindAWall.hostile)
        self.assertFalse(tooFar.hostile)

    def test_if_nobody_sees_it_nothing_happens(self):
        self.standAt(30, 20)
        self.addWall(31, 20)
        faraway = self.addDweller(enemies.DwellerGuard, 70, 50)
        self.assertEqual(dwellers.hostileAct(self.game, self.spot(31, 20)), 0)
        self.game.breakWall(self.spot(31, 20))
        self.assertFalse(faraway.hostile)

    def test_the_dweller_you_hurt_always_knows(self):
        self.standAt(30, 20)
        victim = self.addDweller(enemies.DwellerNoble, 31, 20)
        self.game.enemyDodge = lambda target, damage, position: damage
        self.game.player.DealDamage = lambda: 3  # (bare hands can do 0, which hurts nobody)
        self.game.onInteract()
        self.assertTrue(victim.hostile)

    def test_taking_from_a_city_chest_is_stealing(self):
        self.standAt(30, 20)
        self.game.grid[self.spot(31, 20)] = [CHEST, 1, metropolis.CityChest([resources.MaterialStack("stone", 3)])]
        watching = self.addDweller(enemies.DwellerCitizen, 33, 21)
        self.game.roomItems = self.game.getItemsFromGrid()
        self.game.windowSel["items"] = 0
        self.game.pickUpItem()
        self.assertTrue(watching.hostile)

    def test_taking_from_an_ordinary_chest_is_not(self):
        self.standAt(30, 20)
        self.game.grid[self.spot(31, 20)] = [CHEST, 1, [resources.MaterialStack("stone", 3)]]
        watching = self.addDweller(enemies.DwellerCitizen, 33, 21)
        self.game.roomItems = self.game.getItemsFromGrid()
        self.game.windowSel["items"] = 0
        self.game.pickUpItem()
        self.assertFalse(watching.hostile)

    def test_outside_a_city_dwellers_do_not_care(self):
        self.game.proportion = "Mostly Stone"
        self.standAt(30, 20)
        self.addWall(31, 20)
        watching = self.addDweller(enemies.DwellerCitizen, 34, 20)
        self.game.breakWall(self.spot(31, 20))
        self.assertFalse(watching.hostile)

    def test_a_guard_who_sees_it_hunts_you_without_being_told(self):
        self.standAt(30, 20)
        self.addWall(31, 20)
        guard = self.addDweller(enemies.DwellerGuard, 35, 20)
        self.game.breakWall(self.spot(31, 20))
        self.assertTrue(guard.hostile)
        self.game.player.damageTaken = 0
        self.assertTrue(self.runTurns(15, until=lambda: self.game.player.damageTaken > 0))

    def test_a_hostile_dweller_says_so_when_you_look_at_it(self):
        self.standAt(30, 20)
        citizen = self.addDweller(enemies.DwellerCitizen, 31, 20)
        self.assertEqual(self.game.lookingAt(), "Dweller Citizen")
        dwellers.turnHostile(self.game, citizen, self.game.playerPositionFlat)
        self.assertEqual(self.game.lookingAt(), "Dweller Citizen (hostile)")


class FleeingTests(CityTest):
    """Citizens, nobles and merchants run to a guard and tell it."""

    def test_a_hostile_citizen_runs_to_the_nearest_guard_and_tells_it(self):
        self.standAt(2, 2)  # far out of everyone's sight
        citizen = self.addDweller(enemies.DwellerCitizen, 20, 30, home=self.spot(10, 30))
        nearGuard = self.addDweller(enemies.DwellerGuard, 40, 30)
        farGuard = self.addDweller(enemies.DwellerGuard, 90, 60)
        whereItSawYou = self.spot(22, 28)
        dwellers.turnHostile(self.game, citizen, whereItSawYou)
        self.assertTrue(self.runTurns(40, until=lambda: nearGuard.hostile))
        self.assertEqual(nearGuard.sawYouAt, whereItSawYou, "it tells the guard where it saw you")
        self.assertFalse(farGuard.hostile)
        self.assertTrue(citizen.toldGuard)

    def test_having_told_a_guard_it_goes_home(self):
        self.standAt(2, 2)
        home = self.spot(10, 30)
        citizen = self.addDweller(enemies.DwellerCitizen, 20, 30, home=home)
        self.addDweller(enemies.DwellerGuard, 22, 30)
        dwellers.turnHostile(self.game, citizen, self.spot(20, 28))
        self.runTurns(40)
        self.assertEqual(self.positionOf(citizen), home)

    def test_with_no_guards_left_it_runs_away_from_you(self):
        self.standAt(30, 30)
        citizen = self.addDweller(enemies.DwellerCitizen, 33, 30)
        dwellers.turnHostile(self.game, citizen, self.game.playerPositionFlat)
        self.runTurns(5)
        self.assertGreater(dwellers.distance(self.game, self.positionOf(citizen), self.game.playerPositionFlat), 3)

    def test_a_cornered_dweller_fights_back(self):
        self.standAt(29, 30)
        merchant = self.addDweller(enemies.DwellerMerchant, 30, 30)
        for column, row in ((31, 30), (30, 29), (30, 31), (31, 29), (31, 31)):  # walls on its other sides
            self.addWall(column, row)
        self.addDweller(enemies.DwellerGuard, 80, 60)
        dwellers.turnHostile(self.game, merchant, self.game.playerPositionFlat)
        self.assertTrue(dwellers.cornered(self.game, self.spot(30, 30)))
        self.game.player.damageTaken = 0
        self.game.enemyTurn()
        self.assertEqual(self.game.player.damageTaken, 1)

    def test_a_dweller_with_room_to_run_runs_instead(self):
        self.standAt(29, 30)
        citizen = self.addDweller(enemies.DwellerCitizen, 30, 30)
        self.addDweller(enemies.DwellerGuard, 80, 60)
        dwellers.turnHostile(self.game, citizen, self.game.playerPositionFlat)
        self.assertFalse(dwellers.cornered(self.game, self.spot(30, 30)))
        self.game.player.damageTaken = 0
        self.game.enemyTurn()
        self.assertEqual(self.game.player.damageTaken, 0)

    def test_calm_dwellers_beside_a_hostile_one_stay_calm(self):
        self.standAt(2, 2)
        hostileOne = self.addDweller(enemies.DwellerCitizen, 30, 30)
        calmOne = self.addDweller(enemies.DwellerCitizen, 32, 30)
        dwellers.turnHostile(self.game, hostileOne, self.spot(30, 28))
        self.runTurns(5)
        self.assertFalse(calmOne.hostile)


class ForgivingTests(CityTest):
    """The city calms down, but its guards don't."""

    def test_a_citizen_calms_down_after_a_long_time_without_seeing_you(self):
        self.standAt(2, 2)
        citizen = self.addDweller(enemies.DwellerCitizen, 50, 40)
        dwellers.turnHostile(self.game, citizen, self.spot(50, 38))
        citizen.lastSawYou = self.game.turnCount - dwellers.FORGIVE_TURNS
        self.game.enemyTurn()
        self.assertFalse(citizen.hostile)

    def test_it_stays_hostile_while_it_can_see_you(self):
        self.standAt(48, 40)
        citizen = self.addDweller(enemies.DwellerCitizen, 50, 40)
        dwellers.turnHostile(self.game, citizen, self.game.playerPositionFlat)
        citizen.lastSawYou = self.game.turnCount - dwellers.FORGIVE_TURNS
        dwellers.takeTurn(self.game, self.spot(50, 40), citizen)  # (it sees you first, then decides)
        self.assertTrue(citizen.hostile)

    def test_guards_never_calm_down(self):
        self.standAt(2, 2)
        guard = self.addDweller(enemies.DwellerGuard, 50, 40)
        dwellers.turnHostile(self.game, guard, self.spot(50, 38))
        guard.lastSawYou = self.game.turnCount - 10 * dwellers.FORGIVE_TURNS
        self.runTurns(3)
        self.assertTrue(guard.hostile)


class GuardTests(CityTest):
    """Hostile guards hunt you."""

    def test_a_told_guard_goes_where_you_were_seen(self):
        self.standAt(2, 2)
        guard = self.addDweller(enemies.DwellerGuard, 60, 40)
        whereYouWereSeen = self.spot(45, 40)
        dwellers.tellGuard(self.game, self.spot(60, 40), guard, whereYouWereSeen)
        self.runTurns(10)
        self.assertLess(dwellers.distance(self.game, self.positionOf(guard), whereYouWereSeen), 5)

    def test_a_hostile_guard_beside_you_hits_you(self):
        self.standAt(29, 30)
        guard = self.addDweller(enemies.DwellerGuard, 30, 30)
        dwellers.turnHostile(self.game, guard, self.game.playerPositionFlat)
        self.game.player.damageTaken = 0
        self.game.enemyTurn()
        self.assertGreater(self.game.player.damageTaken, 0)

    def test_a_hunting_guard_gets_past_a_dweller_coming_the_other_way_in_a_narrow_passage(self):
        for column in range(15, 42):  # a corridor one tile wide along row 30
            self.addWall(column, 29)
            self.addWall(column, 31)
        self.standAt(46, 30)
        guard = self.addDweller(enemies.DwellerGuard, 18, 30)
        citizen = self.addDweller(enemies.DwellerCitizen, 30, 30, home=self.spot(10, 30))
        self.addDweller(enemies.DwellerMerchant, 31, 30)  # behind it and never moving: it can't be nudged aside
        dwellers.turnHostile(self.game, citizen, self.spot(30, 30))
        citizen.toldGuard = True  # it's on its way home, toward the guard
        dwellers.tellGuard(self.game, self.spot(18, 30), guard, self.game.playerPositionFlat)
        count = len(dwellers.cityDwellers(self.game))
        self.game.player.damageTaken = 0
        self.assertTrue(self.runTurns(60, until=lambda: self.game.player.damageTaken > 0), "the guard got past and reached you")
        self.assertEqual(len(dwellers.cityDwellers(self.game)), count, "nobody lost or doubled")

    def test_a_calm_guard_beside_you_does_not(self):
        self.standAt(29, 30)
        self.addDweller(enemies.DwellerGuard, 30, 30)
        self.game.player.damageTaken = 0
        for _ in range(5):
            self.game.enemyTurn()
        self.assertEqual(self.game.player.damageTaken, 0)


if __name__ == "__main__":
    unittest.main()
