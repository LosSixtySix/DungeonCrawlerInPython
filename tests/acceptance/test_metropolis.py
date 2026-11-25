"""The Metropolis floor (metropolis.py, dwellers.py): a whole floor that is a city of insectoid Dwellers, its streets,
buildings, chests and themes, when it turns up, and the Dwellers going about their day.

Acceptance tests; the rest are in tests/unit/test_metropolis.py, tests/integration/test_metropolis.py."""
import os
import random
import tempfile
import unittest
from cruel.core import gamemanager
from cruel.world import metropolis
from cruel.world import themes
from cruel.world import wall
from tests import support
from tests.helpers.metropolis import FLOOR, ROW_LENGTH, WALL, cityGame, newCity


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

    def test_the_rock_is_drawn_and_dug_like_any_floors_stone(self):
        game = cityGame()
        rock = next(spot for spot in game.rooms[metropolis.YARD] if game.grid[spot][0] == WALL)
        self.assertEqual(game.grid[rock][2].name, wall.StoneWall().name)

    def test_city_walls_give_stone(self):
        random.seed(1)
        game = support.newGame()
        game.player.attributes["wisdom"] = 30  # (lucky: always something)
        drops = [gamemanager.loot.rollWall(wallKind().name, 30) for wallKind in (wall.HouseWall, wall.CityWall)]
        self.assertTrue(all(drop and drop[0][0] == "stone" for drop in drops))


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

    def test_lamp_posts_only_stand_in_open_road_so_they_never_block_the_way(self):
        for seed in range(10):
            city = newCity(seed)
            for spot, tile in city.grid.items():
                if tile[0] == metropolis.STREET_LIGHT:
                    for stepColumn in (-1, 0, 1):
                        for stepRow in (-1, 0, 1):
                            self.assertIn(spot + stepColumn + stepRow * ROW_LENGTH, city.roads)

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


if __name__ == "__main__":
    unittest.main()
