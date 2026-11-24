"""The Metropolis floor (metropolis.py, dwellers.py): a whole floor that is a city of insectoid Dwellers, its streets,
buildings, chests and themes, when it turns up, and the Dwellers going about their day."""
import math
import os
import random
import tempfile
import unittest
from unittest import mock

from cruel.core import gamemanager
from cruel.entities import enemies
from cruel.inventory import relics
from cruel.world import dwellers
from cruel.world import events
from cruel.world import metropolis
from cruel.world import peddler
from cruel.world import plants
from cruel.world import themes
from cruel.world import wall
from tests import support

FLOOR, WALL, CHEST, ENEMY = 0, 2, 3, 5
ROW_LENGTH, ROW_COUNT = 102, 76


def middleSpot():
    return ROW_LENGTH // 2 + (ROW_COUNT // 2) * ROW_LENGTH


def newCity(seed=1, playerSpot=None):
    random.seed(seed)
    return metropolis.buildCity(ROW_LENGTH, ROW_COUNT, middleSpot() if playerSpot is None else playerSpot)


def cityGame(seed=4):
    """A game walked down to a new floor that is a city."""
    random.seed(seed)
    game = support.newGame()
    game.saveGame = lambda *args, **kwargs: None
    game.metropolisNext = True
    game.goToNewLevel()
    return game


def dwellersOn(game, role=None):
    """(position, Dweller) for the Dwellers on the floor (of one role, if given)."""
    found = []
    for spot in game.EnemyPositions:
        tile = game.grid[spot]
        if tile[0] == ENEMY and dwellers.isDweller(tile[2]) and (role is None or tile[2].role == role):
            found.append((spot, tile[2]))
    return found


def ringOf(city, inside):
    """The tiles round a building's inside: its walls and its door."""
    insideSet = set(inside)
    ring = set()
    for spot in inside:
        for rowOffset in (-1, 0, 1):
            for columnOffset in (-1, 0, 1):
                other = spot + columnOffset + rowOffset * city.rowLength
                if other not in insideSet:
                    ring.add(other)
    return ring


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

    def test_every_building_has_exactly_one_door_onto_a_street(self):
        buildings = self.city.houses + self.city.mansions + [(shop["inside"], shop["door"]) for shop in self.city.shops]
        self.assertTrue(buildings)
        for inside, door in buildings:
            gaps = [spot for spot in ringOf(self.city, inside) if self.city.grid[spot][0] not in (WALL, metropolis.SHOP_SIGN)  # (a shop's sign is set in its wall)
                    and spot % ROW_LENGTH not in (0,) and any(abs(spot - insideSpot) in (1, ROW_LENGTH) for insideSpot in inside)]
            self.assertEqual(gaps, [door])
            outside = [spot for spot in metropolis.neighborsOf(self.city, door) if spot not in inside]
            open = self.city.rooms[metropolis.STREET] | self.city.rooms[metropolis.YARD]
            self.assertTrue(any(spot in open for spot in outside), "the door opens onto a road or a yard")

    def test_three_to_five_shops_each_a_different_kind(self):
        for seed in range(15):
            city = newCity(seed)
            kinds = [shop["kind"] for shop in city.shops]
            self.assertTrue(3 <= len(kinds) <= 5)
            self.assertEqual(len(set(kinds)), len(kinds))

    def test_roads_are_street_and_the_ground_between_buildings_is_yard(self):
        self.assertEqual(self.city.rooms[metropolis.STREET] & self.city.rooms[metropolis.YARD], set())
        for spot in self.city.rooms[metropolis.STREET]:
            self.assertIn(spot, self.city.roads)
        self.assertGreater(len(self.city.rooms[metropolis.YARD]), 100)

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
                self.assertIn(building.door, reached)

    def test_the_roads_are_rounded(self):
        """The inner ring road goes all the way round the plaza: there's road in every direction from the middle at
        about the same distance."""
        city = self.city
        middleColumn, middleRow = (ROW_LENGTH - 1) / 2, (ROW_COUNT - 1) / 2
        reachAcross, reachDown = ROW_LENGTH / 2 - 2, ROW_COUNT / 2 - 2
        share = metropolis.RING_ROADS[0]
        for eighth in range(8):
            angle = 6.2832 * eighth / 8
            found = False
            for wobble in (0.9, 0.95, 1.0, 1.05, 1.1):
                column = round(middleColumn + share * wobble * reachAcross * math.cos(angle))
                row = round(middleRow + share * wobble * reachDown * math.sin(angle))
                found = found or city.spot(column, row) in city.roads
            self.assertTrue(found, f"no ring road toward {eighth * 45} degrees")


