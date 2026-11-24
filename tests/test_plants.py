"""Plants: the herb kinds, how each plant grows through its stages, and the Game-of-Life style growth step (plants.py)."""
import random
import unittest
from unittest import mock

from cruel.world import plants
from cruel.world import wall

ROW_LENGTH = 7
ROW_COUNT = 7
CENTER = 3 * ROW_LENGTH + 3


def smallFloor(floorType="Stone"):
    """A 7x7 grid of open floor, every tile of one floor type. Returns (grid, rooms)."""
    grid = {position: [0, 0] for position in range(ROW_LENGTH * ROW_COUNT)}
    rooms = {"Stone": set(), "Wood": set(), "Sand": set(), "Gold": set(), "Molten": set()}
    if floorType != "Sand":  # Sand is any tile in no other room
        rooms[floorType] = set(grid)
    return grid, rooms


def spotAt(column, row):
    return row * ROW_LENGTH + column


def plantTile(kind, stage=None, planted=False):
    plant = plants.Plant(kind, planted=planted)
    if stage is not None:
        plant.stage, plant.timer = stage, 0
        plant.seeded = stage == "seed"
    return [8, 0, plant]


def plantPositions(grid, kind=None):
    return {position for position, tile in grid.items() if tile[0] == 8 and (kind is None or tile[2].kind == kind)}


class PlantKindTests(unittest.TestCase):
    """The PLANTS table: what each kind does."""

    def test_walkable_and_sight_blocking_flags_match_each_kind(self):
        expected = {"bloodcap": (False, False), "hearthmoss": (True, False), "glowcap": (True, False),
                    "emberroot": (False, True), "shadowfern": (True, True), "organizers_demise": (True, False)}
        for kind, (walkable, blocksSight) in expected.items():
            plant = plants.Plant(kind)
            self.assertEqual((plant.walkable, plant.blocksSight), (walkable, blocksSight), kind)

    def test_only_a_plant_you_can_walk_into_that_blocks_sight_hides_you(self):
        self.assertTrue(plants.Plant("shadowfern").hides)
        self.assertFalse(plants.Plant("emberroot").hides)
        self.assertFalse(plants.Plant("glowcap").hides)

    def test_every_kind_grows_on_at_most_two_floors_and_has_both_ripe_stages(self):
        for kind, plantDetails in plants.PLANTS.items():
            self.assertTrue(1 <= len(plantDetails["floors"]) <= 2, kind)
            self.assertEqual(sorted(plantDetails["stages"]), ["harvest", "seed"], kind)

    def test_organizers_demise_follows_conway_and_never_grows_wild(self):
        self.assertTrue(plants.isConway("organizers_demise"))
        self.assertFalse(plants.isConway("bloodcap"))
        self.assertNotIn("organizers_demise", plants.wildKinds())
        self.assertEqual(set(plants.wildKinds("Gold")), {"glowcap", "emberroot"})

    def test_the_takeover_loop_on_stone_has_no_winner(self):
        self.assertIn("bloodcap", plants.TAKES_OVER["glowcap"])
        self.assertIn("shadowfern", plants.TAKES_OVER["bloodcap"])
        self.assertIn("glowcap", plants.TAKES_OVER["shadowfern"])

    def test_descriptions_read_well(self):
        self.assertEqual(plants.traits("shadowfern"), "walk into it to hide")
        self.assertEqual(plants.traits("emberroot"), "blocks the way, blocks sight")
        self.assertEqual(plants.traits("glowcap"), "can be walked through")
        self.assertEqual(plants.takesOver("shadowfern"), "Takes over Hearthmoss and Glowcap")
        self.assertEqual(plants.takesOver("organizers_demise"), "")
        self.assertEqual(sorted(plants.takenOverBy("bloodcap")), ["Glowcap", "Hearthmoss"])
        description = plants.plantDescription("bloodcap")
        self.assertTrue(description.startswith("Grows on Stone and Wood floors, blocks the way"))
        self.assertIn("Planted, it gives herbs, then seeds", description)
        self.assertIn("Deals magic damage", plants.plantDescription("organizers_demise"))


