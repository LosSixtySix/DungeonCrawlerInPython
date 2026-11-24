"""A city's works (mineshafts.py): its mine and its farm, the mineshafts down to them, and the works floors below,
which sit beside the city's floor while you're on them."""
import os
import tempfile
import unittest
from unittest import mock

from cruel.core import gamemanager
from cruel.inventory import items
from cruel.world import dwellers
from cruel.world import events
from cruel.world import metropolis
from cruel.world import mineshafts
from cruel.world import wall
from tests import support
from tests.test_metropolis import cityGame, newCity

FLOOR, WALL, CHEST, ENEMY = 0, 2, 3, 5


def shaftSpot(game, kind):
    return next(spot for spot, tile in game.grid.items() if tile[0] == metropolis.MINESHAFT and tile[2].kind == kind)


def climbDown(game, kind):
    """Walks onto the city's shaft of this kind and presses Enter."""
    support.placePlayer(game, shaftSpot(game, kind))
    game.onEnter()


def dwellersHere(game):
    return [game.grid[spot][2] for spot in game.EnemyPositions
            if game.grid[spot][0] == ENEMY and dwellers.isDweller(game.grid[spot][2])]


class CityWorksTests(unittest.TestCase):
    """The mine and the farm in the city."""

    def test_every_city_has_a_mine_and_a_farm(self):
        for seed in range(10):
            city = newCity(seed)
            self.assertEqual(set(city.works), set(metropolis.WORKS))

    def test_each_has_a_mineshaft_in_its_middle_and_a_sign_by_its_door(self):
        city = newCity(3)
        for kind, building in city.works.items():
            self.assertIn(building.shaft, building.inside)
            shaft = city.grid[building.shaft]
            self.assertEqual(shaft[0], metropolis.MINESHAFT)
            self.assertEqual(shaft[2].kind, kind)
            self.assertTrue(shaft[2].down)
            self.assertEqual(city.grid[building.sign][0], metropolis.SHOP_SIGN)
            self.assertEqual(metropolis.signName(city.grid[building.sign][2]), metropolis.WORKS[kind])

    def test_looking_at_a_shaft_or_standing_on_one_says_where_it_goes(self):
        game = cityGame()
        spot = shaftSpot(game, "mine")
        game.PlayerLookPosition = spot
        self.assertEqual(game.lookingAt(), "Mineshaft down to the Dweller Mine")
        support.placePlayer(game, spot)
        game.updateDoors()
        self.assertEqual(game.currentPosition, "Mineshaft down to the Dweller Mine")


