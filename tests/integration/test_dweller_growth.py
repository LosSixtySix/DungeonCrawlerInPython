"""The Dwellers' works floors growing: young Dew Grubs, farmers moving grubs between pens and building new pens
(dewgrubs.py), and new storehouses when the chests are full (dwellerbuilding.py).

Integration tests; the rest are in tests/acceptance/test_dweller_growth.py."""
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
from tests.helpers.dweller_growth import ENEMY, FLOOR, PenTest


# ---------------------------------------------------------------- young

class YoungGrubTests(PenTest):
    def test_two_fed_grown_grubs_together_can_have_a_young_one_in_their_pen(self):
        pen = self.pen(40, 30)
        mother, _ = self.fill(pen, 2)
        motherSpot = self.positionOf(mother)
        with mock.patch.object(dewgrubs, "BIRTH_CHANCE", 1):
            youngSpot = dewgrubs.maybeGiveBirth(self.game, motherSpot, mother)
        self.assertIn(youngSpot, pen["inside"])
        young = self.game.grid[youngSpot][2]
        self.assertFalse(young.grown)
        self.assertEqual(young.name, "Young Dew Grub")
        self.assertEqual(young.pen, pen["inside"])
        self.assertIn(youngSpot, self.game.EnemyPositions)

    def test_no_young_without_a_fed_grown_grub_near(self):
        pen = self.pen(40, 30)
        mother = self.fill(pen, 1)[0]
        motherSpot = self.positionOf(mother)
        with mock.patch.object(dewgrubs, "BIRTH_CHANCE", 1):
            self.assertIsNone(dewgrubs.maybeGiveBirth(self.game, motherSpot, mother), "alone")
            farSpot = motherSpot + (dewgrubs.MATE_RANGE + 1) * self.game.rowLength * 3
            self.grub(farSpot, pen)
            self.assertIsNone(dewgrubs.maybeGiveBirth(self.game, motherSpot, mother), "too far away")
            self.game.grid[farSpot] = [0, 1]
            self.game.EnemyPositions.discard(farSpot)
            free = [tile for tile in pen["inside"] if self.game.grid[tile][0] == 0]
            mate = self.grub(min(free, key=lambda tile: dwellers.distance(self.game, motherSpot, tile)), pen)
            mate.hunger = dwellerfarming.HUNGRY_TURNS
            self.assertIsNone(dewgrubs.maybeGiveBirth(self.game, motherSpot, mother), "hungry")
            mate.grown = False
            mate.hunger = 0
            self.assertIsNone(dewgrubs.maybeGiveBirth(self.game, motherSpot, mother), "young")
            mate.grown = True
            self.assertIsNotNone(dewgrubs.maybeGiveBirth(self.game, motherSpot, mother))

    def test_a_full_pen_still_has_young_and_the_farmers_then_move_grubs_out(self):
        pen = self.pen(40, 30)
        grubs = self.fill(pen, dewgrubs.PEN_MOST)
        other = self.pen(60, 30)
        with mock.patch.object(dewgrubs, "BIRTH_CHANCE", 1):
            self.assertIsNotNone(dewgrubs.maybeGiveBirth(self.game, self.positionOf(grubs[0]), grubs[0]))
        self.assertEqual(len(self.grubsIn(pen)), dewgrubs.PEN_MOST + 1, "no hard limit")
        grub, target = dewgrubs.grubToMove(self.game, self.farmer(52, 25))
        self.assertEqual((grub.pen, target), (pen["inside"], other["inside"]))

    def test_a_young_grub_has_no_young(self):
        pen = self.pen(40, 30)
        young = self.fill(pen, 1, grown=False)[0]
        with mock.patch.object(dewgrubs, "BIRTH_CHANCE", 1):
            self.assertIsNone(dewgrubs.maybeGiveBirth(self.game, self.positionOf(young), young))

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
        pen = self.pen(40, 30)
        hungry, _ = self.fill(pen, 2)  # (the other one has been fed: a mate)
        hungry.hunger = dwellerfarming.HUNGRY_TURNS
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

