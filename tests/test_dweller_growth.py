"""The Dwellers' works floors growing: young Dew Grubs, farmers moving grubs between pens and building new pens
(dewgrubs.py), and new storehouses when the chests are full (dwellerbuilding.py)."""
import random
import unittest
from unittest import mock

from cruel.entities import enemies
from cruel.graphics import sprites
from cruel.inventory import items
from cruel.inventory import loot
from cruel.inventory import resources
from cruel.world import dewgrubs
from cruel.world import dwellerbuilding
from cruel.world import dwellerfarming
from cruel.world import dwellers
from cruel.world import dwellerwork
from cruel.world import mineshafts
from cruel.world import wall
from tests import support
from tests.test_dweller_work import WorkTest
from tests.test_mineshafts import cityGame, climbDown

FLOOR, WALL, CHEST, ENEMY, PLANT = 0, 2, 3, 5, 8


class PenTest(WorkTest):
    """An open floor where each test fences pens (PEN_WIDTH x PEN_HEIGHT, the gate in the middle of the top side)
    and puts grubs and farmers in them."""

    def setUp(self):
        super().setUp()
        self.pens = []
        self.plans = []

    def pen(self, left, top):
        inside = frozenset(self.spot(column, row) for column in range(left + 1, left + mineshafts.PEN_WIDTH - 1)
                           for row in range(top + 1, top + mineshafts.PEN_HEIGHT - 1))
        gate = self.spot(left + mineshafts.PEN_WIDTH // 2, top)
        fence = set()
        for column in range(left, left + mineshafts.PEN_WIDTH):
            for row in range(top, top + mineshafts.PEN_HEIGHT):
                spot = self.spot(column, row)
                if spot not in inside and spot != gate:
                    self.wallAt(column, row, wall.PenFence)
                    fence.add(spot)
        pen = {"fence": fence, "inside": inside, "gate": gate}
        self.pens.append(pen)
        return pen

    def grub(self, spot, pen, grown=True):
        grub = enemies.DewGrub(grown=grown)
        grub.pen = pen["inside"]
        self.game.grid[spot] = [ENEMY, 1, grub]
        self.game.EnemyPositions.add(spot)
        return grub

    def fill(self, pen, count, grown=True):
        """count grubs in the pen, filling it from the back."""
        spots = sorted(pen["inside"], reverse=True)[:count]
        return [self.grub(spot, pen, grown) for spot in spots]

    def farmer(self, column, row):
        farmer = self.worker(column, row, work="farm")
        farmer.fields = {}
        farmer.pens = self.pens
        farmer.plans = self.plans
        return farmer

    def foodPutBy(self, amount=100):
        """A storage chest with herbs in it (a grub only gives birth with food put by)."""
        chest = self.storageChest(10, 60)
        chest.append(resources.MaterialStack("bloodcap", amount))
        return chest

    def grubsIn(self, pen):
        return [grub for spot, grub in dwellerwork.grubsHere(self.game) if spot in pen["inside"] and grub.pen == pen["inside"]]


# ---------------------------------------------------------------- young

class YoungGrubTests(PenTest):
    def test_a_fed_grown_grub_can_give_birth_to_a_young_one_in_its_pen(self):
        self.foodPutBy()
        pen = self.pen(40, 30)
        mother = self.fill(pen, 1)[0]
        motherSpot = self.positionOf(mother)
        with mock.patch.object(dewgrubs, "BIRTH_CHANCE", 1):
            youngSpot = dewgrubs.maybeGiveBirth(self.game, motherSpot, mother, self.pens)
        self.assertIn(youngSpot, pen["inside"])
        young = self.game.grid[youngSpot][2]
        self.assertFalse(young.grown)
        self.assertEqual(young.name, "Young Dew Grub")
        self.assertEqual(young.pen, pen["inside"])
        self.assertIn(youngSpot, self.game.EnemyPositions)

    def test_no_young_without_food_put_by_for_it(self):
        pen = self.pen(40, 30)
        grubs = self.fill(pen, 2)
        chest = self.foodPutBy(14)  # (2 grubs and the young one need 5 herbs each)
        with mock.patch.object(dewgrubs, "BIRTH_CHANCE", 1):
            self.assertIsNone(dewgrubs.maybeGiveBirth(self.game, self.positionOf(grubs[0]), grubs[0], self.pens))
        chest[0].amount += 1
        with mock.patch.object(dewgrubs, "BIRTH_CHANCE", 1):
            self.assertIsNotNone(dewgrubs.maybeGiveBirth(self.game, self.positionOf(grubs[0]), grubs[0], self.pens))

    def test_a_full_pen_still_has_young_and_the_farmers_then_move_grubs_out(self):
        self.foodPutBy()
        pen = self.pen(40, 30)
        grubs = self.fill(pen, dewgrubs.PEN_MOST)
        other = self.pen(60, 30)
        with mock.patch.object(dewgrubs, "BIRTH_CHANCE", 1):
            self.assertIsNotNone(dewgrubs.maybeGiveBirth(self.game, self.positionOf(grubs[0]), grubs[0], self.pens))
        self.assertEqual(len(self.grubsIn(pen)), dewgrubs.PEN_MOST + 1, "no hard limit")
        grub, target = dewgrubs.grubToMove(self.game, self.farmer(52, 25))
        self.assertEqual((grub.pen, target), (pen["inside"], other["inside"]))

    def test_a_young_grub_has_no_young(self):
        pen = self.pen(40, 30)
        young = self.fill(pen, 1, grown=False)[0]
        with mock.patch.object(dewgrubs, "BIRTH_CHANCE", 1):
            self.assertIsNone(dewgrubs.maybeGiveBirth(self.game, self.positionOf(young), young, self.pens))

    def test_a_young_grub_makes_no_dew_until_it_grows_up_after_enough_feedings(self):
        young = enemies.DewGrub(grown=False)
        farmer = enemies.DwellerCitizen()
        farmer.materials = {"bloodcap": 100}
        for _ in range(dewgrubs.FEEDINGS_TO_GROW - 1):
            dwellerwork.feed(young, farmer)
        self.assertFalse(young.grown)
        self.assertFalse(young.dewReady)
        self.assertEqual(young.feedings, 0)
        dwellerwork.feed(young, farmer)
        self.assertTrue(young.grown)
        self.assertEqual(young.name, "Dew Grub")
        self.assertEqual(young.maxHp, enemies.DewGrub.GROWN_HP)
        for _ in range(dwellerwork.FEEDINGS_FOR_DEW):
            dwellerwork.feed(young, farmer)
        self.assertTrue(young.dewReady)

    def test_a_farmer_feeding_a_grown_grub_can_bring_a_birth(self):
        self.foodPutBy()
        pen = self.pen(40, 30)
        for grub in self.fill(pen, 2):
            grub.hunger = dwellerfarming.HUNGRY_TURNS
        farmer = self.farmer(43, 29)
        farmer.materials = {"bloodcap": 1}
        with mock.patch.object(dewgrubs, "BIRTH_CHANCE", 1), mock.patch.object(dwellers, "IDLE_CHANCE", 0), \
                mock.patch.object(dwellerwork, "GRUB_SHUFFLE", 0):
            self.assertTrue(self.runTurns(30, until=lambda: len(self.grubsIn(pen)) == 3))
        self.assertEqual(sum(1 for grub in self.grubsIn(pen) if not grub.grown), 1)

    def test_how_a_young_one_looks_and_what_it_drops(self):
        young = enemies.DewGrub(grown=False)
        self.assertEqual(dwellers.attitudeLabel(young), "livestock, young")
        self.assertIn("Young Dew Grub", sprites.ENEMY_SPRITES)
        self.assertEqual({materialId for materialId, _, _ in loot.ENEMY_LOOT["Young Dew Grub"]}, {"meat"})


# ---------------------------------------------------------------- pens

class GrubMovingTests(PenTest):
    def test_from_a_crowded_pen_to_one_with_room(self):
        crowded, roomy = self.pen(40, 30), self.pen(60, 30)
        self.fill(crowded, dewgrubs.PEN_MOST + 1)
        self.fill(roomy, 3)
        grub, target = dewgrubs.grubToMove(self.game, self.farmer(50, 25))
        self.assertEqual(grub.pen, crowded["inside"])
        self.assertEqual(target, roomy["inside"])

    def test_a_pen_with_too_few_gets_one_from_a_pen_that_can_spare_it(self):
        lonely, full = self.pen(40, 30), self.pen(60, 30)
        self.fill(lonely, 1)
        self.fill(full, 5)
        grub, target = dewgrubs.grubToMove(self.game, self.farmer(50, 25))
        self.assertEqual(grub.pen, full["inside"])
        self.assertEqual(target, lonely["inside"])

    def test_a_lone_grub_with_none_to_spare_joins_a_pen_with_some(self):
        lonely, other = self.pen(40, 30), self.pen(60, 30)
        self.fill(lonely, 1)
        self.fill(other, 2)
        grub, target = dewgrubs.grubToMove(self.game, self.farmer(50, 25))
        self.assertEqual(grub.pen, lonely["inside"])
        self.assertEqual(target, other["inside"])

    def test_a_grub_out_of_its_pen_goes_back(self):
        pen = self.pen(40, 30)
        self.fill(pen, 2)
        loose = self.grub(self.spot(50, 40), pen)
        self.assertEqual(dewgrubs.grubToMove(self.game, self.farmer(50, 25)), (loose, pen["inside"]))

    def test_pens_of_two_to_six_are_left_alone(self):
        first, second = self.pen(40, 30), self.pen(60, 30)
        self.fill(first, dewgrubs.PEN_FEWEST)
        self.fill(second, dewgrubs.PEN_MOST)
        self.assertIsNone(dewgrubs.grubToMove(self.game, self.farmer(50, 25)))

    def test_a_farmer_carries_a_grub_from_a_crowded_pen_to_one_with_room(self):
        crowded, roomy = self.pen(40, 30), self.pen(60, 30)
        self.fill(crowded, dewgrubs.PEN_MOST + 1)
        self.fill(roomy, 3)
        self.farmer(52, 27)
        with mock.patch.object(dwellers, "IDLE_CHANCE", 0), mock.patch.object(dwellerwork, "GRUB_SHUFFLE", 0):
            self.assertTrue(self.runTurns(150, until=lambda: len(self.grubsIn(roomy)) == 4))
        self.assertEqual(len(self.grubsIn(crowded)), dewgrubs.PEN_MOST)

    def test_a_grub_is_off_the_map_while_carried_and_dropped_where_its_farmer_dies(self):
        pen = self.pen(40, 30)
        grub = self.fill(pen, 1)[0]
        farmer = self.farmer(52, 27)
        farmer.movingGrub = farmer.heldGrub = dewgrubs.takeUnit(self.game, self.positionOf(grub), grub)
        self.assertNotIn(grub, [unit for _, unit in dwellerwork.grubsHere(self.game)])
        self.game.killEnemy(self.spot(52, 27), "player")
        self.assertIn(grub, [unit for _, unit in dwellerwork.grubsHere(self.game)])


class NewPenTests(PenTest):
    def test_when_every_pen_is_full_the_farmers_plan_a_new_one(self):
        pen = self.pen(40, 30)
        self.fill(pen, dewgrubs.PEN_MOST)
        farmer = self.farmer(43, 45)
        self.assertTrue(dewgrubs.needsNewPen(self.game, farmer))
        dewgrubs.herdTurn(self.game, self.spot(43, 45), farmer)
        self.assertEqual([plan["kind"] for plan in self.plans], ["pen"])

    def test_no_new_pen_while_one_has_room(self):
        pen = self.pen(40, 30)
        self.fill(pen, dewgrubs.PEN_MOST - 1)
        self.assertFalse(dewgrubs.needsNewPen(self.game, self.farmer(43, 45)))

    def test_the_farmers_build_it_and_then_move_grubs_into_it(self):
        pen = self.pen(40, 30)
        self.fill(pen, dewgrubs.PEN_MOST)
        for column in (36, 38, 50):
            self.farmer(column, 40)
        dewgrubs.herdTurn(self.game, self.spot(36, 40), self.game.grid[self.spot(36, 40)][2])
        newPen = self.plans[0]
        with mock.patch.object(dwellers, "IDLE_CHANCE", 0), mock.patch.object(dwellerwork, "GRUB_SHUFFLE", 0):
            self.assertTrue(self.runTurns(400, until=lambda: len(self.pens) == 2))
        self.assertEqual(self.plans, [])
        for spot in newPen["walls"]:
            self.assertIsInstance(self.game.grid[spot][2], wall.PenFence)
        self.assertEqual(self.game.grid[newPen["door"]][0], FLOOR, "a gate")
        self.assertEqual(self.game.grid[newPen["backDoor"]][0], FLOOR, "and a back gate")
        self.assertEqual(self.pens[-1]["backGate"], newPen["backDoor"])

    def test_a_planned_building_has_a_back_door_opposite_its_door_with_a_way_out(self):
        farmer = self.farmer(50, 40)
        for row in range(0, 80):  # a wall of rock behind where it'll go
            if self.spot(30, row) in self.game.grid:
                self.wallAt(30, row)
        site = dwellerbuilding.findSite(self.game, self.spot(50, 40), farmer, 7, 6)
        rowLength = self.game.rowLength
        door, backDoor = site["door"], site["backDoor"]
        self.assertNotIn(backDoor, site["walls"])
        self.assertTrue(door % rowLength == backDoor % rowLength or door // rowLength == backDoor // rowLength, "on opposite sides")
        self.assertGreater(dwellers.distance(self.game, door, backDoor), 4)
        for spot in site["backWay"]:
            tile = self.game.grid[spot]
            self.assertTrue(tile[0] == FLOOR or dwellerwork.mineable(tile))


# ---------------------------------------------------------------- building

class BuildingTests(PenTest):
    def test_a_site_keeps_off_fields_and_city_walls_and_its_door_can_be_reached(self):
        farmer = self.farmer(50, 40)
        for column in range(30, 70):  # a row of crops and a storehouse wall
            farmer.fields[self.spot(column, 52)] = "bloodcap"
            self.wallAt(column, 28, wall.ShopWall)
        site = dwellerbuilding.findSite(self.game, self.spot(50, 40), farmer, 7, 6)
        self.assertFalse(site["box"] & set(farmer.fields))
        for spot in site["box"] | site["margin"]:
            self.assertNotIsInstance(self.game.grid[spot][2] if len(self.game.grid[spot]) > 2 else None, wall.CityBuildingWall)
        self.assertIn(site["outside"], dwellerbuilding.expansion.walkingDistances(self.game, self.spot(50, 40), 200))

    def test_a_builder_digs_rock_on_the_site_no_more_than_its_hardness_a_swing(self):
        farmer = self.farmer(50, 40)
        rock = self.wallAt(51, 40, wall.StoneWall)
        plan = {"kind": "pen", "box": {self.spot(51, 40)}, "walls": set(), "inside": frozenset({self.spot(51, 40)}),
                "door": self.spot(51, 40), "outside": self.spot(50, 40), "chests": []}
        dwellerbuilding.build(self.game, self.spot(50, 40), farmer, plan)
        self.assertEqual(rock.hp, wall.StoneWall().hp - min(dwellerwork.MINE_SWING, rock.hardness))

    def test_walls_go_in_only_from_inside_or_the_doorway(self):
        farmer = self.farmer(50, 40)
        site = dwellerbuilding.findSite(self.game, self.spot(50, 40), farmer, 7, 6)
        for spot in site["walls"]:
            standing = dwellerbuilding.standingSpots(self.game, site, spot)
            self.assertTrue(standing, "every wall can be reached")
            self.assertTrue(set(standing) <= set(site["inside"]) | {site["door"]})


class StorehouseTests(PenTest):
    def miner(self, column, row):
        miner = self.worker(column, row)
        miner.plans = self.plans
        return miner

    def fullChest(self, column, row):
        chest = self.storageChest(column, row)
        for index in range(dwellerwork.CHEST_STACKS):
            chest.append(resources.MaterialStack(f"stone{index}", dwellerwork.STACK_LIMIT))
        return chest

    def test_a_chest_takes_new_stacks_until_it_has_its_fill(self):
        chest = items.StorageChest()
        leftOver = dwellerwork.putInChest(chest, {"coal": dwellerwork.STACK_LIMIT + 5})
        self.assertEqual([(stack.materialId, stack.amount) for stack in chest], [("coal", dwellerwork.STACK_LIMIT), ("coal", 5)])
        self.assertEqual(leftOver, {})
        leftOver = dwellerwork.putInChest(chest, {"iron_ore": dwellerwork.STACK_LIMIT * dwellerwork.CHEST_STACKS})
        self.assertEqual(len(chest), dwellerwork.CHEST_STACKS)
        self.assertEqual(leftOver, {"iron_ore": dwellerwork.STACK_LIMIT * 2})  # (the two coal stacks took two places)
        self.assertFalse(dwellerwork.hasRoomFor(chest, {"gold": 1}))
        self.assertTrue(dwellerwork.hasRoomFor(items.StorageChest(), {"gold": 1}))

    def test_with_every_chest_full_the_workers_build_a_storehouse_and_fill_it(self):
        self.fullChest(40, 30)
        miners = [self.miner(44, 34), self.miner(46, 34)]
        for miner in miners:
            miner.materials = {"iron_ore": 3}
        with mock.patch.object(dwellers, "IDLE_CHANCE", 0):
            self.assertTrue(self.runTurns(500, until=lambda: not self.plans and not any(dwellerwork.carrying(miner) for miner in miners)))
        self.assertEqual(len(dwellerwork.storageChests(self.game)), 1 + mineshafts.STOREHOUSE_CHESTS)
        stored = sum(stack.amount for spot in dwellerwork.storageChests(self.game) for stack in self.game.grid[spot][2]
                     if stack.materialId == "iron_ore")
        self.assertEqual(stored, 6)

    def test_with_nowhere_to_build_a_storehouse_what_doesnt_fit_goes_up_to_the_city(self):
        self.fullChest(40, 30)
        miner = self.miner(44, 34)
        miner.materials = {"iron_ore": 3}
        with mock.patch.object(dwellerbuilding, "findSite", return_value=None):
            dwellerwork.workTurn(self.game, self.spot(44, 34), miner)
        self.assertEqual(dwellerwork.carrying(miner), {})
        self.assertEqual(self.plans, [])


# ---------------------------------------------------------------- getting past each other

class SwappingTests(PenTest):
    def test_a_stuck_worker_swaps_past_one_that_swapped_lately(self):
        game = self.game
        other = self.worker(41, 30)
        other.swappedAt = game.turnCount
        game.movedEnemies = {self.spot(41, 30)}
        game.grid[self.spot(40, 30)] = [ENEMY, 1]  # (the mover, lifted off for its turn)
        self.assertFalse(dwellers.swapPast(game, self.spot(40, 30), self.spot(41, 30)))
        self.assertTrue(dwellers.swapPast(game, self.spot(40, 30), self.spot(41, 30), force=True))

    def test_a_grub_is_only_swapped_into_its_own_pen(self):
        game = self.game
        pen = self.pen(40, 30)
        grub = self.grub(self.spot(43, 31), pen)
        game.movedEnemies = {self.spot(43, 31)}
        game.grid[self.spot(43, 30)] = [ENEMY, 1]  # a farmer in the gate, wanting in
        self.assertFalse(dwellers.swapPast(game, self.spot(43, 30), self.spot(43, 31), force=True))
        grub.headedTo = frozenset({self.spot(43, 30)})  # (unless that's where it's being taken)
        self.assertTrue(dwellers.swapPast(game, self.spot(43, 30), self.spot(43, 31), force=True))


# ---------------------------------------------------------------- whole floors

class GrowingFloorTests(unittest.TestCase):
    def runFloor(self, kind, turns, seed=11):
        random.seed(seed)
        game = cityGame(seed)
        climbDown(game, kind)
        game.floorEvents.pop(game.level, None)  # (no Expansion or Overgrowth: just the works)
        for _ in range(turns):
            game.enemyTurn()
        return game

    def test_a_farm_keeps_its_grubs_fed_grows_its_herd_and_makes_dew(self):
        game = self.runFloor("farm", 1500, seed=7)
        grubs = dwellerwork.grubsHere(game)
        self.assertGreater(len(grubs), sum(mineshafts.GRUBS_PER_PEN), "the herd has grown")
        self.assertTrue(all(grub.hunger < dwellerfarming.STARVE_TURNS for _, grub in grubs))
        dew = sum(stack.amount for spot in dwellerwork.storageChests(game) for stack in game.grid[spot][2] if stack.materialId == "dew")
        self.assertGreater(dew, 0)


if __name__ == "__main__":
    unittest.main()
