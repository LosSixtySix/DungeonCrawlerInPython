"""Organizers: the enemies that clear a spot and build spirals, rings, squares and Demise gliders (organizers.py)."""
import random
import unittest

from cruel.entities import enemies
from cruel.world import organizers
from cruel.world import plants
from cruel.world import wall
from tests import support


def blankFloor(game):
    """Turns the game's floor into open Stone floor with no enemies, the player in the top-left corner."""
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


def addOrganizer(game, position, organizerClass):
    organizer = organizerClass()
    organizer.rest = 0
    game.grid[position] = [5, 0, organizer]
    game.EnemyPositions.add(position)
    return organizer


def emptyContext():
    return {"protected": {}, "claimed": set(), "targets": []}


class ShapeTests(unittest.TestCase):
    """The pattern shapes, as offsets from their center."""

    def test_a_spiral_has_one_wall_per_step_of_each_longer_leg(self):
        walls, inside = organizers.spiralShape(3)
        self.assertEqual(len(walls), 1 + 2 + 3 + 4)
        self.assertEqual(inside, set())

    def test_a_ring_is_hollow_with_exactly_one_compass_doorway(self):
        random.seed(1)
        radius = 5
        walls, inside = organizers.circleShape(radius)
        compassPoints = {(radius, 0), (-radius, 0), (0, radius), (0, -radius)}
        self.assertEqual(len(compassPoints - walls), 1)
        self.assertFalse(walls & inside)
        self.assertIn((0, 0), inside)

    def test_a_square_is_an_outline_with_a_doorway_in_one_side(self):
        random.seed(2)
        walls, inside = organizers.squareShape(5)
        self.assertEqual(len(walls), 16 - 1)
        self.assertEqual(len(inside), 9)
        doorways = {(0, -2), (0, 2), (-2, 0), (2, 0)} - walls
        self.assertEqual(len(doorways), 1)

    def test_a_glider_has_five_cells_all_on_its_wood(self):
        cells, wood = organizers.gliderShape(1, 1)
        self.assertEqual(len(cells), 5)
        self.assertTrue(cells <= wood)
        pointedLeftUp, _ = organizers.gliderShape(-1, -1)
        self.assertEqual(pointedLeftUp, {(-column, -row) for column, row in cells})

    def test_a_margin_adds_every_tile_around_the_shape(self):
        self.assertEqual(len(organizers.withMargin({(0, 0)})), 9)
        self.assertEqual(len(organizers.withMargin({(0, 0), (1, 0)})), 12)


