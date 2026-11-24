"""The Metropolis floor (metropolis.py, dwellers.py): a whole floor that is a city of insectoid Dwellers, its streets,
buildings, chests and themes, when it turns up, and the Dwellers going about their day."""
import random
import unittest
from unittest import mock

from cruel.core import gamemanager
from cruel.entities import enemies
from cruel.inventory import relics
from cruel.world import dwellers
from cruel.world import metropolis
from cruel.world import peddler
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
            gaps = [spot for spot in ringOf(self.city, inside) if self.city.grid[spot][0] != WALL
                    and spot % ROW_LENGTH not in (0,) and any(abs(spot - insideSpot) in (1, ROW_LENGTH) for insideSpot in inside)]
            self.assertEqual(gaps, [door])
            outside = [spot for spot in metropolis.neighborsOf(self.city, door) if spot not in inside]
            self.assertTrue(any(spot in self.city.rooms[metropolis.STREET] for spot in outside), "the door opens onto a street")

    def test_three_to_five_shops_each_a_different_kind(self):
        for seed in range(15):
            city = newCity(seed)
            kinds = [shop["kind"] for shop in city.shops]
            self.assertTrue(3 <= len(kinds) <= 5)
            self.assertEqual(len(set(kinds)), len(kinds))

    def test_the_rooms_do_not_overlap(self):
        rooms = [self.city.rooms[room] for room in (metropolis.STREET, metropolis.HOUSE, metropolis.SHOP, metropolis.NOBLE)]
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

    def test_the_street_grid_always_runs_through_a_given_spot(self):
        for coordinate in range(2, ROW_COUNT - 3):
            lines = metropolis.streetLines(ROW_COUNT, coordinate)
            self.assertTrue(any(line <= coordinate < line + metropolis.STREET_WIDTH for line in lines), coordinate)


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

    def test_guards_stand_at_posts_on_street_corners(self):
        columns, rows = self.city.streetLines
        corners = {self.city.spot(column, row) for column in columns for row in rows}
        for spot, guard in self.ofRole("guard"):
            self.assertEqual(guard.home, spot)
            self.assertIn(spot, corners)

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

    def test_a_city_has_no_floor_event_no_peddler_and_no_other_monsters(self):
        game = cityGame()
        self.assertNotIn(game.level, game.floorEvents)
        for spot in game.EnemyPositions:
            self.assertTrue(dwellers.isDweller(game.grid[spot][2]))
        self.assertFalse(any(tile[0] == peddler.SIGNPOST for tile in game.grid.values()))

    def test_the_door_down_is_on_a_street(self):
        game = cityGame()
        self.assertIn(game.doorPositions[game.level], game.rooms[metropolis.STREET])

    def test_no_wild_plants_spring_up_in_a_city(self):
        game = cityGame()
        for _ in range(40):
            game.enemyTurn()
        self.assertFalse(any(tile[0] == 8 for tile in game.grid.values()))


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
