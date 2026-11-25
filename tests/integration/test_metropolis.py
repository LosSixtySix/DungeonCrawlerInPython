"""The Metropolis floor (metropolis.py, dwellers.py): a whole floor that is a city of insectoid Dwellers, its streets,
buildings, chests and themes, when it turns up, and the Dwellers going about their day.

Integration tests; the rest are in tests/unit/test_metropolis.py, tests/acceptance/test_metropolis.py."""
import math
import random
import unittest
from unittest import mock
from cruel.core import gamemanager
from cruel.inventory import recipes
from cruel.inventory import relics
from cruel.world import dwellers
from cruel.world import events
from cruel.world import metropolis
from cruel.world import peddler
from cruel.world import plants
from cruel.world import themes
from cruel.world import wall
from tests import support
from tests.helpers.metropolis import CHEST, ENEMY, FLOOR, ROW_COUNT, ROW_LENGTH, WALL, buildingsOn, cityGame, dwellersOn, middleSpot, newCity, ringOf


class CityLayoutTests(unittest.TestCase):
    """What buildCity lays out."""

    def setUp(self):
        self.city = newCity()

    def test_a_city_wall_rings_the_whole_floor(self):
        for spot, tile in self.city.grid.items():
            column, row = spot % ROW_LENGTH, spot // ROW_LENGTH
            if column in (0, ROW_LENGTH - 1) or row in (0, ROW_COUNT - 1):
                self.assertIsInstance(tile[2], wall.CityWall)

    def test_you_arrive_on_a_street(self):
        for seed in range(10):
            playerSpot = random.Random(seed).randrange(ROW_LENGTH * 3, ROW_LENGTH * (ROW_COUNT - 3))
            if playerSpot % ROW_LENGTH in (0, 1, ROW_LENGTH - 2, ROW_LENGTH - 1):
                continue
            city = newCity(seed, playerSpot)
            self.assertIn(playerSpot, city.rooms[metropolis.STREET])
            self.assertEqual(city.grid[playerSpot][0], FLOOR)

    def test_every_building_has_two_doors_onto_streets_apart_from_each_other(self):
        self.assertTrue(self.city.buildings)
        for building in self.city.buildings:
            inside = building.inside
            gaps = [spot for spot in ringOf(self.city, inside) if self.city.grid[spot][0] not in (WALL, metropolis.SHOP_SIGN, metropolis.MINESHAFT)
                    and spot % ROW_LENGTH not in (0,) and any(abs(spot - insideSpot) in (1, ROW_LENGTH) for insideSpot in inside)]
            self.assertEqual(sorted(gaps), sorted(building.doors))
            self.assertEqual(len(building.doors), 2)
            door, backDoor = building.doors
            self.assertGreater(max(abs(door % ROW_LENGTH - backDoor % ROW_LENGTH), abs(door // ROW_LENGTH - backDoor // ROW_LENGTH)), 1, "not side by side")
            for each in building.doors:
                outside = [spot for spot in metropolis.neighborsOf(self.city, each) if spot not in inside]
                self.assertTrue(any(spot in self.city.rooms[metropolis.STREET] for spot in outside), "each door opens onto a street")

    def test_three_to_five_shops_each_a_different_kind(self):
        for seed in range(15):
            city = newCity(seed)
            kinds = [shop["kind"] for shop in city.shops]
            self.assertTrue(3 <= len(kinds) <= 5)
            self.assertEqual(len(set(kinds)), len(kinds))

    def test_roads_are_street_and_the_rock_between_buildings_is_yard(self):
        self.assertEqual(self.city.rooms[metropolis.STREET] & self.city.rooms[metropolis.YARD], set())
        for spot in self.city.rooms[metropolis.STREET]:
            self.assertIn(spot, self.city.roads)
        self.assertGreater(len(self.city.rooms[metropolis.YARD]), 100)
        for spot in self.city.rooms[metropolis.YARD]:
            self.assertIsInstance(self.city.grid[spot][2], wall.StoneWall)

    def test_the_city_is_rock_with_the_roads_carved_out(self):
        for seed in range(6):
            city = newCity(seed)
            buildingTiles = set()
            for building in city.buildings:
                buildingTiles |= building.tiles
            for spot, tile in city.grid.items():
                column, row = spot % ROW_LENGTH, spot // ROW_LENGTH
                if not city.inside(column, row) or spot in buildingTiles:
                    continue
                if spot in city.roads:
                    self.assertNotEqual(tile[0], WALL, "a road is open")
                else:
                    self.assertEqual(tile[0], WALL, "everything off the roads is rock")
                    self.assertIsInstance(tile[2], wall.StoneWall)

    def test_every_door_has_a_doorstep_carved_to_the_road(self):
        for seed in range(6):
            city = newCity(seed)
            for building in city.buildings:
                for door in building.doors:
                    outside = [near for near in metropolis.neighborsOf(city, door) if near not in building.tiles]
                    self.assertTrue(any(near in city.roads for near in outside), "the step outside each door is road")

    def test_digging_out_the_rock_leaves_yard_ground(self):
        game = cityGame()
        rock = next(spot for spot in game.rooms[metropolis.YARD] if game.grid[spot][0] == WALL)
        self.assertEqual(plants.floorOf(rock, game.rooms), metropolis.YARD)

    def test_the_rooms_do_not_overlap(self):
        rooms = [self.city.rooms[room] for room in (metropolis.STREET, metropolis.YARD, metropolis.HOUSE, metropolis.SHOP, metropolis.NOBLE)]
        for index, room in enumerate(rooms):
            for other in rooms[index + 1:]:
                self.assertFalse(room & other)

    def test_about_a_third_of_houses_have_a_chest_and_no_chest_holds_a_relic(self):
        houses = chests = 0
        for seed in range(12):
            city = newCity(seed)
            houses += len(city.houses)
            for inside, _ in city.houses:
                houseChests = [city.grid[spot][2] for spot in inside if city.grid[spot][0] == CHEST]
                chests += len(houseChests)
                for chest in houseChests:
                    self.assertIsInstance(chest, metropolis.CityChest)
                    self.assertFalse(any(relics.isRelic(thing) for thing in chest))
        self.assertAlmostEqual(chests / houses, metropolis.CHEST_CHANCE, delta=0.06)

    def test_every_door_can_be_walked_to_from_where_you_arrive(self):
        for seed in range(8):
            city = newCity(seed)
            reached, frontier = {middleSpot()}, [middleSpot()]
            while frontier:
                spot = frontier.pop()
                for near in metropolis.neighborsOf(city, spot):
                    if near not in reached and city.grid[near][0] in (FLOOR, ENEMY, CHEST):
                        reached.add(near)
                        frontier.append(near)
            for building in city.buildings:
                for door in building.doors:
                    self.assertIn(door, reached)

    def test_paths_are_rounded_or_square_and_both_turn_up(self):
        styles = set()
        for seed in range(6):
            city = newCity(seed)
            for style, tiles in city.paths:
                self.assertIn(style, metropolis.PATH_STYLES)
                styles.add(style)
        self.assertEqual(styles, set(metropolis.PATH_STYLES))

    def test_a_square_path_runs_straight_with_right_angle_corners(self):
        random.seed(4)
        for _ in range(20):
            end = (random.randint(20, 90), random.randint(20, 60))
            points = metropolis.squarePath(self.city, (10, 10), end)
            for (fromColumn, fromRow), (toColumn, toRow) in zip(points, points[1:]):
                self.assertTrue(fromColumn == toColumn or fromRow == toRow, "every step runs straight across or down")
            self.assertEqual(points[-1], end)

    def test_a_rounded_path_curves_and_still_arrives(self):
        random.seed(4)
        for _ in range(20):
            end = (random.randint(20, 90), random.randint(20, 60))
            points = metropolis.roundedPath(self.city, (10, 10), end)
            self.assertEqual(points[-1], end)
            headings = [math.atan2(toRow - fromRow, toColumn - fromColumn) for (fromColumn, fromRow), (toColumn, toRow)
                        in zip(points[:-1], points[1:-1])]
            self.assertGreater(max(headings) - min(headings), 0.3, "it bends on its way")

    def test_the_roads_are_one_network_from_where_you_arrive(self):
        city = self.city
        reached, frontier = {middleSpot()}, [middleSpot()]
        while frontier:
            spot = frontier.pop()
            for near in metropolis.neighborsOf(city, spot):
                if near in city.roads and near not in reached:
                    reached.add(near)
                    frontier.append(near)
        self.assertEqual(reached & city.roads, city.roads)

    def test_every_building_is_built_along_a_road(self):
        for building in self.city.buildings:
            outside = [near for near in metropolis.neighborsOf(self.city, building.door) if near not in building.inside]
            self.assertTrue(any(near in self.city.roads or any(far in self.city.roads for far in metropolis.neighborsOf(self.city, near))
                                for near in outside), "its door faces a road")


class AppearingTests(unittest.TestCase):
    """When a floor is a city."""

    def newFloor(self, depth, chance):
        random.seed(2)
        game = support.newGame(level=depth - 1)
        game.saveGame = lambda *args, **kwargs: None
        with mock.patch.object(metropolis, "APPEAR_CHANCE", chance):
            game.goToNewLevel()
        return game

    def test_from_floor_four_a_new_floor_can_be_a_city(self):
        self.assertNotEqual(self.newFloor(3, 1.0).proportion, metropolis.METROPOLIS)
        self.assertEqual(self.newFloor(4, 1.0).proportion, metropolis.METROPOLIS)
        self.assertNotEqual(self.newFloor(4, 0.0).proportion, metropolis.METROPOLIS)

    def test_the_console_makes_the_next_new_floor_a_city(self):
        random.seed(2)
        game = support.newGame()
        game.saveGame = lambda *args, **kwargs: None
        game.console.cmdMetropolis([])
        game.goToNewLevel()
        self.assertEqual(game.proportion, metropolis.METROPOLIS)
        game.goToNewLevel()
        self.assertNotEqual(game.proportion, metropolis.METROPOLIS, "only the one floor")

    def test_patience_still_drops_you_onto_an_ore_floor(self):
        random.seed(2)
        game = support.newGame()
        game.saveGame = lambda *args, **kwargs: None
        game.metropolisNext = True
        game.patienceFall()
        self.assertNotEqual(game.proportion, metropolis.METROPOLIS)

    def test_a_city_gets_a_metropolis_theme_and_says_so_when_you_arrive(self):
        game = cityGame()
        self.assertIn(game.theme.name, [data["name"] for data in themes.THEMES[metropolis.METROPOLIS]])
        self.assertTrue(game.floorSubtitle().startswith("Metropolis  -  "))

    def test_a_city_has_no_peddler_and_no_other_monsters(self):
        game = cityGame()
        for spot in game.EnemyPositions:
            self.assertTrue(dwellers.isDweller(game.grid[spot][2]))
        self.assertFalse(any(tile[0] == peddler.SIGNPOST for tile in game.grid.values()))

    def test_the_door_down_is_on_a_street(self):
        game = cityGame()
        self.assertIn(game.doorPositions[game.level], game.rooms[metropolis.STREET])

    def test_a_city_can_get_a_floor_event(self):
        random.seed(2)
        game = support.newGame()
        game.saveGame = lambda *args, **kwargs: None
        game.metropolisNext = True
        with mock.patch.object(events, "EVENT_CHANCE", 1.0):
            game.goToNewLevel()
        self.assertEqual(game.proportion, metropolis.METROPOLIS)
        self.assertIn(game.floorEvents[game.level]["id"], events.EVENTS)

    def test_no_wild_plants_spring_up_in_a_city(self):
        game = cityGame()
        for _ in range(40):
            game.enemyTurn()
        self.assertFalse(any(tile[0] == 8 for tile in game.grid.values()))


class CityEventTests(unittest.TestCase):
    """Overgrowth and Expansion on a city floor."""

    def plantCount(self, game):
        return sum(1 for tile in game.grid.values() if tile[0] == 8)

    def startSoon(self, game, eventId):
        game.floorEvents[game.level] = {"id": eventId, "turnsLeft": 1, "active": False}
        game.stepFloorEvent()

    def test_overgrowth_on_a_floor_with_no_plants_plants_three_patches(self):
        game = cityGame()
        self.assertEqual(self.plantCount(game), 0)
        realAddPatch = plants.addPatch
        patches = []
        with mock.patch.object(plants, "addPatch", lambda *args, **kwargs: patches.append(1) or realAddPatch(*args, **kwargs)):
            self.startSoon(game, "overgrowth")
        self.assertEqual(game.activeEvent(), "overgrowth")
        self.assertEqual(len(patches), events.OVERGROWTH_SEEDS)
        self.assertGreaterEqual(self.plantCount(game), events.OVERGROWTH_SEEDS)

    def test_the_overgrowth_plants_grow_and_are_kept_going(self):
        game = cityGame()
        self.startSoon(game, "overgrowth")
        for _ in range(30):
            game.enemyTurn()
        self.assertGreater(self.plantCount(game), 0)

    def test_plants_grow_on_every_city_floor(self):
        for floor in plants.CITY_FLOORS:
            self.assertTrue(plants.wildKinds(floor), f"nothing grows on {floor}")

    def test_overgrowth_plants_can_sprout_anywhere_in_the_city(self):
        game = cityGame()
        self.startSoon(game, "overgrowth")
        for _ in range(40):
            game.enemyTurn()
        floors = {plants.floorOf(spot, game.rooms) for spot, tile in game.grid.items() if tile[0] == 8}
        self.assertTrue(floors)
        self.assertLessEqual(floors, set(plants.CITY_FLOORS), "they grow on the city's floors")

    def test_you_can_plant_a_street_seed_on_a_street_but_not_another(self):
        game = cityGame()
        street = next(spot for spot in game.rooms[metropolis.STREET] if game.grid[spot][0] == FLOOR
                      and spot != game.playerPositionFlat)
        game.PlayerLookPosition = street
        recipesById = {recipe.id: recipe for recipe in recipes.RECIPES}
        for kind in ("bloodcap", "hearthmoss"):
            game.player.addMaterial(plants.PLANTS[kind]["seed"], 1)
        self.assertIsNone(game.craftProblem(recipesById["plant_bloodcap"]))
        self.assertEqual(game.craftProblem(recipesById["plant_hearthmoss"]), "it only grows on Yard or House floors")

    def test_which_kinds_can_grow_on_a_street(self):
        game = cityGame()
        street = next(spot for spot in game.rooms[metropolis.STREET] if game.grid[spot][0] == FLOOR
                      and spot not in (game.playerPositionFlat,))
        streetKind = next(kind for kind in plants.PLANTS if plants.growsOn(kind, metropolis.STREET))
        yardOnlyKind = next(kind for kind in plants.PLANTS if not plants.growsOn(kind, metropolis.STREET)
                            and plants.PLANTS[kind].get("cityFloors"))
        self.assertTrue(plants.canGrow(streetKind, street, game.grid, game.rooms))
        self.assertFalse(plants.canGrow(yardOnlyKind, street, game.grid, game.rooms))

    def test_overgrowth_on_a_floor_that_has_plants_plants_no_more(self):
        random.seed(5)
        game = support.newGame(level=1)
        before = self.plantCount(game)
        self.assertGreater(before, 0)
        self.startSoon(game, "overgrowth")
        self.assertEqual(self.plantCount(game), before)

    def test_the_console_starts_overgrowth_with_its_seeds_too(self):
        game = cityGame()
        game.console.cmdEvent(["overgrowth"])
        self.assertEqual(game.activeEvent(), "overgrowth")
        self.assertGreater(self.plantCount(game), 0)

    def test_expansion_brings_a_war_band_into_the_city(self):
        game = cityGame()
        self.startSoon(game, "expansion")
        game.stepFloorEvent()
        goblins = [spot for spot in game.EnemyPositions if getattr(game.grid[spot][2], "faction", None) is not None]
        self.assertEqual(len(goblins), len(gamemanager.expansion.WARBAND))


class CalmDwellerTests(unittest.TestCase):
    """The Dwellers going about their day."""

    def setUp(self):
        self.game = cityGame()

    def test_they_walk_about(self):
        before = {id(dweller): spot for spot, dweller in dwellersOn(self.game)}
        for _ in range(10):
            self.game.enemyTurn()
        after = {id(dweller): spot for spot, dweller in dwellersOn(self.game)}
        moved = sum(1 for key, spot in after.items() if before.get(key) != spot)
        self.assertGreater(moved, len(after) // 3)

    def test_merchants_stay_at_their_counters(self):
        counters = {id(merchant): spot for spot, merchant in dwellersOn(self.game, "merchant")}
        for _ in range(20):
            self.game.enemyTurn()
        for spot, merchant in dwellersOn(self.game, "merchant"):
            self.assertEqual(counters[id(merchant)], spot)

    def test_guards_patrol_near_their_posts(self):
        game = self.game
        for spot, guard in dwellersOn(game, "guard"):
            for _ in range(20):
                patrolSpot = dwellers.pickGoal(game, spot, guard)
                self.assertLessEqual(dwellers.distance(game, patrolSpot, guard.home), dwellers.WANDER_REACH["guard"] * 1.5)
        for _ in range(40):
            game.enemyTurn()
        for spot, guard in dwellersOn(game, "guard"):
            # (a detour round a building, or a citizen swapping past it, can take it a few tiles further for a while)
            self.assertLessEqual(dwellers.distance(game, spot, guard.home), 10)

    def test_calm_dwellers_never_hurt_you(self):
        game = self.game
        citizenSpot, citizen = dwellersOn(game, "citizen")[0]
        support.placePlayer(game, next(spot for spot in game.neighbors(citizenSpot) if game.grid[spot][0] == FLOOR))
        game.player.damageTaken = 0
        for _ in range(20):
            game.enemyTurn()
        self.assertEqual(game.player.damageTaken, 0)

    def test_nobody_is_lost_or_doubled_as_they_walk(self):
        count = len(dwellersOn(self.game))
        for _ in range(30):
            self.game.enemyTurn()
        self.assertEqual(len(dwellersOn(self.game)), count)


class BuildingStyleTests(unittest.TestCase):
    """Each theme builds its own shape of building."""

    def test_each_style_has_its_own_shape(self):
        square = metropolis.shapeCells("square", 7, 7)
        self.assertEqual(len(square), 49, "a square fills its box")
        for style in ("round", "oblong", "rounded", "hexagon"):
            self.assertNotIn((0, 0), metropolis.shapeCells(style, 7, 7), f"{style} has no sharp corner")
        self.assertLess(len(metropolis.shapeCells("round", 7, 7)), len(metropolis.shapeCells("rounded", 7, 7)),
                        "rounded corners are softer than a circle")
        hexagon = metropolis.shapeCells("hexagon", 9, 7)
        self.assertIn((0, 3), hexagon)  # its point, half way down its left side
        self.assertNotIn((0, 0), hexagon)

    def test_round_buildings_are_as_wide_as_they_are_tall_and_oblong_ones_are_not(self):
        random.seed(1)
        for _ in range(20):
            width, height = metropolis.buildingSize("round", metropolis.HOUSE_SIZE)
            self.assertEqual(width, height)
            width, height = metropolis.buildingSize("oblong", metropolis.HOUSE_SIZE)
            self.assertGreaterEqual(max(width, height) / min(width, height), 1.25)

    def test_every_theme_has_a_style_and_the_city_is_built_in_it(self):
        self.assertEqual(set(metropolis.STYLES), {data["name"] for data in themes.THEMES[metropolis.METROPOLIS]})
        for themeName, style in metropolis.STYLES.items():
            random.seed(3)
            game = support.newGame()
            game.saveGame = lambda *args, **kwargs: None
            game.metropolisNext = True
            game.forcedTheme = themeName
            game.goToNewLevel()
            self.assertEqual(game.theme.name, themeName)
            for building in buildingsOn(game):
                columns = [spot % ROW_LENGTH for spot in building]
                rows = [spot // ROW_LENGTH for spot in building]
                corner = min(rows) * ROW_LENGTH + min(columns)
                if style == "square":
                    self.assertIn(corner, building, f"{themeName}: square corners")
                else:
                    self.assertNotIn(corner, building, f"{themeName}: no sharp corners")


class SavingTests(unittest.TestCase):
    def test_a_city_floor_survives_going_down_and_back_up(self):
        game = cityGame()
        count = len(dwellersOn(game))
        game.grid[game.playerPositionFlat] = game.currentLocation
        game.playerPositionFlat = game.doorPositions[game.level]
        game.currentLocation = list(game.grid[game.playerPositionFlat])
        game.onOpenDoor()
        game.changeLevel(game.level - 1)
        self.assertEqual(game.proportion, metropolis.METROPOLIS)
        self.assertEqual(len(dwellersOn(game)), count)


if __name__ == "__main__":
    unittest.main()
