"""The Dwellers at work on their city's works floors (dwellerwork.py): miners breaking seams, farmers tending crops
and Dew Grubs, and everything they get taken to the storehouse chests."""
import random
import unittest
from unittest import mock

from cruel.entities import enemies
from cruel.graphics import sprites
from cruel.inventory import items
from cruel.inventory import loot
from cruel.inventory import resources
from cruel.world import cityshops
from cruel.world import dwellerbuilding
from cruel.world import dwellerfarming
from cruel.world import dwellers
from cruel.world import dwellerwork
from cruel.world import expansion
from cruel.world import metropolis
from cruel.world import mineshafts
from cruel.world import plants
from cruel.world import wall
from tests import support
from tests.test_expansion import blankFloor
from tests.test_mineshafts import cityGame, climbDown

FLOOR, WALL, CHEST, ENEMY, PLANT = 0, 2, 3, 5, 8


class WorkTest(unittest.TestCase):
    """An open floor with you far off in the top-left corner; walls, chests and workers placed by each test."""

    def setUp(self):
        random.seed(5)
        self.game = support.newGame()
        blankFloor(self.game)
        self.rowLength = self.game.rowLength

    def spot(self, column, row):
        return column + row * self.rowLength

    def worker(self, column, row, work="mine"):
        worker = enemies.DwellerCitizen()
        worker.work = work
        worker.home = self.spot(column, row)
        self.game.grid[self.spot(column, row)] = [ENEMY, 1, worker]
        self.game.EnemyPositions.add(self.spot(column, row))
        return worker

    def storageChest(self, column, row):
        chest = items.StorageChest()
        self.game.grid[self.spot(column, row)] = [CHEST, 1, chest]
        return chest

    def wallAt(self, column, row, kind=wall.StoneWall):
        self.game.grid[self.spot(column, row)] = [WALL, 1, kind()]
        return self.game.grid[self.spot(column, row)][2]

    def positionOf(self, unit):
        return next(spot for spot in self.game.EnemyPositions if self.game.grid[spot][2] is unit)

    def runTurns(self, count, until):
        for _ in range(count):
            self.game.enemyTurn()
            if until():
                return True
        return False


class MinerTests(WorkTest):
    def test_a_miner_breaks_the_seam_beside_it_and_pockets_the_ore(self):
        miner = self.worker(40, 30)
        self.wallAt(41, 30, wall.IronVein)
        self.storageChest(10, 60)
        with mock.patch.object(dwellers, "IDLE_CHANCE", 0):
            self.assertTrue(self.runTurns(20, until=lambda: self.game.grid[self.spot(41, 30)][0] == FLOOR))
        self.assertIn("iron_ore", dwellerwork.carrying(miner))

    def test_a_swing_takes_off_no_more_than_the_walls_hardness(self):
        miner = self.worker(40, 30)
        seam = self.wallAt(41, 30, wall.GoldWall)
        seam.hardness = dwellerwork.MINE_SWING - 2
        startingHp = seam.hp
        dwellerwork.swing(self.game, self.spot(41, 30), miner)
        self.assertEqual(seam.hp, startingHp - seam.hardness)

    def test_it_goes_to_the_nearest_seam_it_can_reach(self):
        miner = self.worker(40, 30)
        self.wallAt(50, 30, wall.CopperVein)
        self.wallAt(46, 30, wall.IronVein)
        self.assertEqual(dwellerwork.pickSeam(self.game, self.spot(40, 30), miner), self.spot(46, 30))

    def test_gold_walls_are_seams_too(self):
        self.assertTrue(dwellerwork.isSeam([WALL, 1, wall.GoldWall()]))
        self.assertFalse(dwellerwork.isSeam([WALL, 1, wall.StoneWall()]))

    def test_with_no_seam_in_reach_it_tunnels_toward_the_nearest(self):
        miner = self.worker(40, 30)
        for row in range(0, 80):  # a wall of rock between it and the seam
            if self.spot(44, row) in self.game.grid:
                self.wallAt(44, row)
        self.wallAt(60, 30, wall.SilverVein)
        self.assertEqual(dwellerwork.pickSeam(self.game, self.spot(40, 30), miner), self.spot(44, 30))

    def test_it_never_breaks_the_citys_walls(self):
        miner = self.worker(40, 30)
        for column in range(38, 43):  # shut in a storehouse, with a seam outside it
            for row in range(28, 33):
                if max(abs(column - 40), abs(row - 30)) == 2:
                    self.wallAt(column, row, wall.ShopWall)
        self.wallAt(50, 30, wall.IronVein)
        self.assertIsNone(dwellerwork.pickSeam(self.game, self.spot(40, 30), miner))

    def test_it_never_breaks_a_wall_a_lamp_hangs_on(self):
        game = self.game
        miner = self.worker(40, 30)
        self.wallAt(40, 31, wall.IronVein)
        game.sideFloor = ("mine", 0)  # (a works floor: it has lamps)
        game.wallLamps = {game.level: {self.spot(40, 30): metropolis.WallLamp("down", 3)}}  # hung on the vein
        self.assertIsNone(dwellerwork.pickSeam(game, self.spot(40, 30), miner))

    def test_two_miners_do_not_work_the_same_seam(self):
        first, second = self.worker(40, 30), self.worker(40, 32)
        self.wallAt(41, 31, wall.IronVein)
        self.wallAt(48, 31, wall.CopperVein)
        first.target = self.spot(41, 31)
        self.assertEqual(dwellerwork.pickSeam(self.game, self.spot(40, 32), second), self.spot(48, 31))