class PlantStageTests(unittest.TestCase):
    """One plant moving through sprout, growing and its two ripe stages."""

    def growSteps(self, plant, count):
        return [plant.grow() for _ in range(count)]

    def test_a_new_plant_is_an_unripe_sprout(self):
        sprout = plants.Plant("bloodcap")
        self.assertEqual(sprout.stage, "planted")
        self.assertEqual(sprout.stageLabel(), "sprout")
        self.assertFalse(sprout.ready)
        self.assertFalse(sprout.seeding)
        self.assertFalse(sprout.canWither)

    def test_a_bloodcap_is_harvested_first_then_goes_to_seed_for_good(self):
        bloodcap = plants.Plant("bloodcap")
        self.assertEqual(self.growSteps(bloodcap, 2), [False, True])
        self.assertEqual(bloodcap.stage, "growing")
        self.growSteps(bloodcap, 3)
        self.assertEqual(bloodcap.stage, "harvest")
        self.assertTrue(bloodcap.ready)
        self.assertFalse(bloodcap.seeded)
        self.growSteps(bloodcap, 3)
        self.assertEqual(bloodcap.stage, "seed")
        self.assertTrue(bloodcap.seeded and bloodcap.seeding and bloodcap.lastStage)
        self.assertEqual(self.growSteps(bloodcap, 5), [False] * 5)  # it stays gone to seed until picked
        self.assertEqual(bloodcap.stage, "seed")

    def test_a_hearthmoss_goes_to_seed_first_and_stays_able_to_wither_after(self):
        hearthmoss = plants.Plant("hearthmoss")
        self.growSteps(hearthmoss, 5)
        self.assertEqual(hearthmoss.stage, "seed")
        self.growSteps(hearthmoss, 3)
        self.assertEqual(hearthmoss.stage, "harvest")
        self.assertTrue(hearthmoss.lastStage)
        self.assertTrue(hearthmoss.canWither)
        self.assertFalse(hearthmoss.seeding)

    def test_picking_gives_the_ripe_stage_or_nothing_when_unripe(self):
        self.assertIsNone(plants.Plant("glowcap").pick())
        self.assertEqual(plantTile("glowcap", "harvest")[2].pick(), "harvest")
        self.assertEqual(plantTile("glowcap", "seed")[2].pick(), "seed")

    def test_a_plant_from_an_old_save_counts_as_fully_grown(self):
        oldPlant = plants.Plant("bloodcap")
        oldPlant.stage = None
        self.assertFalse(oldPlant.staged)
        self.assertTrue(oldPlant.ready and oldPlant.seeding and oldPlant.canWither)
        self.assertEqual(oldPlant.pick(), "harvest")
        self.assertFalse(oldPlant.grow())

    def test_wild_plants_start_somewhere_in_their_cycle(self):
        random.seed(1)
        seenStages = set()
        for _ in range(300):
            wildPlant = plants.Plant.grown("hearthmoss")
            seenStages.add(wildPlant.stage)
            if wildPlant.stage == "harvest":  # hearthmoss seeds before its harvest stage
                self.assertTrue(wildPlant.seeded)
                self.assertEqual(wildPlant.timer, 0)
            if wildPlant.stage == "planted":
                self.assertFalse(wildPlant.seeded)
        self.assertEqual(seenStages, {"planted", "growing", "seed", "harvest"})


