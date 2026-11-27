"""Dwellers walking between a city and its works floors through the mineshafts (livingfloors.climb and arrive), and
the Queen's Dew carriers who use them (queen.carrierTurn).

Integration tests; the rest are in tests/unit/test_queen.py, tests/acceptance/test_dew_carriers.py."""
import os
import random
import tempfile
import unittest
from unittest import mock

from cruel.core import gamemanager
from cruel.entities import enemies
from cruel.inventory import resources
from cruel.world import dewgrubs
from cruel.world import dwellers
from cruel.world import dwellerwork
from cruel.world import livingfloors
from cruel.world import metropolis
from cruel.world import mineshafts
from cruel.world import occupancy
from cruel.world import queen
from tests import support
from tests.helpers.metropolis import cityGame, newCity
from tests.helpers.mineshafts import climbDown

FLOOR, ENEMY = 0, 5


def besideFree(game, spot):
    return next(near for near in game.neighbors(spot) if game.grid[near][0] == FLOOR and near != game.playerPositionFlat)


def unitsOnFloor(game, key):
    """The units on the floor with key: the live one, or one kept aside (looked at the way its turn would)."""
    if key == mineshafts.floorKey(game):
        return [unit for _, unit in occupancy.allUnits(game)]
    with livingfloors.awayFloor(game, key):
        return [unit for _, unit in occupancy.allUnits(game)]


class WalkingBetweenFloorsTests(unittest.TestCase):
    def setUp(self):
        self.game = cityGame()
        self.shaft = queen.shaftsHere(self.game, "farm")[0]
        self.farmKey = (self.game.level, self.shaft)

    def climbFrom(self, spot, unit, shaft):
        dewgrubs.placeUnit(self.game, spot, unit)
        occupancy.lift(self.game, spot, unit)
        livingfloors.climb(self.game, spot, unit, shaft)

    def test_climbing_down_it_leaves_the_city_and_comes_out_by_the_farm_shaft_next_turn(self):
        citizen = enemies.DwellerCitizen()
        spot = besideFree(self.game, self.shaft)
        self.climbFrom(spot, citizen, self.shaft)
        self.assertEqual(self.game.grid[spot][0], FLOOR, "the tile it climbed from is clear")
        self.assertNotIn(citizen, [unit for _, unit in dwellers.cityDwellers(self.game)])
        self.assertEqual(livingfloors.arrivals(self.game)[self.farmKey], [(citizen, self.shaft)])
        self.game.enemyTurn()
        self.assertIn(citizen, unitsOnFloor(self.game, self.farmKey))
        self.assertNotIn(self.farmKey, livingfloors.arrivals(self.game))
        with livingfloors.awayFloor(self.game, self.farmKey):
            where = next(spot for spot, unit in occupancy.allUnits(self.game) if unit is citizen)
            self.assertLessEqual(dwellers.distance(self.game, where, self.shaft), 2)

    def test_climbing_up_it_comes_out_in_the_city_by_the_shaft(self):
        climbDown(self.game, "farm")  # (you're on the farm now: the city keeps going)
        citizen = enemies.DwellerCitizen()
        spot = besideFree(self.game, self.shaft)
        self.climbFrom(spot, citizen, self.shaft)
        self.assertEqual(list(livingfloors.arrivals(self.game)), [self.game.level])
        self.game.enemyTurn()
        self.assertIn(citizen, unitsOnFloor(self.game, self.game.level))

    def test_it_comes_out_on_the_floor_you_are_on(self):
        climbDown(self.game, "farm")
        citizen = enemies.DwellerCitizen()
        livingfloors.arrivals(self.game)[mineshafts.floorKey(self.game)] = [(citizen, self.shaft)]
        self.game.enemyTurn()
        self.assertIn(citizen, [unit for _, unit in dwellers.cityDwellers(self.game)])

    def test_with_nowhere_to_stand_it_waits_another_turn(self):
        citizen = enemies.DwellerCitizen()
        livingfloors.arrivals(self.game)[self.farmKey] = [(citizen, self.shaft)]
        with mock.patch.object(livingfloors, "nearestFree", lambda *arguments, **keywords: None):
            self.game.enemyTurn()
        self.assertEqual(livingfloors.arrivals(self.game)[self.farmKey], [(citizen, self.shaft)])

    def test_who_is_on_the_way_is_saved_with_the_game(self):
        citizen = enemies.DwellerCitizen()
        citizen.name = "Traveller"
        livingfloors.arrivals(self.game)[self.farmKey] = [(citizen, self.shaft)]
        path = os.path.join(tempfile.mkdtemp(), "save.pkl")
        gamemanager.gameManager.saveGame(self.game, path)  # (cityGame turns saving off)
        loaded = support.newGame()
        self.assertTrue(loaded.loadGame(path))
        [(unit, shaft)] = livingfloors.arrivals(loaded)[self.farmKey]
        self.assertEqual((unit.name, shaft), ("Traveller", self.shaft))

    def test_floors_you_can_never_reach_again_lose_theirs(self):
        random.seed(2)
        game = support.newGame(level=3)
        game.trackStarts.add(3)
        livingfloors.arrivals(game)[(1, 99)] = [(enemies.DwellerCitizen(), 99)]
        livingfloors.arrivals(game)[3] = [(enemies.DwellerCitizen(), 99)]
        livingfloors.dropUnreachable(game)
        self.assertEqual(list(livingfloors.arrivals(game)), [3])