class HaulingTests(WorkTest):
    def test_a_worker_carrying_something_takes_it_to_the_nearest_storage_chest(self):
        miner = self.worker(40, 30)
        miner.materials = {"iron_ore": 3, "gold": 1}
        chest = self.storageChest(46, 30)
        self.storageChest(80, 60)
        with mock.patch.object(dwellers, "IDLE_CHANCE", 0):
            self.assertTrue(self.runTurns(20, until=lambda: not dwellerwork.carrying(miner)))
        self.assertEqual({stack.materialId: stack.amount for stack in chest}, {"iron_ore": 3, "gold": 1})

    def test_it_adds_to_a_stack_of_the_same_thing_up_to_the_limit(self):
        chest = items.StorageChest()
        dwellerwork.putInChest(chest, {"coal": 5})
        dwellerwork.putInChest(chest, {"coal": 4, "stone": 2})
        self.assertEqual([(stack.materialId, stack.amount) for stack in chest], [("coal", 9), ("stone", 2)])
        dwellerwork.putInChest(chest, {"coal": dwellerwork.STACK_LIMIT})
        self.assertEqual(chest[0].amount, dwellerwork.STACK_LIMIT)

    def test_killing_a_worker_gets_you_a_share_of_what_it_carried(self):
        game = self.game
        miner = self.worker(40, 30)
        miner.materials = {"iron_ore": 20}
        game.player.attributes["wisdom"] = 30  # (all of it)
        game.killEnemy(self.spot(40, 30), "player")
        self.assertGreater(game.player.materials.get("iron_ore", 0), 0)


class MineFloorTests(unittest.TestCase):
    def test_a_mine_fills_its_storage_chests_with_ore(self):
        random.seed(3)
        game = cityGame()
        climbDown(game, "mine")
        for _ in range(150):
            game.enemyTurn()
        stored = [stack for spot in dwellerwork.storageChests(game) for stack in game.grid[spot][2]]
        self.assertTrue(any(isinstance(stack, resources.MaterialStack) and stack.materialId != "stone" for stack in stored))

    def test_taking_from_a_storage_chest_is_stealing(self):
        game = cityGame()
        climbDown(game, "mine")
        chestSpot = dwellerwork.storageChests(game)[0]
        game.PlayerLookPosition = chestSpot
        with mock.patch.object(dwellers, "hostileAct") as hostileAct:
            game.tookFromChest()
        hostileAct.assert_called_once_with(game, chestSpot)

    def test_a_worker_that_sees_trouble_stops_working_to_deal_with_it(self):
        game = cityGame()
        climbDown(game, "mine")
        spot, worker = next((spot, game.grid[spot][2]) for spot in game.EnemyPositions if dwellerwork.isWorker(game.grid[spot][2]))
        dwellers.turnHostile(game, worker, game.playerPositionFlat)
        with mock.patch.object(dwellerwork, "workTurn") as workTurn:
            game.grid[spot].pop()
            dwellers.takeTurn(game, spot, worker)
        workTurn.assert_not_called()