class HerdSizeTests(PenTest):
    def setUp(self):
        super().setUp()
        self.keepers = []

    def keeper(self):
        keeper = self.farmer(50 + 2 * len(self.keepers), 25)
        self.keepers.append(keeper)
        keeper.farmRole = "keeper"
        return keeper

    def test_young_are_born_however_big_the_herd(self):
        pen = self.pen(40, 30)
        grubs = self.fill(pen, dwellerfarming.KEEPER_HERD + 1)
        with mock.patch.object(dewgrubs, "BIRTH_CHANCE", 1):
            self.assertIsNotNone(dewgrubs.maybeGiveBirth(self.game, self.positionOf(grubs[0]), grubs[0]))

    def test_the_keepers_look_after_as_many_as_they_can_feed_grown_and_least_hungry_first(self):
        pen = self.pen(40, 30)
        grubs = self.fill(pen, dwellerfarming.KEEPER_HERD + 2)
        self.keeper()
        for index, grub in enumerate(grubs):
            grub.hunger = 60 + index
        young = grubs[0]
        young.grown = False
        cared = dwellerfarming.caredFor(self.game, dwellerwork.grubsHere(self.game))
        self.assertEqual(len(cared), dwellerfarming.KEEPER_HERD)
        self.assertNotIn(id(young), cared, "the young one goes first")
        self.assertNotIn(id(grubs[-1]), cared, "then the hungriest")
        self.keeper()
        self.assertEqual(len(dwellerfarming.caredFor(self.game, dwellerwork.grubsHere(self.game))), len(grubs),
                         "a second keeper can feed them all")

    def test_a_keeper_lets_a_grub_it_cant_look_after_starve(self):
        pen = self.pen(40, 30)
        grubs = self.fill(pen, dwellerfarming.KEEPER_HERD + 1)
        keeper = self.keeper()
        keeper.materials = {"bloodcap": 10}
        for grub in grubs:
            grub.hunger = dwellerfarming.HUNGRY_TURNS
        letGo = grubs[-1]
        letGo.hunger = dwellerfarming.STARVING_TURNS
        cared = dwellerfarming.caredFor(self.game, dwellerwork.grubsHere(self.game))
        self.assertNotIn(id(letGo), cared)
        with mock.patch.object(dewgrubs, "BIRTH_CHANCE", 0), mock.patch.object(dwellers, "IDLE_CHANCE", 0):
            for _ in range(dwellerfarming.STARVE_TURNS):
                self.game.enemyTurn()
                dwellerfarming.starveTurn(self.game)
        self.assertNotIn(letGo, self.grubsIn(pen), "it starved")
        self.assertEqual(len(self.grubsIn(pen)), dwellerfarming.KEEPER_HERD, "the rest were fed")


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
        door, backDoor = site["door"], site["backDoor"]
        self.assertNotIn(backDoor, site["walls"])
        self.assertTrue(door % self.game.rowLength == backDoor % self.game.rowLength
                        or door // self.game.rowLength == backDoor // self.game.rowLength, "on opposite sides")
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

    def test_a_site_is_two_tiles_from_any_other_building_and_its_rock_that_close_is_dug_out_too(self):
        farmer = self.farmer(50, 40)
        for column in range(30, 70):
            self.wallAt(column, 31, wall.ShopWall)  # another building's wall
            self.wallAt(column, 49, wall.StoneWall)  # rock
        site = dwellerbuilding.findSite(self.game, self.spot(50, 40), farmer, 7, 6)
        for spot in site["box"]:
            for other in range(30, 70):
                self.assertGreater(dwellers.distance(self.game, spot, self.spot(other, 31)), mineshafts.CLEARANCE,
                                   "another building's wall is no nearer than CLEARANCE")
        boxColumns = [spot % self.game.rowLength for spot in site["box"]]
        boxRows = [spot // self.game.rowLength for spot in site["box"]]
        ring = {column + row * self.game.rowLength
                for row in range(min(boxRows) - mineshafts.CLEARANCE, max(boxRows) + mineshafts.CLEARANCE + 1)
                for column in range(min(boxColumns) - mineshafts.CLEARANCE, max(boxColumns) + mineshafts.CLEARANCE + 1)} - site["box"]
        self.assertEqual(site["margin"], ring)
        rockNear = {spot for spot in ring if dwellerwork.mineable(self.game.grid[spot])}
        self.assertTrue(rockNear <= site["rock"], "it's all dug out with the site")

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
        other = self.worker(41, 30)
        other.swappedAt = self.game.turnCount
        self.game.movedEnemies = {self.spot(41, 30)}
        self.game.grid[self.spot(40, 30)] = [ENEMY, 1]  # (the mover, lifted off for its turn)
        self.assertFalse(dwellers.swapPast(self.game, self.spot(40, 30), self.spot(41, 30)))
        self.assertTrue(dwellers.swapPast(self.game, self.spot(40, 30), self.spot(41, 30), force=True))

    def test_a_grub_is_only_swapped_into_its_own_pen(self):
        pen = self.pen(40, 30)
        grub = self.grub(self.spot(43, 31), pen)
        self.game.movedEnemies = {self.spot(43, 31)}
        self.game.grid[self.spot(43, 30)] = [ENEMY, 1]  # a farmer in the gate, wanting in
        self.assertFalse(dwellers.swapPast(self.game, self.spot(43, 30), self.spot(43, 31), force=True))
        grub.headedTo = frozenset({self.spot(43, 30)})  # (unless that's where it's being taken)
        self.assertTrue(dwellers.swapPast(self.game, self.spot(43, 30), self.spot(43, 31), force=True))


if __name__ == "__main__":
    unittest.main()