class FloorHelperTests(unittest.TestCase):
    """The small helpers used by the growth step."""

    def test_a_tile_in_no_room_is_sand(self):
        _grid, rooms = smallFloor("Wood")
        self.assertEqual(plants.floorOf(CENTER, rooms), "Wood")
        self.assertEqual(plants.floorOf(CENTER, {"Stone": set()}), "Sand")

    def test_every_wild_kind_grows_on_two_city_floors_and_each_city_floor_grows_something(self):
        for kind in plants.wildKinds():
            self.assertEqual(len(plants.PLANTS[kind]["cityFloors"]), 2, kind)
            for floor in plants.PLANTS[kind]["cityFloors"]:
                self.assertIn(floor, plants.CITY_FLOORS)
        for floor in plants.CITY_FLOORS:
            self.assertTrue(plants.wildKinds(floor), floor)

    def test_a_city_floor_is_its_own_floor_type(self):
        grid, rooms = smallFloor()
        rooms = {"Street": set(grid)}
        self.assertEqual(plants.floorOf(CENTER, rooms), "Street")
        self.assertTrue(plants.canGrow("bloodcap", CENTER, grid, rooms))
        self.assertFalse(plants.canGrow("hearthmoss", CENTER, grid, rooms), "Hearthmoss grows on Yard and House, not Street")

    def test_a_plants_description_names_its_city_floors(self):
        self.assertIn("in a city, on Street and House floors", plants.plantDescription("bloodcap"))

    def test_plants_only_grow_on_open_floor_of_their_types(self):
        grid, rooms = smallFloor("Stone")
        self.assertTrue(plants.canGrow("bloodcap", CENTER, grid, rooms))
        self.assertFalse(plants.canGrow("hearthmoss", CENTER, grid, rooms))
        grid[CENTER] = [2, 0, wall.StoneWall()]
        self.assertFalse(plants.canGrow("bloodcap", CENTER, grid, rooms))

    def test_around_does_not_wrap_past_the_left_and_right_edges(self):
        grid, _rooms = smallFloor()
        self.assertEqual(len(plants.around(CENTER, ROW_LENGTH, grid)), 8)
        leftEdge = spotAt(0, 3)
        neighborsOfEdge = plants.around(leftEdge, ROW_LENGTH, grid)
        self.assertEqual(len(neighborsOfEdge), 5)
        self.assertTrue(all(position % ROW_LENGTH <= 1 for position in neighborsOfEdge))
        self.assertEqual(len(plants.around(0, ROW_LENGTH, grid)), 3)

    def test_a_corrupted_wall_reports_its_plant(self):
        stoneWall = wall.StoneWall()
        stoneWall.corruptedBy = "glowcap"
        self.assertEqual(plants.corruptedBy([2, 0, stoneWall]), "glowcap")
        self.assertIsNone(plants.corruptedBy([2, 0, wall.StoneWall()]))
        self.assertIsNone(plants.corruptedBy([0, 0]))