class FarmTest(WorkTest):
    """A pen with a Dew Grub in it, on the open floor; fields placed by each test."""

    def setUp(self):
        super().setUp()
        self.penInside = {self.spot(column, row) for column in range(41, 46) for row in range(31, 35)}
        for column in range(40, 47):
            for row in range(30, 36):
                if self.spot(column, row) not in self.penInside and (column, row) != (43, 30):  # (43, 30): the gate
                    self.wallAt(column, row, wall.PenFence)
        self.grub = enemies.DewGrub()
        self.grub.pen = frozenset(self.penInside)
        self.game.grid[self.spot(43, 33)] = [ENEMY, 1, self.grub]
        self.game.EnemyPositions.add(self.spot(43, 33))
        self.fields = {}

    def crop(self, column, row, kind="bloodcap", stage="harvest"):
        crop = plants.Plant(kind, planted=True)
        crop.stage, crop.timer, crop.cityCrop = stage, 0, True
        self.game.grid[self.spot(column, row)] = [PLANT, 1, crop]
        self.fields[self.spot(column, row)] = kind
        return crop

    def farmer(self, column, row):
        farmer = self.worker(column, row, work="farm")
        farmer.fields = self.fields
        return farmer


class FarmerTests(FarmTest):
    def test_a_farmer_picks_a_ripe_crop_and_keeps_what_it_gives(self):
        farmer = self.farmer(30, 20)
        self.crop(31, 20)
        with mock.patch.object(dwellerfarming, "shortOfSeeds", return_value=False):
            dwellerwork.workTurn(self.game, self.spot(30, 20), farmer)
        self.assertGreater(dwellerwork.carrying(farmer).get("bloodcap", 0), 0, "its herb")
        self.assertEqual(self.game.grid[self.spot(31, 20)][0], FLOOR, "picking uses the crop up")

    def test_short_of_seeds_it_leaves_a_crop_ready_to_harvest_to_go_to_seed(self):
        farmer = self.farmer(30, 20)
        self.crop(31, 20, stage="harvest")  # (a bloodcap's first ripe stage: its seed stage comes next)
        dwellerwork.workTurn(self.game, self.spot(30, 20), farmer)
        self.assertEqual(self.game.grid[self.spot(31, 20)][0], PLANT)
        self.crop(31, 20, stage="seed")
        dwellerwork.workTurn(self.game, self.spot(30, 20), farmer)
        self.assertGreater(dwellerwork.carrying(farmer).get("bloodcap_spores", 0), 0)

    def test_it_leaves_a_crop_that_is_not_ripe(self):
        farmer = self.farmer(30, 20)
        self.crop(31, 20, stage="growing")
        dwellerwork.workTurn(self.game, self.spot(30, 20), farmer)
        self.assertEqual(dwellerwork.carrying(farmer), {})

    def test_it_sows_a_bare_field_tile_with_a_seed(self):
        farmer = self.farmer(30, 20)
        farmer.materials = {"bloodcap_spores": 2}
        self.fields[self.spot(31, 20)] = "bloodcap"  # (bare floor)
        dwellerwork.workTurn(self.game, self.spot(30, 20), farmer)
        sprout = self.game.grid[self.spot(31, 20)][2]
        self.assertEqual((sprout.stage, sprout.cityCrop, sprout.planted), ("planted", True, True))
        self.assertEqual(farmer.materials, {"bloodcap_spores": 1})

    def test_with_no_seeds_it_fetches_some_from_a_storehouse_chest(self):
        farmer = self.farmer(30, 20)
        self.fields[self.spot(31, 20)] = "bloodcap"
        chest = self.storageChest(29, 20)
        chest.append(resources.MaterialStack("bloodcap_spores", 10))
        dwellerwork.workTurn(self.game, self.spot(30, 20), farmer)
        self.assertEqual(dwellerwork.carrying(farmer), {"bloodcap_spores": dwellerfarming.SEEDS_KEPT})
        self.assertEqual(chest[0].amount, 10 - dwellerfarming.SEEDS_KEPT)

    def test_it_pulls_up_anything_wild_on_its_fields(self):
        farmer = self.farmer(30, 20)
        self.game.grid[self.spot(31, 20)] = [PLANT, 1, plants.Plant.grown("bloodcap")]
        self.fields[self.spot(31, 20)] = "bloodcap"
        dwellerwork.workTurn(self.game, self.spot(30, 20), farmer)
        self.assertEqual(self.game.grid[self.spot(31, 20)][0], FLOOR)

    def test_a_hungry_grub_is_fed_from_over_the_fence(self):
        farmer = self.farmer(43, 24)
        farmer.materials = {"bloodcap": 3}
        self.grub.hunger = dwellerfarming.HUNGRY_TURNS
        with mock.patch.object(dwellers, "IDLE_CHANCE", 0), mock.patch.object(dwellerwork, "GRUB_SHUFFLE", 0):
            self.assertTrue(self.runTurns(30, until=lambda: self.grub.feedings == 1))
        self.assertEqual(self.grub.hunger, 0)
        self.assertEqual(farmer.materials, {"bloodcap": 2})
        self.assertNotIn(self.positionOf(farmer), self.penInside, "it didn't go in")

    def test_a_grub_that_isnt_hungry_yet_is_left_be(self):
        farmer = self.farmer(43, 30)  # (in the gate: within reach of it)
        farmer.materials = {"bloodcap": 3}
        self.grub.hunger = 10  # (fed from 50 turns unfed)
        dwellerfarming.keeperTurn(self.game, self.spot(43, 30), farmer)
        self.assertEqual(self.grub.feedings, 0)

    def test_with_no_food_it_fetches_some_for_a_hungry_grub(self):
        farmer = self.farmer(30, 26)
        chest = self.storageChest(29, 26)
        chest.append(resources.MaterialStack("bloodcap", 30))
        self.grub.hunger = dwellerfarming.HUNGRY_TURNS
        dwellerwork.workTurn(self.game, self.spot(30, 26), farmer)
        self.assertEqual(dwellerfarming.foodCarried(farmer), dwellerfarming.FOOD_KEPT)

    def test_after_enough_feedings_a_grub_has_dew_and_eats_no_more(self):
        farmer = enemies.DwellerCitizen()
        farmer.materials = {"bloodcap": 10}
        for _ in range(dwellerwork.FEEDINGS_FOR_DEW):
            dwellerwork.feed(self.grub, farmer)
        self.assertTrue(self.grub.dewReady)
        self.assertEqual(dwellers.attitudeLabel(self.grub), "livestock, Dew ready")
        hungry = [spot for spot, grub in dwellerwork.grubsHere(self.game) if not grub.dewReady]
        self.assertEqual(hungry, [])

    def test_a_farmer_collects_the_dew_and_takes_it_to_the_storehouse(self):
        self.grub.dewReady = True
        chest = self.storageChest(30, 26)
        self.farmer(43, 27)
        with mock.patch.object(dwellers, "IDLE_CHANCE", 0), mock.patch.object(dwellerwork, "GRUB_SHUFFLE", 0):
            self.assertTrue(self.runTurns(60, until=lambda: any(stack.materialId == "dew" for stack in chest)))
        self.assertFalse(self.grub.dewReady)