class DwellerPlacementTests(unittest.TestCase):
    """Who lives where."""

    def setUp(self):
        self.city = newCity(3)

    def ofRole(self, role):
        return [(spot, dweller) for spot, dweller in self.city.dwellers.items() if dweller.role == role]

    def test_the_numbers_of_each_dweller(self):
        self.assertTrue(metropolis.CITIZENS[0] <= len(self.ofRole("citizen")) <= metropolis.CITIZENS[1])
        self.assertTrue(len(self.ofRole("noble")) <= metropolis.NOBLES[1])
        self.assertTrue(metropolis.GUARD_POSTS[0] <= len(self.ofRole("guard")) <= metropolis.GUARD_POSTS[1])
        self.assertEqual(len(self.ofRole("merchant")), len(self.city.shops))

    def test_guards_stand_at_posts_spread_over_the_roads(self):
        guards = self.ofRole("guard")
        for spot, guard in guards:
            self.assertEqual(guard.home, spot)
            self.assertIn(spot, self.city.roads)
        closest = min(math.hypot(spot % ROW_LENGTH - other % ROW_LENGTH, spot // ROW_LENGTH - other // ROW_LENGTH)
                      for spot, _ in guards for other, _ in guards if other != spot)
        self.assertGreater(closest, 8, "posts are spread out over the city")

    def test_each_merchant_keeps_a_shop_at_its_counter(self):
        counters = {shop["counter"]: shop["kind"] for shop in self.city.shops}
        for spot, merchant in self.ofRole("merchant"):
            self.assertEqual(counters[spot], merchant.shopKind)

    def test_citizens_start_on_streets_and_live_in_houses(self):
        houseTiles = {spot for inside, _ in self.city.houses for spot in inside}
        for spot, citizen in self.ofRole("citizen"):
            self.assertIn(spot, self.city.rooms[metropolis.STREET])
            self.assertIn(citizen.home, houseTiles)

    def test_nobles_live_in_the_noble_quarter(self):
        for spot, noble in self.ofRole("noble"):
            self.assertIn(noble.home, self.city.rooms[metropolis.NOBLE])

    def test_nobody_starts_on_or_beside_you(self):
        playerSpot = middleSpot()
        self.assertNotIn(playerSpot, self.city.dwellers)
        for besideYou in metropolis.neighborsOf(self.city, playerSpot):
            self.assertNotIn(besideYou, self.city.dwellers)


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


class LookTests(unittest.TestCase):
    """How the city looks."""

    def test_city_walls_are_drawn_in_their_rooms_wall_colors(self):
        game = cityGame()
        painter = game.painter
        for wallKind, room in ((wall.HouseWall, "House"), (wall.ShopWall, "Shop"), (wall.NobleWall, "Noble"), (wall.CityWall, "City")):
            self.assertEqual(painter.wallColor(wallKind().name, False), game.theme.colors[f"wall{room}"])

    def test_every_theme_draws_a_city(self):
        game = cityGame()
        for tile in game.grid.values():
            tile[1] = 1
        for data in themes.THEMES[metropolis.METROPOLIS]:
            game.setTheme(themes.Theme(metropolis.METROPOLIS, data))
            game.change = True
            game.setPositionsVisible()
            game.draw()

    def test_other_themes_color_city_rooms_like_stone(self):
        stoneTheme = themes.randomTheme("Mostly Stone")
        self.assertEqual(stoneTheme.colors["floorStreet"], stoneTheme.colors["floorStone"])

    def test_city_walls_give_stone(self):
        random.seed(1)
        game = support.newGame()
        game.player.attributes["wisdom"] = 30  # (lucky: always something)
        drops = [gamemanager.loot.rollWall(wallKind().name, 30) for wallKind in (wall.HouseWall, wall.CityWall)]
        self.assertTrue(all(drop and drop[0][0] == "stone" for drop in drops))


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


def buildingsOn(game):
    """The tiles of each building on a city floor (its walls, its sign, its inside and its door), worked out from
    the floor's rooms: every connected patch of House, Shop or Noble room is one building."""
    buildingTiles = set()
    for room in (metropolis.HOUSE, metropolis.SHOP, metropolis.NOBLE):
        buildingTiles |= game.rooms[room]
    buildings, seen = [], set()
    for start in buildingTiles:
        if start in seen:
            continue
        building, frontier = {start}, [start]
        seen.add(start)
        while frontier:
            spot = frontier.pop()
            for near in game.neighbors(spot):
                if near in buildingTiles and near not in seen:
                    seen.add(near)
                    building.add(near)
                    frontier.append(near)
        buildings.append(building)
    return buildings


class LightTests(unittest.TestCase):
    """Wall lamps outside along the roads and inside every building, and lamp posts round the plaza."""

    def setUp(self):
        self.city = newCity(5)

    def test_every_lamp_hangs_on_a_wall_on_its_side(self):
        for spot, lamp in self.city.wallLamps.items():
            stepColumn, stepRow = metropolis.SIDES[lamp.side]
            wallSpot = spot + stepColumn + stepRow * ROW_LENGTH
            self.assertIn(self.city.grid[wallSpot][0], (WALL, metropolis.SHOP_SIGN))

    def test_every_building_has_a_lamp_inside(self):
        for building in self.city.buildings:
            insideLamps = [spot for spot in building.inside if spot in self.city.wallLamps]
            self.assertTrue(insideLamps, f"a {building.kind} without a light")
            for spot in insideLamps:
                self.assertEqual(self.city.wallLamps[spot].radius, metropolis.ROOM_LAMP_RADIUS)

    def test_outside_lamps_line_the_roads_spaced_out_and_never_in_a_doorway(self):
        doorways = set()
        for building in self.city.buildings:
            doorways |= {building.door, *metropolis.neighborsOf(self.city, building.door)}
        outside = [spot for spot, lamp in self.city.wallLamps.items() if lamp.radius == metropolis.WALL_LAMP_RADIUS]
        self.assertGreater(len(outside), 10)
        for spot in outside:
            self.assertNotIn(spot, doorways)
            self.assertIn(spot, self.city.rooms[metropolis.STREET] | self.city.rooms[metropolis.YARD])
            for other in outside:
                if other != spot:
                    self.assertGreaterEqual(abs(spot % ROW_LENGTH - other % ROW_LENGTH) + abs(spot // ROW_LENGTH - other // ROW_LENGTH),
                                            metropolis.WALL_LAMP_SPACING)

    def test_wall_lamps_light_round_them(self):
        game = cityGame()
        spot, lamp = next(iter(metropolis.wallLampsHere(game).items()))
        game.updateFireLight()
        self.assertEqual(game.fireLight[spot], (spot, lamp.radius))

    def test_standing_under_a_wall_lamp_does_not_put_it_out(self):
        game = cityGame()
        spot = next(spot for spot, lamp in metropolis.wallLampsHere(game).items() if game.grid[spot][0] == FLOOR)
        support.placePlayer(game, spot)
        game.updateFireLight()
        self.assertEqual(game.fireLight[spot][0], spot)
        game.change = True
        game.setPositionsVisible()
        game.draw()  # (and it's drawn over you)

    def test_lamp_posts_stand_round_the_plaza(self):
        for lamp in self.city.grid:
            if self.city.grid[lamp][0] == metropolis.STREET_LIGHT:
                self.assertIn(lamp, self.city.plaza)

    def test_they_block_the_way_but_not_the_view(self):
        game = cityGame()
        lamp = metropolis.streetLights(game)[0]
        besideLamp = next(spot for spot in game.neighbors(lamp) if game.grid[spot][0] == FLOOR)
        support.placePlayer(game, besideLamp)
        game.movePlayer(lamp)
        self.assertEqual(game.playerPositionFlat, besideLamp)
        beyond = lamp + (lamp - besideLamp)
        farther = beyond + (beyond - lamp)
        for spot in (beyond, farther):  # (only the lamp is in the way: nobody standing about)
            game.grid[spot] = [FLOOR, 1]
        self.assertTrue(game.lineOfSight(besideLamp, farther))
        game.PlayerLookPosition = lamp
        self.assertEqual(game.lookingAt(), "Lamp post")

    def test_other_floors_have_none(self):
        random.seed(3)
        game = support.newGame(level=1)
        self.assertEqual(metropolis.streetLights(game), [])
        self.assertEqual(metropolis.wallLampsHere(game), {})

    def test_wall_lamps_are_saved_with_the_game(self):
        game = cityGame()
        lamps = {spot: lamp.side for spot, lamp in metropolis.wallLampsHere(game).items()}
        saveFile = os.path.join(tempfile.mkdtemp(), "city-save.pkl")
        gamemanager.gameManager.saveGame(game, saveFile)
        loaded = support.newGame()
        self.assertTrue(loaded.loadGame(saveFile))
        self.assertEqual({spot: lamp.side for spot, lamp in metropolis.wallLampsHere(loaded).items()}, lamps)


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