class ClimbingTests(unittest.TestCase):
    """Down a shaft and back up."""

    def test_down_the_mine_shaft_is_a_motherlode_ore_floor(self):
        game = cityGame()
        level = game.level
        climbDown(game, "mine")
        self.assertEqual(game.level, level, "the same depth")
        self.assertIn(game.proportion, wall.ORE_FLOORS)
        self.assertIn(game.level, game.motherlodes)
        self.assertEqual(game.sideFloor[0], "mine")
        self.assertTrue(game.floorTypeName().startswith("Dweller Mine: Motherlode"))

    def test_down_the_farm_shaft_is_a_mixed_cave_floor(self):
        game = cityGame()
        climbDown(game, "farm")
        self.assertEqual(game.proportion, "Mixed")
        self.assertNotIn(game.level, game.motherlodes)

    def test_you_arrive_on_the_shaft_back_up(self):
        game = cityGame()
        spot = shaftSpot(game, "mine")
        climbDown(game, "mine")
        self.assertEqual(game.playerPositionFlat, spot)
        self.assertEqual(game.currentLocation[0], metropolis.MINESHAFT)
        self.assertFalse(game.currentLocation[2].down)

    def test_back_up_you_are_on_the_citys_shaft_and_the_city_is_as_you_left_it(self):
        game = cityGame()
        city = game.grid
        dwellerCount = len(dwellersHere(game))
        city[support.openTile(game)] = [9, 0, []]  # something to find again
        piles = sum(1 for tile in city.values() if tile[0] == 9)
        spot = shaftSpot(game, "farm")
        climbDown(game, "farm")
        game.onEnter()
        self.assertIsNone(game.sideFloor)
        self.assertEqual(game.proportion, metropolis.METROPOLIS)
        self.assertEqual(game.playerPositionFlat, spot)
        self.assertEqual(game.currentLocation[0], metropolis.MINESHAFT)
        self.assertEqual(sum(1 for tile in game.grid.values() if tile[0] == 9), piles)
        self.assertEqual(len(dwellersHere(game)), dwellerCount)

    def test_going_down_again_finds_the_same_works_floor(self):
        game = cityGame()
        climbDown(game, "mine")
        marked = support.openTile(game)
        game.grid[marked] = [9, 0, []]
        game.onEnter()
        game.onEnter()
        self.assertEqual(game.grid[marked][0], 9)

    def test_the_mine_and_the_farm_are_two_different_floors(self):
        game = cityGame()
        climbDown(game, "mine")
        mine = game.proportion
        game.onEnter()
        climbDown(game, "farm")
        self.assertNotEqual(game.proportion, mine)
        self.assertEqual(len(game.floorsAside), 1, "the mine waits aside")

    def test_a_works_floor_has_no_doors(self):
        game = cityGame()
        cityDoor = game.doorPositions[game.level]
        climbDown(game, "mine")
        game.updateDoors()
        self.assertNotIn(game.grid[cityDoor][0], (4, 6))
        support.placePlayer(game, support.openTile(game))
        game.playerPositionFlat = cityDoor  # standing where the city's door down is: nothing happens
        game.currentLocation = [FLOOR, 1]
        game.onEnter()
        self.assertEqual(game.sideFloor[0], "mine")

    def test_a_bomb_never_breaks_a_works_floor(self):
        game = cityGame()
        climbDown(game, "mine")
        with mock.patch.object(gamemanager, "FLOOR_BREAK_CHANCE", 1), mock.patch.object(game, "collapseFloor") as collapse:
            game.land({"landing": support.openTile(game), "effect": "Explosive", "power": 3})
        collapse.assert_not_called()

    def test_floor_keys_and_labels(self):
        game = cityGame()
        self.assertEqual(mineshafts.floorKey(game), game.level)
        spot = shaftSpot(game, "mine")
        climbDown(game, "mine")
        self.assertEqual(mineshafts.floorKey(game), (game.level, spot))
        self.assertEqual(mineshafts.floorNumber((game.level, spot)), game.level)
        self.assertEqual(mineshafts.floorLabel(game.level), str(game.level))
        self.assertEqual(mineshafts.floorLabel((game.level, spot), "mine"), f"{game.level} (Dweller Mine)")


class WorksFloorTests(unittest.TestCase):
    """What's on a works floor."""

    def setUp(self):
        self.game = cityGame()
        climbDown(self.game, "mine")

    def test_storehouses_with_empty_storage_chests_by_the_shaft(self):
        chests = [(spot, tile[2]) for spot, tile in self.game.grid.items() if tile[0] == CHEST and isinstance(tile[2], items.StorageChest)]
        self.assertEqual(len(chests), mineshafts.STOREHOUSES * mineshafts.STOREHOUSE_CHESTS)
        for spot, chest in chests:
            self.assertEqual(list(chest), [])
            self.assertLess(dwellers.distance(self.game, spot, self.game.playerPositionFlat), 12)

    def test_a_storage_chest_belongs_to_the_city(self):
        self.assertIsInstance(items.StorageChest(), items.CityChest)

    def test_workers_and_guards_and_nobody_else(self):
        found = [self.game.grid[spot][2] for spot in self.game.EnemyPositions]
        self.assertTrue(all(dwellers.isDweller(unit) for unit in found))
        roles = [unit.role for unit in found]
        self.assertGreaterEqual(roles.count("guard"), mineshafts.GUARDS[0])
        workers = [unit for unit in found if unit.role == "citizen"]
        self.assertGreaterEqual(len(workers), mineshafts.WORKERS["mine"][0])
        self.assertTrue(all(worker.work == "mine" for worker in workers))

    def test_wall_lamps_light_it(self):
        lamps = metropolis.wallLampsHere(self.game)
        self.assertGreater(len(lamps), 2)
        self.game.updateFireLight()
        spot = next(iter(lamps))
        self.assertIn(spot, self.game.fireLight)

    def test_the_shaft_is_reachable_from_every_storehouse_door(self):
        reach = dwellers.pathMap(self.game, self.game.playerPositionFlat)
        doors = [spot for spot, tile in self.game.grid.items() if tile[0] == CHEST and isinstance(tile[2], items.StorageChest)]
        for chestSpot in doors:
            self.assertTrue(any(near in reach for near in self.game.neighbors(chestSpot)), "you can walk to every chest")

    def test_a_floor_event_can_happen_there_and_the_citys_own_is_kept(self):
        game = cityGame()
        game.floorEvents[game.level] = {"id": "expansion", "turnsLeft": 50, "active": False}
        with mock.patch.object(events, "roll", return_value={"id": "overgrowth", "turnsLeft": 5, "active": False}):
            climbDown(game, "farm")
        self.assertEqual(game.floorEvents[game.level]["id"], "overgrowth")
        game.onEnter()
        self.assertEqual(game.floorEvents[game.level]["id"], "expansion")