class StarvingTests(FarmTest):
    def test_a_grub_gets_hungrier_every_turn_and_starves_unfed(self):
        game = self.game
        dwellerfarming.starveTurn(game)
        self.assertEqual(self.grub.hunger, 1)
        self.grub.hunger = 98
        dwellerfarming.starveTurn(game)
        self.assertIn(self.grub, [grub for _, grub in dwellerwork.grubsHere(game)], "99 turns unfed: still alive")
        dwellerfarming.starveTurn(game)
        self.assertNotIn(self.grub, [grub for _, grub in dwellerwork.grubsHere(game)], "100 turns unfed: starved")

    def test_waiting_with_dew_it_does_not_get_hungrier(self):
        self.grub.dewReady = True
        self.grub.hunger = dwellerfarming.STARVE_TURNS - 1
        dwellerfarming.starveTurn(self.game)
        self.assertEqual(self.grub.hunger, dwellerfarming.STARVE_TURNS - 1)

    def test_feeding_it_takes_its_hunger_away(self):
        self.grub.hunger = 70
        farmer = enemies.DwellerCitizen()
        farmer.materials = {"bloodcap": 1}
        self.assertTrue(dwellerwork.feed(self.grub, farmer))
        self.assertEqual(self.grub.hunger, 0)
        self.assertFalse(dwellerwork.feed(self.grub, farmer), "no food left")

    def test_grubs_only_go_hungry_on_a_works_floor(self):
        game = self.game
        game.enemyTurn()
        self.assertEqual(self.grub.hunger, 0)
        game.sideFloor = ("farm", 0)
        game.enemyTurn()
        self.assertEqual(self.grub.hunger, 1)