class HelperTests(unittest.TestCase):
    """Small helpers: what an organizer can step on, and turning offsets into tiles."""

    def setUp(self):
        self.game = support.newGame()
        blankFloor(self.game)

    def test_enemies_can_step_on_floor_piles_and_walkable_plants_only(self):
        self.assertTrue(organizers.passable([0, 0]))
        self.assertTrue(organizers.passable([9, 0, []]))
        self.assertFalse(organizers.passable([2, 0, wall.StoneWall()]))
        self.assertTrue(organizers.passable([8, 0, plants.Plant("glowcap")]))
        self.assertFalse(organizers.passable([8, 0, plants.Plant("bloodcap")]))
        demiseTile = [8, 0, plants.Plant(organizers.DEMISE)]
        self.assertTrue(organizers.passable(demiseTile))
        self.assertFalse(organizers.passable(demiseTile, demise=False))
        self.assertTrue(organizers.isDemise(demiseTile))

    def test_offsets_that_fall_off_the_map_give_none(self):
        game = self.game
        center = middleOf(game)
        self.assertEqual(organizers.toTiles(game, center, {(1, 0), (0, 1)}), {center + 1, center + game.rowLength})
        leftEdge = (center // game.rowLength) * game.rowLength
        self.assertIsNone(organizers.toTiles(game, leftEdge, {(-1, 0)}))

    def test_manhattan_distance_counts_steps(self):
        game = self.game
        center = middleOf(game)
        self.assertEqual(organizers.manhattan(game, center, center + 3 + 2 * game.rowLength), 5)

    def test_reachable_walks_around_walls(self):
        game = self.game
        center = middleOf(game)
        game.grid[center + 1] = [2, 0, wall.StoneWall()]
        distances, cameFrom = organizers.reachable(game, center)
        self.assertNotIn(center + 1, distances)
        self.assertEqual(distances[center + 2], 4)  # around the wall
        self.assertEqual(distances[center - 1], 1)
        firstStep = organizers.firstStep(cameFrom, center, center + 2)
        self.assertIn(firstStep, game.neighbors(center))


class PlanTests(unittest.TestCase):
    """layOut: where a pattern may go."""

    def setUp(self):
        random.seed(3)
        self.game = support.newGame()
        blankFloor(self.game)
        self.center = middleOf(self.game)

    def test_a_square_plan_clears_room_around_its_walls(self):
        squareOrganizer = enemies.SquareOrganizer()
        plan = organizers.layOut(self.game, self.center, squareOrganizer, emptyContext())
        self.assertIsNotNone(plan)
        self.assertTrue(plan["wallSet"] <= plan["footprint"])
        self.assertEqual(plan["clear"], plan["footprint"] - plan["wallSet"])
        self.assertFalse(plan["outside"] & plan["inside"])
        self.assertEqual(plan["walls"], sorted(plan["wallSet"]))

    def test_no_plan_over_the_player_a_chest_or_another_plan(self):
        game, center = self.game, self.center
        squareOrganizer = enemies.SquareOrganizer()
        game.grid[center + 1] = [3, 0, []]
        self.assertIsNone(organizers.layOut(game, center, squareOrganizer, emptyContext()))
        game.grid[center + 1] = [0, 0]
        claimedContext = emptyContext()
        claimedContext["claimed"] = {center}
        self.assertIsNone(organizers.layOut(game, center, squareOrganizer, claimedContext))
        cornerPlan = organizers.layOut(game, game.rowLength + 1, squareOrganizer, emptyContext())
        self.assertIsNone(cornerPlan)  # the player stands at the top-left corner

    def test_a_plant_organizer_aims_its_glider_at_the_nearest_organizer(self):
        game, center = self.game, self.center
        target = center + 10 + 10 * game.rowLength  # down and to the right
        context = emptyContext()
        context["targets"] = [target]
        plan = organizers.layOut(game, center, enemies.PlantOrganizer(), context)
        expectedCells, _wood = organizers.gliderShape(1, 1)
        self.assertEqual(plan["cells"], organizers.toTiles(game, center, expectedCells))
        self.assertEqual(plan["wallSet"], set())


class BuildingTests(unittest.TestCase):
    """Organizers taking turns on an open floor."""

    def setUp(self):
        random.seed(4)
        self.game = support.newGame()
        blankFloor(self.game)
        self.center = middleOf(self.game)

    def runUntilBuilt(self, organizer, turns=400):
        for _ in range(turns):
            self.game.MoveEnemies()
            if organizer.built:
                return

    def test_a_square_organizer_finishes_a_square_of_real_walls(self):
        squareOrganizer = addOrganizer(self.game, self.center, enemies.SquareOrganizer)
        self.runUntilBuilt(squareOrganizer)
        # a 5-wide square has 16 walls, a 6-wide one 20, less one for the doorway
        self.assertIn(len(squareOrganizer.built), (15, 19))
        for wallPosition in squareOrganizer.built:
            tile = self.game.grid[wallPosition]
            self.assertEqual(tile[0], 2)
            self.assertIsInstance(tile[2], wall.StoneWall)  # the room's wall type
        self.assertEqual(squareOrganizer.placed, squareOrganizer.built)
        self.assertIsNone(squareOrganizer.plan)
        low, high = organizers.REST_TURNS
        self.assertTrue(low <= squareOrganizer.rest <= high)

    def test_an_organizer_never_walls_itself_in(self):
        circleOrganizer = addOrganizer(self.game, self.center, enemies.CircleOrganizer)
        self.runUntilBuilt(circleOrganizer, turns=600)
        self.assertTrue(circleOrganizer.built)
        organizerSpot = next(iter(self.game.EnemyPositions))
        distances, _ = organizers.reachable(self.game, organizerSpot)
        self.assertGreater(len(distances), 100)

    def test_a_plant_organizer_lays_wood_and_sows_a_glider(self):
        plantOrganizer = addOrganizer(self.game, self.center, enemies.PlantOrganizer)
        sown = False
        for _ in range(400):
            self.game.MoveEnemies()
            if any(organizers.isDemise(tile) for tile in self.game.grid.values()):
                sown = True
                break
        self.assertTrue(sown)
        self.assertTrue(self.game.rooms["Wood"])
        demiseTiles = [position for position, tile in self.game.grid.items() if organizers.isDemise(tile)]
        self.assertEqual(len(demiseTiles), 5)
        self.assertTrue(set(demiseTiles) <= self.game.rooms["Wood"])
        self.assertIsInstance(plantOrganizer, enemies.PlantOrganizer)

    def test_an_organizer_touching_demise_becomes_a_plant_organizer(self):
        game, center = self.game, self.center
        squareOrganizer = enemies.SquareOrganizer()
        game.grid[center + 1 + game.rowLength] = [8, 0, plants.Plant(organizers.DEMISE)]  # a diagonal touch counts
        position, newSelf = organizers.takeTurn(game, center, squareOrganizer, emptyContext())
        self.assertEqual(position, center)
        self.assertIsInstance(newSelf, enemies.PlantOrganizer)

    def test_overgrow_turns_an_organizer_on_the_grid_only_once(self):
        game, center = self.game, self.center
        addOrganizer(game, center, enemies.SpiralOrganizer)
        self.assertTrue(organizers.overgrow(game, center))
        self.assertIsInstance(game.grid[center][2], enemies.PlantOrganizer)
        self.assertFalse(organizers.overgrow(game, center))

    def test_an_organizer_beside_you_attacks_instead_of_working(self):
        game = self.game
        support.placePlayer(game, self.center + 1)
        squareOrganizer = enemies.SquareOrganizer()
        squareOrganizer.rest = 0
        position, sameOrganizer = organizers.takeTurn(game, self.center, squareOrganizer, emptyContext())
        self.assertEqual(position, self.center)
        self.assertIs(sameOrganizer, squareOrganizer)
        self.assertIsNone(squareOrganizer.plan)

    def test_gather_collects_each_teams_walls_and_the_glider_targets(self):
        game, center = self.game, self.center
        squareOrganizer = addOrganizer(game, center, enemies.SquareOrganizer)
        squareOrganizer.built = {center + 5}
        addOrganizer(game, center + 20, enemies.PlantOrganizer)
        context = organizers.gather(game)
        self.assertEqual(context["protected"]["square"], {center + 5})
        self.assertEqual(context["targets"], [center])
        self.assertIn(center + 5, context["claimed"])


class BrokenWallTests(unittest.TestCase):
    """What an organizer does when someone breaks a wall it built."""

    def setUp(self):
        self.game = support.newGame()
        blankFloor(self.game)
        self.center = middleOf(self.game)

    def buildersWall(self, organizerClass, wallOffset):
        organizer = addOrganizer(self.game, self.center, organizerClass)
        wallPosition = self.center + wallOffset
        organizers.placedBy(organizer).add(wallPosition)
        return organizer, wallPosition

    def test_breaking_a_nearby_organizer_wall_enrages_it(self):
        squareOrganizer, wallPosition = self.buildersWall(enemies.SquareOrganizer, 3)
        organizers.wallBroken(self.game, wallPosition, "player")
        self.assertEqual(squareOrganizer.aggro, "player")
        self.assertNotIn(wallPosition, squareOrganizer.placed)

    def test_an_organizer_too_far_from_its_broken_wall_just_forgets_it(self):
        squareOrganizer, wallPosition = self.buildersWall(enemies.SquareOrganizer, organizers.AGGRO_RANGE + 1)
        organizers.wallBroken(self.game, wallPosition, "player")
        self.assertIsNone(squareOrganizer.aggro)
        self.assertNotIn(wallPosition, squareOrganizer.placed)

    def test_an_organizer_breaking_its_own_wall_does_not_get_angry(self):
        squareOrganizer, wallPosition = self.buildersWall(enemies.SquareOrganizer, 2)
        organizers.wallBroken(self.game, wallPosition, squareOrganizer)
        self.assertIsNone(squareOrganizer.aggro)

    def test_an_angry_organizer_calms_down_when_its_target_is_gone(self):
        squareOrganizer, _ = self.buildersWall(enemies.SquareOrganizer, 2)
        squareOrganizer.aggro = enemies.Goblin()  # not on the map any more
        position = organizers.chase(self.game, self.center, squareOrganizer, emptyContext())
        self.assertEqual(position, self.center)
        self.assertIsNone(squareOrganizer.aggro)

    def test_an_angry_organizer_walks_toward_the_player(self):
        game = self.game
        support.placePlayer(game, self.center + 6)
        squareOrganizer, _ = self.buildersWall(enemies.SquareOrganizer, 2)
        squareOrganizer.aggro = "player"
        game.grid[self.center].pop()  # lifted off its tile, as MoveEnemies does
        position = organizers.chase(game, self.center, squareOrganizer, emptyContext())
        self.assertEqual(position, self.center + 1)


if __name__ == "__main__":
    unittest.main()