class GrowthStepTests(unittest.TestCase):
    """plants.step on a small grid: births, deaths, takeovers and corruption."""

    def test_a_conway_blinker_flips_from_a_row_to_a_column(self):
        grid, rooms = smallFloor("Wood")
        for column in (2, 3, 4):
            grid[spotAt(column, 3)] = plantTile("organizers_demise")
        self.assertTrue(plants.step(grid, rooms, ROW_LENGTH))
        self.assertEqual(plantPositions(grid), {spotAt(3, 2), spotAt(3, 3), spotAt(3, 4)})

    def test_a_conway_glider_keeps_its_five_cells_and_crawls(self):
        grid, rooms = {position: [0, 0] for position in range(12 * 12)}, {"Wood": set(range(12 * 12))}
        gliderCells = [(1, 0), (2, 1), (0, 2), (1, 2), (2, 2)]
        for column, row in gliderCells:
            grid[row * 12 + column] = plantTile("organizers_demise")
        for _ in range(4):
            plants.step(grid, rooms, 12)
        moved = {position for position, tile in grid.items() if tile[0] == 8}
        self.assertEqual(moved, {(row + 1) * 12 + column + 1 for column, row in gliderCells})  # one down and right

    def test_conway_plants_do_not_sprout_off_their_floor(self):
        grid, rooms = smallFloor("Stone")
        for column in (2, 3, 4):
            grid[spotAt(column, 3)] = plantTile("organizers_demise")
        plants.step(grid, rooms, ROW_LENGTH)
        self.assertEqual(plantPositions(grid), {spotAt(3, 3)})  # the ends die, nothing is born on Stone

    def test_a_seeding_plant_spreads_to_open_floor_around_it(self):
        grid, rooms = smallFloor("Stone")
        grid[CENTER] = plantTile("glowcap", "seed")
        plants.step(grid, rooms, ROW_LENGTH, birth=100, death=0)
        self.assertEqual(plantPositions(grid, "glowcap"), {CENTER} | set(plants.around(CENTER, ROW_LENGTH, grid)))
        newborn = grid[CENTER + 1][2]
        self.assertEqual(newborn.stage, "planted")

    def test_a_plant_that_has_not_seeded_does_not_spread(self):
        grid, rooms = smallFloor("Stone")
        grid[CENTER] = plantTile("glowcap", "harvest")
        plants.step(grid, rooms, ROW_LENGTH, birth=100, death=0)
        self.assertEqual(plantPositions(grid), {CENTER})

    def test_nothing_sprouts_on_no_birth_tiles_or_unsuitable_floor(self):
        grid, rooms = smallFloor("Wood")  # glowcap can't grow on Wood
        grid[CENTER] = plantTile("glowcap", "seed")
        plants.step(grid, rooms, ROW_LENGTH, birth=100, death=0)
        self.assertEqual(plantPositions(grid), {CENTER})
        grid, rooms = smallFloor("Stone")
        grid[CENTER] = plantTile("glowcap", "seed")
        farmTile = CENTER + 1
        plants.step(grid, rooms, ROW_LENGTH, birth=100, death=0, noBirth={farmTile})
        self.assertNotIn(farmTile, plantPositions(grid))

    def test_a_lonely_seeded_plant_withers_but_a_young_one_does_not(self):
        grid, rooms = smallFloor("Stone")
        lonelySeeded, lonelySprout = spotAt(1, 1), spotAt(5, 5)
        grid[lonelySeeded] = plantTile("bloodcap", "seed")
        grid[lonelySprout] = plantTile("bloodcap")
        plants.step(grid, rooms, ROW_LENGTH, birth=0, death=1.0)
        self.assertEqual(grid[lonelySeeded], [0, 0])
        self.assertEqual(grid[lonelySprout][0], 8)

    def test_a_seeded_plant_with_two_or_three_neighbors_survives(self):
        grid, rooms = smallFloor("Stone")
        for column in (2, 3, 4):
            grid[spotAt(column, 3)] = plantTile("bloodcap", "seed")
        plants.step(grid, rooms, ROW_LENGTH, birth=0, death=1.0)
        self.assertEqual(grid[CENTER][0], 8)  # the middle one has 2 neighbors
        self.assertEqual(grid[spotAt(2, 3)], [0, 0])  # the ends have 1

    def test_invaders_take_over_a_wild_plant_but_not_a_planted_one(self):
        for planted, expectedKind in ((False, "glowcap"), (True, "bloodcap")):
            grid, rooms = smallFloor("Stone")
            grid[CENTER] = plantTile("bloodcap", "harvest", planted=planted)
            grid[CENTER - 1] = plantTile("glowcap")  # sprouts: they don't seed, so nothing is born
            grid[CENTER + 1] = plantTile("glowcap")
            with mock.patch("random.random", return_value=0.0):
                plants.step(grid, rooms, ROW_LENGTH, death=0)
            self.assertEqual(grid[CENTER][2].kind, expectedKind, f"planted={planted}")

    def test_no_takeover_when_the_invader_cannot_grow_on_that_floor(self):
        grid, rooms = smallFloor("Wood")
        grid[CENTER] = plantTile("hearthmoss", "harvest")
        grid[CENTER - 1] = plantTile("emberroot")  # emberroot takes over hearthmoss, but not on Wood
        grid[CENTER + 1] = plantTile("emberroot")
        with mock.patch("random.random", return_value=0.0):
            plants.step(grid, rooms, ROW_LENGTH, death=0)
        self.assertEqual(grid[CENTER][2].kind, "hearthmoss")

    def test_overgrowth_corrupts_a_wall_between_plants(self):
        grid, rooms = smallFloor("Stone")
        grid[CENTER] = [2, 0, wall.StoneWall()]
        grid[CENTER - 1] = plantTile("bloodcap")
        grid[CENTER + 1] = plantTile("bloodcap")
        with mock.patch("random.random", return_value=0.0):
            plants.step(grid, rooms, ROW_LENGTH, death=0, corrupt=True)
        self.assertEqual(plants.corruptedBy(grid[CENTER]), "bloodcap")

    def test_walls_stay_clean_without_overgrowth_or_beside_conway_plants(self):
        grid, rooms = smallFloor("Wood")
        grid[CENTER] = [2, 0, wall.WoodWall()]
        grid[CENTER - 1] = plantTile("bloodcap")
        grid[CENTER + 1] = plantTile("bloodcap")
        with mock.patch("random.random", return_value=0.0):
            plants.step(grid, rooms, ROW_LENGTH, death=0)
        self.assertIsNone(plants.corruptedBy(grid[CENTER]))
        grid, rooms = smallFloor("Wood")
        grid[CENTER] = [2, 0, wall.WoodWall()]
        grid[CENTER - 1] = plantTile("organizers_demise")
        grid[CENTER + 1] = plantTile("organizers_demise")
        with mock.patch("random.random", return_value=0.0):
            plants.step(grid, rooms, ROW_LENGTH, corrupt=True)
        self.assertIsNone(plants.corruptedBy(grid[CENTER]))

    def test_a_corrupted_wall_spreads_its_plant_like_a_seeding_one(self):
        grid, rooms = smallFloor("Stone")
        corruptedWall = wall.StoneWall()
        corruptedWall.corruptedBy = "glowcap"
        grid[CENTER] = [2, 0, corruptedWall]
        plants.step(grid, rooms, ROW_LENGTH, birth=100, death=0)
        self.assertEqual(plantPositions(grid, "glowcap"), set(plants.around(CENTER, ROW_LENGTH, grid)))

    def test_a_quiet_floor_reports_no_change(self):
        grid, rooms = smallFloor("Stone")
        self.assertFalse(plants.step(grid, rooms, ROW_LENGTH))