class FarmRoleTests(FarmTest):
    def test_keepers_never_build_and_growers_do(self):
        keeper, grower = self.farmer(30, 20), self.farmer(32, 20)
        keeper.farmRole, grower.farmRole = "keeper", "grower"
        keeper.plans = grower.plans = [{"kind": "pen"}]
        self.assertIsNone(dwellerbuilding.planFor(self.game, keeper))
        self.assertIsNotNone(dwellerbuilding.planFor(self.game, grower))

    def test_keepers_share_the_pens_out_between_them(self):
        keepers = [self.farmer(30, 20), self.farmer(32, 20)]
        pens = [{"inside": frozenset({index}), "fence": set(), "gate": index} for index in range(5)]
        for keeper in keepers:
            keeper.farmRole, keeper.pens = "keeper", pens
        shares = [dwellerfarming.keeperPens(self.game, keeper) for keeper in keepers]
        self.assertEqual(sorted(len(share) for share in shares), [2, 3])
        self.assertEqual(sum(shares, []), [pen for pen in pens if pen in shares[0]] + [pen for pen in pens if pen in shares[1]])
        self.game.killEnemy(self.spot(32, 20), "player")  # one gone: the other has them all
        self.assertEqual(len(dwellerfarming.keeperPens(self.game, keepers[0])), 5)

    def test_growers_share_the_crops_and_split_a_crop_they_share(self):
        growers = [self.farmer(30, 20), self.farmer(32, 20), self.farmer(34, 20)]
        for grower in growers:
            grower.farmRole = "grower"
        for column in range(10, 20):
            self.fields[self.spot(column, 5)] = "bloodcap"
        self.fields[self.spot(10, 8)] = "glowcap"
        shares = [dwellerfarming.myFields(self.game, grower) for grower in growers]
        self.assertEqual(sum(len(share) for share in shares), len(self.fields), "every tile is someone's")
        self.assertEqual(len(set().union(*shares)), len(self.fields), "and only one grower's")

    def test_a_grower_keeps_its_seeds_and_takes_in_its_herbs_a_keeper_keeps_food(self):
        grower, keeper = self.farmer(30, 20), self.farmer(32, 20)
        grower.farmRole, keeper.farmRole = "grower", "keeper"
        grower.materials = {"bloodcap": 9, "bloodcap_spores": 6}
        keeper.materials = {"bloodcap": 25, "dew": 1}
        self.assertEqual(dwellerfarming.toStore(grower), {"bloodcap": 9, "bloodcap_spores": 6 - dwellerfarming.SEEDS_KEPT})
        self.assertEqual(dwellerfarming.toStore(keeper), {"bloodcap": 25 - dwellerfarming.FOOD_KEPT, "dew": 1})

    def test_nothing_wild_sprouts_on_the_fields(self):
        game = self.game
        self.fields[self.spot(31, 20)] = "bloodcap"
        self.farmer(30, 20)
        game.sideFloor = ("farm", 0)
        self.assertIn(self.spot(31, 20), dwellerfarming.fieldTiles(game))
        for column, row in ((30, 21), (32, 21), (31, 21)):  # seeding bloodcaps all round it
            crop = plants.Plant.grown("bloodcap")
            crop.stage = "seed"
            game.grid[self.spot(column, row)] = [PLANT, 1, crop]
        with mock.patch.object(plants, "BIRTH_CHANCE", {3: 1, 2: 1, 1: 1}):
            for _ in range(plants.GROW_TURNS * 3):
                game.turnCount += 1
                game.enemyTurn()
        self.assertNotEqual(game.grid[self.spot(31, 20)][0], PLANT)

    def test_more_field_is_wanted_while_it_is_small_for_the_herd_and_the_growers(self):
        farmer = self.farmer(30, 20)
        farmer.farmRole = "grower"
        self.fields[self.spot(20, 10)] = "bloodcap"
        self.assertTrue(dwellerfarming.needsMoreField(self.game, farmer, grubCount=5))
        self.assertFalse(dwellerfarming.needsMoreField(self.game, farmer, grubCount=0), "no grubs to feed")
        for column in range(dwellerfarming.FIELD_TILES_PER_GROWER):
            self.fields[self.spot(column, 12)] = "bloodcap"
        self.assertFalse(dwellerfarming.needsMoreField(self.game, farmer, grubCount=100), "all one grower can tend")


