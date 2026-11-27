"""The Pheromone Crown and followers in a running game (followers.py): the city turning on you while you wear it,
winning a follower, what a follower does, and it coming with you between floors.

Integration tests; the rest are in tests/unit/test_followers.py, tests/acceptance/test_followers.py."""
import unittest
from unittest import mock

from cruel.entities import enemies
from cruel.inventory import relics
from cruel.world import dwellers
from cruel.world import followers
from cruel.world import mineshafts
from cruel.world import occupancy
from cruel.world import queen
from tests import support
from tests.helpers.metropolis import cityGame
from tests.helpers.mineshafts import shaftSpot
from tests.integration.test_city_hostility import CityTest

FLOOR, ENEMY = 0, 5
FACING_RIGHT = 1


class CrownTest(CityTest):
    def setUp(self):
        super().setUp()
        self.crown = relics.make("pheromone_crown")

    def wear(self):
        self.game.player.equipment["Head"] = self.crown

    def takeOff(self):
        self.game.player.equipment["Head"] = "None"

    def addGoblin(self, column, row):
        goblin = enemies.Goblin()
        position = self.spot(column, row)
        self.game.grid[position] = [ENEMY, 1, goblin]
        self.game.EnemyPositions.add(position)
        return goblin

    def follow(self, unit):
        followers.convert(self.game, self.positionOf(unit), unit)
        return unit


class WearingTests(CrownTest):
    def test_while_you_wear_it_every_dweller_is_hostile_and_calms_when_you_take_it_off(self):
        self.standAt(5, 5)
        citizen = self.addDweller(enemies.DwellerCitizen, 40, 30)
        angry = self.addDweller(enemies.DwellerGuard, 60, 30)
        dwellers.turnHostile(self.game, angry, self.game.playerPositionFlat)  # (hostile already, for something you did)
        self.wear()
        self.game.enemyTurn()
        self.assertTrue(citizen.hostile and angry.hostile)
        self.takeOff()
        self.game.enemyTurn()
        self.assertFalse(citizen.hostile, "it goes back to how it was")
        self.assertTrue(angry.hostile, "what you did is still remembered")

    def test_the_queen_too(self):
        dwellerQueen = enemies.DwellerQueen()
        anchor = self.spot(30, 20)
        self.game.putGiant(self.game.grid, anchor, dwellerQueen)
        self.game.EnemyPositions.add(anchor)
        self.standAt(32, 21)
        self.wear()
        self.game.player.damageTaken = 0
        self.game.enemyTurn()
        self.assertTrue(dwellerQueen.hostile)
        self.assertGreater(self.game.player.damageTaken, 0)


class ConvertingTests(CrownTest):
    def test_wearing_it_a_dweller_beside_you_may_become_your_follower(self):
        self.standAt(30, 30)
        citizen = self.addDweller(enemies.DwellerCitizen, 31, 30)
        citizen.work = "dew"
        self.wear()
        with mock.patch.object(followers, "CONVERT_CHANCE", 1):
            self.game.enemyTurn()
        self.assertEqual(self.game.player.followers, [citizen])
        self.assertTrue(citizen.follower)
        self.assertFalse(citizen.hostile)
        self.assertIsNone(citizen.work, "it leaves its work")

    def test_not_without_the_crown_not_from_further_off_and_not_with_no_room(self):
        self.standAt(30, 30)
        beside = self.addDweller(enemies.DwellerCitizen, 31, 30)
        farther = self.addDweller(enemies.DwellerCitizen, 33, 30)
        with mock.patch.object(followers, "CONVERT_CHANCE", 1):
            self.assertIsNone(followers.stepConvert(self.game), "without the crown")
            self.wear()
            self.assertIs(followers.stepConvert(self.game), beside)
            self.addDweller(enemies.DwellerNoble, 29, 30)
            self.assertIsNone(followers.stepConvert(self.game), "one follower is the most")
        self.assertFalse(getattr(farther, "follower", False))

    def test_a_merchant_never_follows(self):
        self.standAt(30, 30)
        self.addDweller(enemies.DwellerMerchant, 31, 30)
        self.wear()
        with mock.patch.object(followers, "CONVERT_CHANCE", 1):
            self.assertIsNone(followers.stepConvert(self.game))

    def test_one_carrying_an_egg_sets_it_down(self):
        self.standAt(30, 30)
        citizen = self.addDweller(enemies.DwellerCitizen, 31, 30)
        citizen.heldEgg = egg = enemies.DwellerEgg()
        self.follow(citizen)
        self.assertIsNone(citizen.heldEgg)
        self.assertIn(egg, [unit for _, unit in dwellers.cityDwellers(self.game)])