class DewCarrierTests(unittest.TestCase):
    def setUp(self):
        self.game = cityGame()
        self.anchor, self.queen = queen.courtOf(self.game)
        self.shaft = queen.shaftsHere(self.game, "farm")[0]

    def carrierAt(self, spot, dew=0):
        carrier = enemies.DwellerCitizen()
        carrier.work = "dew"
        if dew:
            carrier.materials["dew"] = dew
        dewgrubs.placeUnit(self.game, spot, carrier)
        return carrier

    def test_a_city_sets_some_citizens_aside_to_carry_dew(self):
        for seed in (1, 2, 3):
            city = newCity(seed)
            carriers = [unit for unit in city.dwellers.values() if unit.work == "dew"]
            self.assertTrue(metropolis.CARRIERS[0] <= len(carriers) <= metropolis.CARRIERS[1])
            self.assertTrue(all(unit.role == "citizen" for unit in carriers))

    def test_beside_the_queen_it_feeds_her_all_its_dew(self):
        spot = next(near for tile in self.game.footprint(self.anchor, 2) for near in self.game.neighbors(tile)
                    if self.game.grid[near][0] == FLOOR)
        carrier = self.carrierAt(spot, dew=7)
        occupancy.lift(self.game, spot, carrier)
        self.assertEqual(queen.carrierTurn(self.game, spot, carrier), spot)
        self.assertEqual((self.queen.dew, carrier.materials.get("dew", 0)), (7, 0))

    def test_empty_handed_it_walks_to_the_farm_shaft_and_climbs_down(self):
        carrier = next(unit for _, unit in dwellers.cityDwellers(self.game) if unit.work == "dew")
        with mock.patch.object(dwellers, "IDLE_CHANCE", 0):
            for _ in range(300):
                self.game.enemyTurn()
                if carrier not in [unit for _, unit in dwellers.cityDwellers(self.game)]:
                    break
        self.assertIn(carrier, unitsOnFloor(self.game, (self.game.level, self.shaft)) +
                      [unit for waiting in livingfloors.arrivals(self.game).values() for unit, _ in waiting])

    def test_on_the_farm_it_takes_dew_from_a_chest_then_climbs_up(self):
        climbDown(self.game, "farm")
        chestSpot = dwellerwork.storageChests(self.game)[0]
        self.game.grid[chestSpot][2].append(resources.MaterialStack("dew", 25))
        carrier = self.carrierAt(besideFree(self.game, chestSpot))
        spot = next(spot for spot, unit in dwellers.cityDwellers(self.game) if unit is carrier)
        occupancy.lift(self.game, spot, carrier)
        queen.carrierTurn(self.game, spot, carrier)
        self.assertEqual(carrier.materials["dew"], queen.CARRY)
        occupancy.settle(self.game, spot, carrier)
        with mock.patch.object(dwellers, "IDLE_CHANCE", 0):
            for _ in range(80):
                self.game.enemyTurn()  # (the city takes its turn after yours: it comes out there the same turn)
                if carrier not in [unit for _, unit in dwellers.cityDwellers(self.game)]:
                    break
        self.assertIn(carrier, unitsOnFloor(self.game, self.game.level), "up in the city")
        self.assertEqual(carrier.materials["dew"], queen.CARRY)

    def test_finding_no_dew_it_goes_back_up_and_rests_before_trying_again(self):
        climbDown(self.game, "farm")
        for chestSpot in dwellerwork.storageChests(self.game):
            self.game.grid[chestSpot][2][:] = [thing for thing in self.game.grid[chestSpot][2]
                                               if getattr(thing, "materialId", None) != "dew"]
        carrier = self.carrierAt(besideFree(self.game, self.game.sideFloor[1]))
        spot = next(spot for spot, unit in dwellers.cityDwellers(self.game) if unit is carrier)
        occupancy.lift(self.game, spot, carrier)
        queen.carrierTurn(self.game, spot, carrier)
        self.assertGreater(carrier.restUntil, self.game.turnCount)
        self.assertTrue(livingfloors.leaving(carrier), "it climbed straight back up")
        self.game.onEnter()  # (you go back up too)
        carrier.climbing = False
        self.assertIsNone(queen.carrierTurn(self.game, self.anchor + 5, carrier), "resting: it goes about the city")

    def test_only_a_few_go_down_at_a_time_so_they_do_not_crowd_the_farmers(self):
        away = queen.carriersAway(self.game, self.queen)
        for _ in range(2):  # (two down on the farm already: the most at a time)
            away[enemies.DwellerCitizen()] = self.game.turnCount
        carrier = self.carrierAt(besideFree(self.game, self.shaft))
        spot = next(spot for spot, unit in dwellers.cityDwellers(self.game) if unit is carrier)
        occupancy.lift(self.game, spot, carrier)
        self.assertIsNone(queen.carrierTurn(self.game, spot, carrier), "it waits its turn")
        self.game.turnCount += queen.AWAY_LIMIT + 1  # (the ones down there have been gone too long: maybe dead)
        queen.carrierTurn(self.game, spot, carrier)
        self.assertTrue(livingfloors.leaving(carrier), "beside the shaft, it climbs down")
        self.assertEqual(list(queen.carriersAway(self.game, self.queen)), [carrier])

    def test_with_no_queen_it_is_just_a_citizen(self):
        self.game.killEnemy(self.anchor, killer=None)
        carrier = self.carrierAt(besideFree(self.game, self.shaft))
        self.assertIsNone(queen.carrierTurn(self.game, self.shaft, carrier))


if __name__ == "__main__":
    unittest.main()