class GrubTests(FarmTest):
    def test_a_grub_shuffles_about_its_pen(self):
        start = self.positionOf(self.grub)
        with mock.patch.object(dwellerwork, "GRUB_SHUFFLE", 1):
            self.assertTrue(self.runTurns(10, until=lambda: self.positionOf(self.grub) != start))
            for _ in range(40):
                self.game.enemyTurn()
                self.assertIn(self.positionOf(self.grub), self.penInside)

    def test_a_grub_never_steps_out_of_its_gate(self):
        game = self.game
        game.grid[self.spot(43, 33)] = [FLOOR, 1]
        game.EnemyPositions.clear()
        beside = self.spot(43, 31)  # just inside the gate, the other tiles round it taken by grubs
        for column, row in ((42, 31), (44, 31), (43, 32)):
            game.grid[self.spot(column, row)] = [ENEMY, 1, enemies.DewGrub()]
        game.grid[beside] = [ENEMY, 1, self.grub]
        with mock.patch.object(dwellerwork, "GRUB_SHUFFLE", 1):
            game.grid[beside].pop()
            self.assertEqual(dwellerwork.grubTurn(game, beside, self.grub), beside)

    def test_a_grub_never_fights_and_the_guards_leave_it_be(self):
        self.assertEqual(self.grub.damage, 0)
        self.assertFalse(dwellers.isCityEnemy(self.grub))

    def test_hurting_a_grub_is_hostile(self):
        game = self.game
        game.sideFloor = ("farm", 0)  # (on a farm floor)
        game.playerHurtEnemy(self.grub, self.spot(43, 33))
        self.assertTrue(self.grub.hostile)

    def test_a_grub_drops_meat_and_sometimes_dew(self):
        drops = {materialId for materialId, _, _ in loot.ENEMY_LOOT["Dew Grub"]}
        self.assertEqual(drops, {"meat", "dew"})


class CityCropTests(FarmTest):
    def test_picking_a_city_crop_is_stealing(self):
        game = self.game
        self.crop(20, 20)
        with mock.patch.object(dwellers, "hostileAct") as hostileAct:
            game.harvestPlant(self.spot(20, 20))
        hostileAct.assert_called_once_with(game, self.spot(20, 20))

    def test_picking_a_wild_plant_is_not(self):
        game = self.game
        game.grid[self.spot(20, 20)] = [PLANT, 1, plants.Plant.grown("bloodcap")]
        with mock.patch.object(dwellers, "hostileAct") as hostileAct:
            game.harvestPlant(self.spot(20, 20))
        hostileAct.assert_not_called()

    def test_looking_at_one_says_whose_it_is(self):
        game = self.game
        self.crop(20, 20)
        game.PlayerLookPosition = self.spot(20, 20)
        self.assertIn("Dweller crop", game.lookingAt())


class DewTests(unittest.TestCase):
    def test_dew_is_a_material_the_grocer_deals_in(self):
        self.assertEqual(resources.materialName("dew"), "Dew")
        self.assertIn("dew", cityshops.SHOP_KINDS["food"]["materials"])

    def test_the_grub_has_a_picture(self):
        self.assertIn("Dew Grub", sprites.ENEMY_SPRITES)


class FarmFloorTests(unittest.TestCase):
    def setUp(self):
        random.seed(3)
        self.game = cityGame()
        climbDown(self.game, "farm")

    def test_pens_of_grubs_and_fields_of_crops(self):
        grubs = dwellerwork.grubsHere(self.game)
        self.assertGreaterEqual(len(grubs), mineshafts.PENS[0] * mineshafts.GRUBS_PER_PEN[0])
        crops = [tile[2] for tile in self.game.grid.values() if tile[0] == PLANT and getattr(tile[2], "cityCrop", False)]
        self.assertGreater(len(crops), 5)
        farmers = [self.game.grid[spot][2] for spot in self.game.EnemyPositions
                   if getattr(self.game.grid[spot][2], "work", None) == "farm"]
        self.assertTrue(farmers)
        self.assertTrue(all(farmer.fields is farmers[0].fields for farmer in farmers), "one set of fields for the farm")

    def test_every_pen_can_be_walked_into_from_the_shaft(self):
        reach = expansion.walkingDistances(self.game, self.game.playerPositionFlat, 200)
        for spot, grub in dwellerwork.grubsHere(self.game):
            self.assertTrue(any(tile in reach for tile in grub.pen))

    def test_a_farm_makes_dew(self):
        for _ in range(500):
            self.game.enemyTurn()
        dew = sum(stack.amount for spot in dwellerwork.storageChests(self.game) for stack in self.game.grid[spot][2]
                  if stack.materialId == "dew")
        self.assertGreater(dew, 0)


if __name__ == "__main__":
    unittest.main()
