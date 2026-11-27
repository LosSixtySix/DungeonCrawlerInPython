"""Sight and light remembered between redraws (gameManager.setPositionsVisible with sightmemory.py): it gives the
same as working everything out afresh, and a redraw with nothing changed works nothing out.

Integration tests; the rest are in tests/unit/test_sightmemory.py."""
import random
import unittest
from unittest import mock

from cruel.inventory import items
from cruel.world import sight
from tests import support
from tests.helpers.expansion import blankFloor
from tests.helpers.metropolis import cityGame

FLOOR, WALL, PILE = 0, 2, 9


def afresh(game):
    """(your sight, fire light, glow light, lit tiles seen from afar, Darkvision) worked out the old way, with
    nothing remembered."""
    seen = game.rayCircleVision(game.playerPositionFlat, game.player.getVisionRange(), 1)
    game.updateFireLight()
    game.updateGlowLight()
    fireLight, glowLight = dict(game.fireLight), dict(game.glowLight)
    return seen, fireLight, glowLight, game.seenFromAfar(set(fireLight) | set(glowLight), seen), game.darkvisionSight(seen)


def remembered(game):
    """The same, as setPositionsVisible works them out now."""
    game.setPositionsVisible()
    seen = game.yourSight(game.player.getVisionRange(), game.sightMemory)
    return seen, dict(game.fireLight), dict(game.glowLight), \
        game.seenFromAfar(set(game.fireLight) | set(game.glowLight), seen, game.sightMemory), game.darkSight


class SameAsAfreshTests(unittest.TestCase):
    def assertSame(self, game):
        self.assertEqual(remembered(game), afresh(game))

    def test_in_a_city_with_the_dwellers_about(self):
        game = cityGame()
        for _ in range(40):
            game.enemyTurn()
            self.assertSame(game)

    def test_with_smoke_darkvision_and_glowrocks_and_walls_broken(self):
        random.seed(5)
        game = support.newGame(level=2)
        game.saveGame = lambda *arguments, **keywords: None
        here = game.playerPositionFlat
        floors = [spot for spot, tile in game.grid.items() if tile[0] == FLOOR]
        for spot in random.sample(floors, 6):
            game.grid[spot] = [PILE, 0, items.ItemPile([items.consumable("Glowrock", 0, items.GLOW)])]
        with mock.patch.object(game.player, "hasEffect", lambda tag: tag == "darkvision"):
            for turn in range(30):
                game.enemyTurn()
                if turn % 5 == 0:
                    game.smoke = {here + game.rowLength * 2 + turn % 3: 3}
                if turn % 7 == 0:
                    walls = [spot for spot, tile in game.grid.items() if tile[0] == WALL]
                    game.grid[min(walls, key=lambda spot: abs(spot - here))] = [FLOOR, 1]
                self.assertSame(game)


class RedrawTests(unittest.TestCase):
    def test_a_redraw_with_nothing_changed_works_nothing_out(self):
        game = cityGame()
        game.enemyTurn()
        game.setPositionsVisible()
        before = {spot: tile[1] for spot, tile in game.grid.items()}
        with mock.patch.object(sight, "fieldOfView", side_effect=AssertionError("worked out again")):
            game.setPositionsVisible()
        self.assertEqual({spot: tile[1] for spot, tile in game.grid.items()}, before)

    def test_a_wall_broken_beside_you_shows_what_is_behind_it_at_once(self):
        game = support.newGame()
        blankFloor(game)
        here = 30 + 20 * game.rowLength
        support.placePlayer(game, here)
        game.currentLocation = [FLOOR, 1]
        game.grid[here + 1] = [WALL, 0]
        game.setPositionsVisible()
        self.assertNotEqual(game.grid[here + 2][1], 1)
        game.grid[here + 1] = [FLOOR, 1]  # (broken, no turn taken yet)
        game.setPositionsVisible()
        self.assertEqual(game.grid[here + 2][1], 1)

    def test_smoke_rising_beside_you_hides_what_is_behind_it_at_once(self):
        game = support.newGame()
        blankFloor(game)
        here = 30 + 20 * game.rowLength
        support.placePlayer(game, here)
        game.currentLocation = [FLOOR, 1]
        game.smoke = {}
        game.setPositionsVisible()
        self.assertEqual(game.grid[here + 2][1], 1)
        game.smoke = {here + 1: 5}
        game.setPositionsVisible()
        self.assertNotEqual(game.grid[here + 2][1], 1)


if __name__ == "__main__":
    unittest.main()