class WildPatchTests(unittest.TestCase):
    """Wild patches on a new floor, and topping a bare floor back up."""

    def test_a_patch_grows_three_to_six_plants_of_one_kind_together(self):
        random.seed(5)
        grid, rooms = smallFloor("Stone")
        placed = plants.growPatch(grid, rooms, ROW_LENGTH, CENTER, "bloodcap")
        self.assertTrue(3 <= placed <= 6)
        self.assertEqual(len(plantPositions(grid, "bloodcap")), placed)

    def test_a_patch_never_grows_on_avoided_tiles(self):
        random.seed(6)
        grid, rooms = smallFloor("Stone")
        avoided = set(range(0, ROW_LENGTH * 4))
        plants.addPatch(grid, rooms, ROW_LENGTH, "bloodcap", avoid=avoided)
        self.assertTrue(plantPositions(grid))
        self.assertFalse(plantPositions(grid) & avoided)

    def test_a_patch_only_uses_kinds_that_grow_on_that_floor(self):
        random.seed(7)
        grid, rooms = smallFloor("Gold")
        for _ in range(5):
            plants.addPatch(grid, rooms, ROW_LENGTH)
        kinds = {grid[position][2].kind for position in plantPositions(grid)}
        self.assertTrue(kinds and kinds <= {"glowcap", "emberroot"})

    def test_no_patch_where_nothing_can_grow(self):
        grid, rooms = smallFloor("Stone")
        for position in grid:
            grid[position] = [2, 0, wall.StoneWall()]
        self.assertEqual(plants.addPatch(grid, rooms, ROW_LENGTH), 0)

    def test_the_first_floor_gets_a_patch_of_every_wild_kind_its_floors_allow(self):
        random.seed(8)
        rowLength, size = 30, 30 * 30
        grid = {position: [0, 0] for position in range(size)}
        # left half Stone, right half Sand: every wild kind has somewhere to grow
        rooms = {"Stone": {position for position in grid if position % rowLength < 15}, "Wood": set(), "Gold": set()}
        plants.placeWild(grid, rooms, rowLength, size, everyKind=True)
        kinds = {tile[2].kind for tile in grid.values() if tile[0] == 8}
        reachableKinds = {kind for kind in plants.wildKinds()
                          if {"Stone", "Sand"} & set(plants.PLANTS[kind]["floors"])}
        self.assertTrue(reachableKinds <= kinds)

    def test_a_floor_low_on_plants_gets_a_new_patch(self):
        random.seed(9)
        grid, rooms = smallFloor("Stone")
        self.assertTrue(plants.keepAlive(grid, rooms, ROW_LENGTH))
        for position in list(grid)[:plants.MIN_PLANTS]:
            grid[position] = plantTile("bloodcap")
        self.assertFalse(plants.keepAlive(grid, rooms, ROW_LENGTH))


if __name__ == "__main__":
    unittest.main()