class RulesTests(unittest.TestCase):
    """The city's rules hold on its works floors."""

    def test_hurting_a_worker_turns_those_who_see_it_hostile(self):
        game = cityGame()
        climbDown(game, "mine")
        self.assertTrue(dwellers.onDwellerFloor(game))
        spot, worker = next((spot, game.grid[spot][2]) for spot in game.EnemyPositions if game.grid[spot][2].role == "citizen")
        game.playerHurtEnemy(worker, spot)
        self.assertTrue(worker.hostile)

    def test_breaking_the_citys_rock_is_not_hostile_but_breaking_a_building_is(self):
        game = cityGame()
        rock = next(spot for spot in game.rooms[metropolis.YARD] if game.grid[spot][0] == WALL)
        with mock.patch.object(dwellers, "hostileAct") as hostileAct:
            game.breakWall(rock)
            hostileAct.assert_not_called()
            buildingWall = next(spot for spot, tile in game.grid.items() if tile[0] == WALL and isinstance(tile[2], wall.HouseWall))
            game.breakWall(buildingWall)
            hostileAct.assert_called_once()

    def test_an_emptied_storage_chest_stays(self):
        game = cityGame()
        climbDown(game, "mine")
        chestSpot = next(spot for spot, tile in game.grid.items() if tile[0] == CHEST and isinstance(tile[2], items.StorageChest))
        game.PlayerLookPosition = chestSpot
        game.roomItems = game.groundAt(chestSpot)[2]  # (empty: you've just taken the last thing)
        with mock.patch.object(game, "pickUpItem", lambda: None):
            game.onPickUpItem()
        self.assertEqual(game.grid[chestSpot][0], CHEST)


class KeepingTests(unittest.TestCase):
    """Saving, and floors that go away."""

    def test_saving_and_loading_on_a_works_floor(self):
        game = cityGame()
        spot = shaftSpot(game, "mine")
        climbDown(game, "mine")
        mineType = game.proportion
        path = os.path.join(tempfile.mkdtemp(), "save.pkl")
        gamemanager.gameManager.saveGame(game, path)  # (cityGame turns saving off)
        loaded = support.newGame()
        self.assertTrue(loaded.loadGame(path))
        self.assertEqual(loaded.sideFloor, ("mine", spot))
        self.assertEqual(loaded.proportion, mineType)
        loaded.onEnter()  # still on the shaft: up to the city
        self.assertEqual(loaded.proportion, metropolis.METROPOLIS)

    def test_a_station_set_up_on_a_works_floor_is_elsewhere_in_the_city(self):
        game = cityGame()
        climbDown(game, "mine")
        game.player.stations.add("smelter")
        game.player.stationPlaced["smelter"] = (mineshafts.floorKey(game), support.openTile(game))
        game.onEnter()
        self.assertEqual(game.stationState("smelter"), "elsewhere")
        game.onEnter()
        self.assertNotEqual(game.stationState("smelter"), "elsewhere")

    def test_works_floors_below_a_dropped_floor_go_too(self):
        game = cityGame()
        climbDown(game, "mine")
        game.onEnter()
        self.assertTrue(game.floorsAside)
        game.dropFloorsBelow(game.level - 1)
        self.assertEqual(game.floorsAside, {})


if __name__ == "__main__":
    unittest.main()
