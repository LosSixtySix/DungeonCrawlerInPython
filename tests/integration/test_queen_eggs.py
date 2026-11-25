"""The Queen's eggs in a running city (queen.py): hatcheries and their nests, laying, citizens carrying eggs to the
nests, hatching into what the city needs, and hatchlings going to their work.

Integration tests; the rest are in tests/unit/test_queen.py, tests/acceptance/test_queen.py."""
import random
import unittest
from unittest import mock

from cruel.entities import enemies
from cruel.inventory import items
from cruel.world import dewgrubs
from cruel.world import dwellers
from cruel.world import dwellerwork
from cruel.world import livingfloors
from cruel.world import metropolis
from cruel.world import occupancy
from cruel.world import queen
from tests.helpers.metropolis import cityGame
from tests.support import newGame

FLOOR, CHEST, ENEMY = 0, 3, 5


class HatcheryTests(unittest.TestCase):
    def test_every_city_has_hatcheries_with_nests_apart_from_each_other_and_the_doors(self):
        game = newGame()
        rowLength, rowCount = game.rowLength, game.numberOfSpots // game.rowLength
        for seed in range(6):
            random.seed(seed)
            city = metropolis.buildCity(rowLength, rowCount, rowLength * (rowCount // 2) + rowLength // 2,
                                        metropolis.BUILDING_STYLES[seed % len(metropolis.BUILDING_STYLES)])
            self.assertEqual(len(city.hatcheries), metropolis.HATCHERIES, f"seed {seed}")
            for hatchery in city.hatcheries:
                self.assertTrue(0 < len(hatchery.nests) <= metropolis.NESTS)
                for nest in hatchery.nests:
                    self.assertIn(nest, hatchery.inside)
                    self.assertFalse(set(metropolis.neighborsOf(city, nest)) & set(hatchery.doors))
                    for other in hatchery.nests:
                        if other != nest:
                            self.assertGreater(max(abs(nest % rowLength - other % rowLength),
                                                   abs(nest // rowLength - other // rowLength)), 1)
            court = city.queen.court
            self.assertEqual(court["nests"], [nest for hatchery in city.hatcheries for nest in hatchery.nests])
            self.assertEqual(court["posts"], city.posts)
            self.assertEqual(court["wanted"]["guard"], len(city.posts))


class EggTest(unittest.TestCase):
    def setUp(self):
        random.seed(4)
        self.game = cityGame()
        self.anchor, self.queen = queen.courtOf(self.game)

    def eggs(self):
        return [(spot, unit) for spot, unit in dwellers.cityDwellers(self.game) if queen.isEgg(unit)]

    def runTurns(self, count, until):
        for _ in range(count):
            self.game.enemyTurn()
            if until():
                return True
        return False


class LayingTests(EggTest):
    def test_fed_enough_dew_she_lays_a_clutch_touching_her(self):
        game = self.game
        self.queen.dew = queen.DEW_TO_LAY + 3
        self.assertEqual(queen.layEggs(game, self.anchor, self.queen), queen.CLUTCH)
        self.assertEqual(self.queen.dew, 3)
        eggs = self.eggs()
        self.assertEqual(len(eggs), queen.CLUTCH)
        for spot, egg in eggs:
            self.assertEqual(game.reachOf(self.queen, self.anchor, spot), 1)
            self.assertIs(egg.court, self.queen.court)

    def test_not_before(self):
        self.queen.dew = queen.DEW_TO_LAY - 1
        self.assertEqual(queen.layEggs(self.game, self.anchor, self.queen), 0)
        self.assertEqual(self.eggs(), [])

    def test_with_no_room_round_her_she_waits(self):
        game = self.game
        for tile in game.footprint(self.anchor, 2):
            for spot in game.neighbors(tile):
                if game.grid[spot][0] == FLOOR:
                    dewgrubs.placeUnit(game, spot, enemies.DwellerNoble())
        self.queen.dew = queen.DEW_TO_LAY
        self.assertEqual(queen.layEggs(game, self.anchor, self.queen), 0)
        self.assertEqual(self.queen.dew, queen.DEW_TO_LAY)


class CarryingTests(EggTest):
    def test_citizens_carry_each_egg_to_a_nest_where_it_starts_to_hatch(self):
        self.queen.dew = queen.DEW_TO_LAY
        with mock.patch.object(dwellers, "IDLE_CHANCE", 0), mock.patch.object(queen, "HATCH_TURNS", 10 ** 6):
            self.assertTrue(self.runTurns(400, until=lambda: len(self.eggs()) == queen.CLUTCH
                                          and all(egg.nest == spot for spot, egg in self.eggs())))
        nests = self.queen.court["nests"]
        for spot, egg in self.eggs():
            self.assertIn(spot, nests)
            self.assertIsNotNone(egg.hatchIn)

    def test_with_every_nest_taken_eggs_wait_where_they_were_laid(self):
        game = self.game
        for nest in self.queen.court["nests"]:  # (eggs already in every nest, a long way from hatching)
            if game.grid[nest][0] == FLOOR:
                nested = enemies.DwellerEgg(self.queen.court)
                nested.nest, nested.hatchIn = nest, 10 ** 6
                dewgrubs.placeUnit(game, nest, nested)
        self.queen.dew = queen.DEW_TO_LAY
        with mock.patch.object(dwellers, "IDLE_CHANCE", 0):
            self.runTurns(60, until=lambda: False)
        waiting = queen.waitingEggs(game)
        self.assertEqual(len(waiting), queen.CLUTCH)
        self.assertTrue(all(game.reachOf(self.queen, self.anchor, spot) == 1 for spot, _ in waiting))
        self.assertEqual(queen.heldEggs(game), [])

    def test_a_citizen_killed_carrying_an_egg_drops_it(self):
        game = self.game
        self.queen.dew = queen.DEW_TO_LAY
        with mock.patch.object(dwellers, "IDLE_CHANCE", 0):
            self.assertTrue(self.runTurns(200, until=lambda: queen.heldEggs(game)))
        carrier, egg = queen.heldEggs(game)[0]
        where = next(spot for spot, unit in dwellers.cityDwellers(game) if unit is carrier)
        game.killEnemy(where, killer=None, unit=carrier)
        found = [spot for spot, unit in dwellers.cityDwellers(game) if unit is egg]
        self.assertEqual(len(found), 1)
        self.assertLessEqual(dwellers.distance(game, found[0], where), 1)
        self.assertIsNone(egg.nestTarget)


class HatchingTests(EggTest):
    def eggInNest(self, hatchIn=1):
        game = self.game
        nest = next(nest for nest in self.queen.court["nests"] if game.grid[nest][0] == FLOOR)
        egg = enemies.DwellerEgg(self.queen.court)
        egg.nest, egg.hatchIn = nest, hatchIn
        dewgrubs.placeUnit(game, nest, egg)
        return nest, egg

    def hatchAs(self, kind):
        game = self.game
        nest, egg = self.eggInNest()
        with mock.patch.object(queen, "neediest", lambda game, court: kind):
            game.enemyTurn()
        return nest, next(unit for spot, unit in dwellers.cityDwellers(game) if spot == nest or unit not in self.before)

    def setUp(self):
        super().setUp()
        self.before = [unit for _, unit in dwellers.cityDwellers(self.game)]

    def test_in_its_nest_an_egg_hatches_after_its_time(self):
        game = self.game
        nest, egg = self.eggInNest(hatchIn=3)
        game.enemyTurn()
        game.enemyTurn()
        self.assertIn(egg, [unit for _, unit in dwellers.cityDwellers(game)])
        game.enemyTurn()
        self.assertNotIn(egg, [unit for _, unit in dwellers.cityDwellers(game)])

    def test_an_egg_out_of_a_nest_never_hatches(self):
        game = self.game
        egg = enemies.DwellerEgg(self.queen.court)
        egg.hatchIn = 1
        spot = next(spot for spot in game.neighbors(self.queen.court["nests"][0]) if game.grid[spot][0] == FLOOR)
        dewgrubs.placeUnit(game, spot, egg)
        with mock.patch.object(dwellers, "IDLE_CHANCE", 1):  # (and nobody carries it off)
            for _ in range(3):
                queen.takeTurn(game, spot, egg)
        self.assertEqual(egg.hatchIn, 1)

    def test_a_guard_goes_to_the_post_with_fewest_guards(self):
        game = self.game
        guarded = [unit.home for _, unit in dwellers.cityDwellers(game) if queen.jobOf(unit) == "guard"]
        _, guard = self.hatchAs("guard")
        self.assertIsInstance(guard, enemies.DwellerGuard)
        self.assertIn(guard.home, self.queen.court["posts"])
        self.assertEqual(guarded.count(guard.home), min(guarded.count(post) for post in self.queen.court["posts"]))

    def test_a_carrier_or_citizen_gets_a_house(self):
        _, carrier = self.hatchAs("carrier")
        self.assertEqual((carrier.role, carrier.work), ("citizen", "dew"))
        self.assertIn(carrier.home, self.queen.court["homes"])

    def test_a_miner_walks_down_the_mine_shaft_and_joins_the_workers_there(self):
        game = self.game
        _, miner = self.hatchAs("miner")
        self.assertEqual((miner.joining, miner.work), ("mine", None))
        mineShaft = queen.shaftsHere(game, "mine")[0]
        mineKey = (game.level, mineShaft)
        with mock.patch.object(dwellers, "IDLE_CHANCE", 0):
            for _ in range(300):
                game.enemyTurn()
                if miner.work == "mine":
                    break
        self.assertEqual((miner.work, miner.joining), ("mine", None))
        with livingfloors.awayFloor(game, mineKey):
            workers = [unit for _, unit in dwellers.cityDwellers(game) if unit.work == "mine"]
            self.assertIn(miner, workers)
            self.assertIs(miner.plans, next(unit for unit in workers if unit is not miner).plans)

    def test_a_farmer_keeps_grubs_or_grows_crops_whichever_there_are_fewer_of(self):
        game = self.game
        game.enemyTurn()  # (the city's works floors are made on its first turn)
        farmKey = (game.level, queen.shaftsHere(game, "farm")[0])
        with livingfloors.awayFloor(game, farmKey):
            workers = [unit for _, unit in dwellers.cityDwellers(game) if unit.work == "farm"]
            for everyone, expected in (("keeper", "grower"), ("grower", "keeper")):
                for worker in workers:
                    worker.farmRole = everyone
                hatchling = enemies.DwellerCitizen()
                hatchling.joining = "farm"
                queen.joinWorks(game, game.sideFloor[1], hatchling)
                self.assertEqual(hatchling.farmRole, expected)
                self.assertIs(hatchling.fields, workers[0].fields)
                self.assertIs(hatchling.pens, workers[0].pens)


class CensusTests(EggTest):
    def test_the_city_counts_its_works_floors_from_their_census(self):
        game = self.game
        game.enemyTurn()  # (each works floor counts itself on its turn)
        records = game.workCensus
        shafts = queen.shaftsHere(game)
        self.assertEqual(set(records), {(game.level, shaft) for shaft in shafts})
        counts = queen.cityCounts(game)
        city = queen.census(game)
        self.assertEqual(counts["miner"], city["miner"] + sum(record["miner"] for record in records.values()))
        self.assertEqual(counts["guard"], city["guard"], "the works' guards are their own")

    def test_someone_on_their_way_up_or_down_counts(self):
        game = self.game
        game.enemyTurn()
        before = queen.cityCounts(game)["farmer"]
        hatchling = enemies.DwellerCitizen()
        hatchling.joining = "farm"
        livingfloors.arrivals(game)[(game.level, queen.shaftsHere(game, "farm")[0])] = [(hatchling, 0)]
        self.assertEqual(queen.cityCounts(game)["farmer"], before + 1)


class StorageChestCacheTests(unittest.TestCase):
    def test_a_chest_destroyed_during_the_turn_is_left_out_at_once(self):
        game = newGame()
        spots = [spot for spot, tile in game.grid.items() if tile[0] == FLOOR][:2]
        for spot in spots:
            game.grid[spot] = [CHEST, 1, items.StorageChest()]
        self.assertTrue(set(spots) <= set(dwellerwork.storageChests(game)))
        game.grid[spots[0]] = [FLOOR, 1]
        self.assertNotIn(spots[0], dwellerwork.storageChests(game))
        self.assertIn(spots[1], dwellerwork.storageChests(game))


if __name__ == "__main__":
    unittest.main()
