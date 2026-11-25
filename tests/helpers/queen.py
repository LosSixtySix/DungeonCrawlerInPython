"""Helpers for the Dweller Queen's tests."""
import unittest

from cruel.world import queen
from tests import support
from tests.helpers.metropolis import cityGame

FLOOR = 0
FACINGS = {-1: 0, 1: 1}  # a step left or right: the player's direction (0 left, 1 right)


class BesideTheQueen(unittest.TestCase):
    """A real city with you standing beside its Queen, facing her, and everything on the floor seen."""

    def setUp(self):
        self.game = cityGame()
        self.anchor, self.queen = queen.courtOf(self.game)
        game = self.game
        body = set(game.footprint(self.anchor, 2))
        beside = [spot for tile in body for spot in game.neighbors(tile)
                  if spot not in body and game.grid[spot][0] == FLOOR and spot // game.rowLength in {tile // game.rowLength for tile in body}]
        self.besideHer = beside[0]
        self.towardHer = 1 if any(self.besideHer + 1 == tile for tile in body) else -1
        support.placePlayer(game, self.besideHer)
        game.player.playerDirection = FACINGS[self.towardHer]
        game.setLookPosition()
        for spot in game.grid:
            game.grid[spot][1] = 1
