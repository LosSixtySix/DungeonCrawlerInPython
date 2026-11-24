"""The Expansion event: goblin factions, their huts, spawners, bonfires and what goblins carry (expansion.py)."""
import random
import unittest

from cruel.entities import enemies
from cruel.world import expansion
from cruel.world import wall
from tests import support


def blankFloor(game):
    """Turns the game's floor into open, unseen Stone floor with no enemies, the player in the top-left corner."""
    for position in game.grid:
        game.grid[position] = [0, 0]
    game.rooms = {"Stone": set(game.grid), "Wood": set(), "Sand": set(), "Gold": set(), "Molten": set()}
    game.EnemyPositions = set()
    game.enemyOccupiedItemSpaces = {}
    game.playerPositionFlat = 0
    game.currentLocation = [0, 0]
    game.grid[0] = [1, 0]


def middleOf(game):
    rowCount = game.numberOfSpots // game.rowLength
    return (rowCount // 2) * game.rowLength + game.rowLength // 2


def factionGoblins(game, faction):
    return [unit for _position, unit in expansion.factionUnits(game, faction)]


class HutShapeTests(unittest.TestCase):
    """The hut layout: walls, entrances, the room inside."""

    def test_a_hut_wall_ring_leaves_out_its_corners_and_doors(self):
        self.assertEqual(len(expansion.hutWalls(())), 24 - 4)
        hutWithDoors = expansion.hutWalls(expansion.HUT_SIDES)
        self.assertEqual(len(hutWithDoors), 16)
        self.assertNotIn((3, 3), hutWithDoors)
        self.assertNotIn((0, -3), hutWithDoors)

    def test_the_room_inside_a_hut_leaves_the_middle_for_the_spawner(self):
        self.assertEqual(len(expansion.HUT_INSIDE), 24)
        self.assertNotIn((0, 0), expansion.HUT_INSIDE)
        self.assertEqual(len(expansion.HUT_FLOOR), 81)


class HutLayoutTests(unittest.TestCase):
    """layOutHut on a real (blank) floor."""

    def setUp(self):
        self.game = support.newGame()
        blankFloor(self.game)
        self.center = middleOf(self.game)

    def test_a_spawner_hut_fits_on_open_floor(self):
        hut = expansion.layOutHut(self.game, self.center, set())
        self.assertEqual(len(hut["floor"]), 81)
        self.assertEqual(len(hut["walls"]), 16)
        self.assertEqual(len(hut["inside"]), 24)
        self.assertFalse(hut["done"])

    def test_a_storage_hut_is_bigger_and_lined_with_chests(self):
        storageHut = expansion.layOutHut(self.game, self.center, set(), kind="storage")
        self.assertEqual(storageHut["radius"], expansion.STORAGE_RADIUS)
        self.assertEqual(len(storageHut["chests"]), len(expansion.STORAGE_CHESTS))
        self.assertFalse(set(storageHut["chests"]) & set(storageHut["inside"]))

    def test_a_farming_hut_has_beds_round_a_middle_chest(self):
        farmHut = expansion.layOutHut(self.game, self.center, set(), kind="farm")
        self.assertEqual(farmHut["chest"], self.center)
        self.assertEqual(len(farmHut["beds"]), 16)
        self.assertNotIn(self.center + 1, farmHut["beds"])  # the paths from the doors stay clear

    def test_no_hut_over_claimed_ground_the_player_a_chest_or_the_map_edge(self):
        game, center = self.game, self.center
        self.assertIsNone(expansion.layOutHut(game, center, {center + 2}))
        game.grid[center + 3] = [3, 0, []]
        self.assertIsNone(expansion.layOutHut(game, center, set()))
        self.assertIsNone(expansion.layOutHut(game, game.rowLength * 3 + 3, set()))  # the player is at 0
        self.assertIsNone(expansion.layOutHut(game, game.rowLength * 10 + 1, set()))  # too close to the left edge

    def test_offset_tiles_off_the_map_are_none(self):
        game = self.game
        self.assertEqual(expansion.offsetTile(game, self.center, 2, 1), self.center + 2 + game.rowLength)
        self.assertIsNone(expansion.offsetTile(game, 0, -1, 0))
        self.assertIsNone(expansion.offsetTile(game, 0, 0, -1))


class FactionTests(unittest.TestCase):
    """Factions, who fights whom, and the camp state."""

    def setUp(self):
        random.seed(1)
        self.game = support.newGame()
        blankFloor(self.game)
        expansion.PEACE.clear()

    def tearDown(self):
        expansion.PEACE.clear()

    def test_new_factions_get_the_next_id_on_this_floor(self):
        firstFaction = expansion.newFaction(self.game, "warpaint")
        secondFaction = expansion.newFaction(self.game, "ashen")
        self.assertEqual((firstFaction.id, secondFaction.id), (0, 1))
        self.assertIs(expansion.camp(self.game)["factions"][1], secondFaction)

    def test_goblins_fight_everyone_outside_their_faction_unless_at_peace(self):
        redFaction = expansion.newFaction(self.game, "warpaint")
        blueFaction = expansion.newFaction(self.game, "ashen")
        redGoblin, redChief, blueGoblin, wildGoblin = enemies.Goblin(), enemies.GoblinChief(), enemies.Goblin(), enemies.Goblin()
        expansion.setFaction(redGoblin, redFaction)
        expansion.setFaction(redChief, redFaction)
        expansion.setFaction(blueGoblin, blueFaction)
        self.assertFalse(expansion.hostile(redGoblin, redChief))
        self.assertTrue(expansion.hostile(redGoblin, blueGoblin))
        self.assertTrue(expansion.hostile(redGoblin, wildGoblin))
        expansion.PEACE.add(frozenset((redFaction.id, blueFaction.id)))
        self.assertFalse(expansion.hostile(redGoblin, blueGoblin))

    def test_peace_after_a_schism_runs_out(self):
        game = self.game
        oldFaction = expansion.newFaction(game, "warpaint")
        newFaction = expansion.newFaction(game, "ashen")
        newFaction.peaceWith, newFaction.peaceUntil = oldFaction.id, game.turnCount + 5
        expansion.updatePeace(game)
        self.assertTrue(expansion.atPeace(oldFaction.id, newFaction.id))
        game.turnCount += 6
        expansion.updatePeace(game)
        self.assertFalse(expansion.atPeace(oldFaction.id, newFaction.id))
        self.assertIsNone(newFaction.peaceWith)

    def test_joining_a_faction_keeps_the_goblins_own_gold_apart(self):
        faction = expansion.newFaction(self.game, "ochre")
        goblin = enemies.Goblin()
        ownGold = goblin.gold
        expansion.setFaction(goblin, faction)
        self.assertEqual((goblin.faction, goblin.look, goblin.baseGold), (faction.id, "ochre", ownGold))
        goblin.gold += 7
        self.assertEqual(expansion.pickedGold(goblin), 7)

    def test_a_new_look_is_one_no_living_faction_wears(self):
        game = self.game
        faction = expansion.newFaction(game, "warpaint")
        expansion.spawn(game, middleOf(game), "Goblin", faction)
        for _ in range(20):
            self.assertNotEqual(expansion.pickLook(game), "warpaint")


class CarryingTests(unittest.TestCase):
    """A goblin's pouch: slots, stacks and what spills out."""

    def setUp(self):
        self.game = support.newGame()
        blankFloor(self.game)
        self.goblin = enemies.Goblin()
        expansion.setFaction(self.goblin, expansion.newFaction(self.game, "warpaint"))

    def test_each_stack_of_a_material_takes_a_slot(self):
        goblin = self.goblin
        goblin.materials = {"stone": 15, "coal": 3}
        self.assertEqual(expansion.slotsUsed(goblin), 3)
        self.assertEqual(expansion.roomFor(goblin), expansion.CARRY_SLOTS - 3)

    def test_picked_up_gold_and_items_take_a_slot_each(self):
        goblin = self.goblin
        goblin.materials = {}
        goblin.gold += 50
        goblin.loot = ["a sword", "a shield"]
        self.assertEqual(expansion.slotsUsed(goblin), 3)

    def test_fit_amount_tops_up_stacks_then_fills_free_slots(self):
        goblin = self.goblin
        goblin.materials = {"stone": 15}
        expected = (2 + expansion.CARRY_SLOTS - 2) * expansion.GOBLIN_STACK - 15
        self.assertEqual(expansion.fitAmount(goblin, "stone"), expected)

    def test_what_does_not_fit_drops_on_the_floor(self):
        game, goblin = self.game, self.goblin
        dropSpot = middleOf(game)
        goblin.materials = {"stone": expansion.GOBLIN_STACK * expansion.CARRY_SLOTS, "coal": 4}
        expansion.dropExtra(game, goblin, dropSpot)
        self.assertEqual(expansion.slotsUsed(goblin), expansion.CARRY_SLOTS)
        self.assertNotIn("coal", goblin.materials)  # the smallest stack goes first
        self.assertEqual(game.grid[dropSpot][0], 9)

    def test_a_squads_load_is_the_share_of_its_slots_filled(self):
        squad = expansion.Squad()
        fullGoblin, emptyGoblin = enemies.Goblin(), enemies.Goblin()
        fullGoblin.materials = {"stone": expansion.GOBLIN_STACK * expansion.CARRY_SLOTS}
        emptyGoblin.materials = {}
        squad.members = [fullGoblin, emptyGoblin]
        self.assertAlmostEqual(expansion.squadLoad(squad), 0.5)
        self.assertEqual(expansion.squadLoad(expansion.Squad()), 0)

    def test_ore_veins_and_gold_walls_are_worth_mining(self):
        self.assertTrue(expansion.isOre([2, 0, wall.IronVein()]))
        self.assertTrue(expansion.isOre([2, 0, wall.GoldWall()]))
        self.assertFalse(expansion.isOre([2, 0, wall.StoneWall()]))


class SharedWorkTests(unittest.TestCase):
    """work(): progress kept on a hut or faction so builders add up."""

    def test_work_finishes_after_the_turns_needed_and_starts_over(self):
        hut = {}
        self.assertEqual([expansion.work(hut, "wall", 2) for _ in range(3)], [False, True, False])
        self.assertEqual(hut["progress"], {"wall": 1})

    def test_two_builders_on_the_same_thing_share_progress(self):
        faction = expansion.Faction(0, "warpaint")
        self.assertFalse(expansion.work(faction, ("bonfire", 5), 2))
        self.assertTrue(expansion.work(faction, ("bonfire", 5), 2))


class WalkingTests(unittest.TestCase):
    """The path maps goblins share."""

    def test_walking_distance_on_open_floor_is_the_step_count(self):
        game = support.newGame()
        blankFloor(game)
        center = middleOf(game)
        distances = expansion.walkingDistances(game, center, 6)
        self.assertEqual(distances[center + 3 + 2 * game.rowLength], 5)
        self.assertNotIn(center + 7, distances)

    def test_goblins_do_not_walk_through_walls(self):
        game = support.newGame()
        blankFloor(game)
        center = middleOf(game)
        for position in game.neighbors(center):
            game.grid[position] = [2, 0, wall.StoneWall()]
        self.assertEqual(expansion.walkingDistances(game, center, 5), {center: 0})


class WarbandTests(unittest.TestCase):
    """The war band arriving and setting up camp."""

    def setUp(self):
        random.seed(2)
        self.game = support.newGame()
        blankFloor(self.game)

    def test_the_war_band_arrives_together_out_of_sight(self):
        game = self.game
        self.assertTrue(expansion.spawnWarband(game))
        faction = next(iter(expansion.camp(game)["factions"].values()))
        self.assertIn(faction.look, expansion.FIRST_LOOKS)
        goblins = factionGoblins(game, faction)
        self.assertEqual(sorted(goblin.name for goblin in goblins), sorted(expansion.WARBAND))
        for position, _goblin in expansion.factionUnits(game, faction):
            self.assertGreaterEqual(expansion.dist(game, position, game.playerPositionFlat), 10)
        squad = faction.squads[0]
        self.assertEqual(sorted(member.name for member in squad.members), ["Goblin", "Goblin", "Goblin Chieftan"])
        self.assertFalse(squad.marching)
        farmer = next(goblin for goblin in goblins if goblin.name == "Goblin Farmer")
        self.assertEqual(sum(farmer.materials.values()), expansion.FARMER_START_SEEDS)

    def test_no_war_band_when_there_is_no_room(self):
        game = self.game
        for position in game.grid:
            if position != 0:
                game.grid[position] = [2, 0, wall.StoneWall()]
        self.assertFalse(expansion.spawnWarband(game))
        self.assertEqual(expansion.camp(game)["factions"], {})

    def test_the_builders_light_a_bonfire_and_start_a_hut(self):
        game = self.game
        expansion.spawnWarband(game)
        faction = next(iter(expansion.camp(game)["factions"].values()))
        for _ in range(60):
            game.enemyTurn()
        self.assertTrue(faction.bonfires)
        bonfireTile = game.grid[faction.bonfires[0]]
        self.assertEqual(bonfireTile[0], expansion.CAMP)
        self.assertEqual(bonfireTile[2].kind, "bonfire")
        self.assertIn(faction.bonfires[0], expansion.bonfires(game))
        self.assertTrue(faction.huts)

    def test_the_starting_crop_grows_on_the_floor_round_the_camp(self):
        game = self.game
        crop = expansion.startingCrop(game, middleOf(game))
        self.assertIn("Stone", expansion.plants.PLANTS[crop]["floors"])


class StructureTests(unittest.TestCase):
    """Spawners and bonfires."""

    def setUp(self):
        random.seed(3)
        self.game = support.newGame()
        blankFloor(self.game)
        self.center = middleOf(self.game)
        self.faction = expansion.newFaction(self.game, "warpaint")

    def addSpawner(self):
        spawner = expansion.Structure("spawner", self.faction.id)
        expansion.place(self.game, self.center, spawner)
        return spawner

    def test_a_spawner_eats_food_to_make_a_goblin_of_its_faction(self):
        game = self.game
        self.faction.bonfires.append(self.center + 20)
        spawner = self.addSpawner()
        spawner.timer, spawner.food = 1, 4
        expansion.stepSpawner(game, self.center, spawner)
        self.assertEqual(spawner.food, 4 - expansion.FOOD_PER_SPAWN)
        self.assertEqual(len(factionGoblins(game, self.faction)), 1)
        low, high = expansion.SPAWN_TURNS
        self.assertTrue(low <= spawner.timer <= high)

    def test_a_hungry_spawner_waits(self):
        game = self.game
        self.faction.bonfires.append(self.center + 20)
        spawner = self.addSpawner()
        spawner.timer, spawner.food = 1, expansion.FOOD_PER_SPAWN - 1
        expansion.stepSpawner(game, self.center, spawner)
        self.assertEqual(factionGoblins(game, self.faction), [])
        self.assertEqual(spawner.timer, 1)

    def test_a_spawner_with_no_camp_and_no_builder_makes_a_builder(self):
        game = self.game
        spawner = self.addSpawner()
        spawner.timer = 1
        expansion.stepSpawner(game, self.center, spawner)
        self.assertEqual([goblin.name for goblin in factionGoblins(game, self.faction)], ["Goblin Builder"])

    def test_three_hits_put_a_bonfire_out(self):
        game = self.game
        expansion.place(game, self.center, expansion.Structure("bonfire", self.faction.id))
        self.faction.bonfires.append(self.center)
        for _ in range(expansion.BONFIRE_HITS - 1):
            expansion.hitStructure(game, self.center)
        self.assertEqual(game.grid[self.center][0], expansion.CAMP)
        expansion.hitStructure(game, self.center)
        self.assertEqual(game.grid[self.center], [0, 0])
        self.assertEqual(self.faction.bonfires, [])
        self.assertEqual(expansion.bonfires(game), [])

    def test_a_goblin_that_smashes_a_spawner_pockets_its_drops(self):
        game = self.game
        self.addSpawner()
        goblin = enemies.Goblin()
        goblin.materials = {}
        expansion.breakSpawner(game, self.center, goblin)
        self.assertEqual(game.grid[self.center], [0, 0])
        self.assertEqual(goblin.materials, dict(expansion.SPAWNER_DROPS))
        self.assertNotIn(self.center, expansion.camp(game)["structures"])

    def test_spawner_hits_crack_its_picture(self):
        spawner = self.addSpawner()
        expansion.crack(self.game, spawner, 10)
        self.assertTrue(spawner.brokenPoints)

    def test_food_counts_what_its_spawners_hold(self):
        spawner = self.addSpawner()
        spawner.food = 6
        self.assertEqual(expansion.foodCount(self.game, self.faction), 6)


if __name__ == "__main__":
    unittest.main()