class FollowerTests(CrownTest):
    def setUp(self):
        super().setUp()
        self.standAt(30, 30)
        self.follower = self.follow(self.addDweller(enemies.DwellerGuard, 31, 30))

    def test_it_keeps_close_to_you(self):
        self.standAt(45, 30)
        with mock.patch.object(dwellers, "IDLE_CHANCE", 0):
            self.runTurns(20)
        self.assertLessEqual(dwellers.distance(self.game, self.positionOf(self.follower), self.game.playerPositionFlat),
                             followers.KEEP_CLOSE)

    def test_it_fights_what_is_hostile_to_you_but_not_calm_dwellers(self):
        goblin = self.addGoblin(33, 30)
        goblin.speed = 0  # (it stays put)
        calm = self.addDweller(enemies.DwellerCitizen, 31, 31)
        before = goblin.hp
        self.assertTrue(self.runTurns(10, until=lambda: goblin.hp < before
                                      or goblin not in [unit for _, unit in occupancy.allUnits(self.game)]))
        self.assertEqual(calm.hp, calm.maxHp)

    def test_the_city_s_guards_fight_it(self):
        guard = self.addDweller(enemies.DwellerGuard, 33, 30)
        self.assertEqual(dwellers.enemyInSight(self.game, self.spot(33, 30), guard)[1], self.follower)

    def test_it_never_hurts_you(self):
        self.game.player.damageTaken = 0
        self.runTurns(10)
        self.assertEqual(self.game.player.damageTaken, 0)

    def test_walking_into_it_swaps_places(self):
        where = self.positionOf(self.follower)
        before = self.game.playerPositionFlat
        self.game.movePlayer(where)
        self.assertEqual(self.game.playerPositionFlat, where)
        self.assertIs(self.game.grid[before][2], self.follower)
        self.assertIn(before, self.game.EnemyPositions)
        self.assertNotIn(where, self.game.EnemyPositions)

    def test_interacting_with_it_does_not_hit_it_but_shift_does(self):
        self.game.player.playerDirection = FACING_RIGHT
        self.game.setLookPosition()
        self.game.player.DealDamage = lambda: 3
        self.game.enemyDodge = lambda target, damage, position: damage
        self.game.onInteract()
        self.assertEqual(self.follower.hp, self.follower.maxHp)
        self.game.onInteract(forceAttack=True)
        self.assertLess(self.follower.hp, self.follower.maxHp)

    def test_one_that_dies_is_forgotten(self):
        self.game.killEnemy(self.positionOf(self.follower), killer=None)
        self.game.enemyTurn()
        self.assertEqual(self.game.player.followers, [])


class FloorChangeTests(unittest.TestCase):
    def test_your_follower_comes_with_you_down_a_shaft_and_back_up(self):
        game = cityGame()
        game.player.equipment["Head"] = relics.make("pheromone_crown")
        spot, citizen = next((spot, unit) for spot, unit in dwellers.cityDwellers(game) if unit.role == "citizen")
        support.placePlayer(game, next(near for near in game.neighbors(spot) if game.grid[near][0] == FLOOR))
        followers.convert(game, spot, citizen)
        for floorKey in ("down", "up"):
            if floorKey == "down":
                support.placePlayer(game, shaftSpot(game, "mine"))
            game.onEnter()
            here = [unit for _, unit in dwellers.cityDwellers(game)]
            self.assertIn(citizen, here, floorKey)
            where = next(position for position, unit in dwellers.cityDwellers(game) if unit is citizen)
            self.assertLessEqual(dwellers.distance(game, where, game.playerPositionFlat), 2)
            self.assertEqual(citizen.floorKey, mineshafts.floorKey(game))
            self.assertEqual(game.player.followers, [citizen])

    def test_down_the_stairs_too(self):
        game = support.newGame(level=0)
        citizen = enemies.DwellerCitizen()
        spot = support.openTile(game)
        game.grid[spot] = [ENEMY, 1, citizen]
        game.EnemyPositions.add(spot)
        citizen.follower, citizen.floorKey = True, mineshafts.floorKey(game)
        game.player.followers = [citizen]
        game.goToNewLevel()
        self.assertIn(citizen, [unit for _, unit in occupancy.allUnits(game)])
        self.assertNotIn(citizen, [tile[2] for tile in game.levelGrids[0][0].values() if len(tile) > 2])


if __name__ == "__main__":
    unittest.main()
