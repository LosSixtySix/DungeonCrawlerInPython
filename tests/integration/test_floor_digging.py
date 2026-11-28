"""Breaking the floor (digging.py): Ctrl + interact digs at the floor tile you face. A floor is as tough as its room's
wall, and once it gives way it's a hole to the floor below. Trapped in an Overgrowth plant, Ctrl + interact breaks
the plant instead.

Integration tests."""
import os
import tempfile
import unittest

import pygame

from cruel.graphics import sprites
from cruel.world import digging, expansion, plants, wall
from tests.helpers.gamemanager import FLOOR, LEFT, PILE, WALL, keyDown, standInOpenFloor
from tests.support import newGame

PLANT = 8


def ctrlInteract(game):
    keyDown(game, game.settings.hotkeys["interact"], pygame.KMOD_LCTRL)


def tileColors(game, spot):
    """Every color drawn on the screen over the tile at spot, after drawing a frame."""
    for message in game.messageBools:  # (the big "Floor N" message darkens the screen at first)
        game.messageBools[message] = False
    game.painter.fade = 0
    game.setPositionsVisible()
    game.draw()
    tile = game.painter.tileOnScreen(spot)
    return {tuple(game.win.get_at((pixelX, pixelY)))[:3] for pixelX in range(tile.left, tile.right)
            for pixelY in range(tile.top, tile.bottom)}


def swingsToBreak(game, spot, dig):
    """How many swings dig(spot) takes before the tile at spot stops being what it was."""
    startKind = game.grid[spot][0]
    for swing in range(1, 500):
        dig(spot)
        if game.grid[spot][0] != startKind:
            return swing
    raise AssertionError("never broke")


class DiggingTests(unittest.TestCase):
    def setUp(self):
        self.game = newGame()
        self.playerSpot = standInOpenFloor(self.game, facing=LEFT)
        self.target = self.game.PlayerLookPosition
        self.setFloorType("Stone")

    def setFloorType(self, floorType):
        self.game.rooms = {room: set() for room in digging.FLOOR_WALLS}
        self.game.rooms[floorType] = {self.target}

    def test_a_swing_cracks_the_floor_you_face_and_takes_your_turn(self):
        ctrlInteract(self.game)
        crack = digging.cracksHere(self.game)[self.target]
        self.assertLess(crack.hp, wall.StoneWall().hp)
        self.assertEqual(self.game.grid[self.target][0], FLOOR)
        self.assertTrue(self.game.enemyMove)

    def test_the_floor_gives_way_into_a_hole(self):
        swingsToBreak(self.game, self.target, lambda spot: ctrlInteract(self.game))
        self.assertEqual(self.game.grid[self.target][0], expansion.HOLE)
        self.assertNotIn(self.target, digging.cracksHere(self.game))

    def test_every_floor_is_as_tough_as_its_rooms_wall(self):
        walls = {"Stone": wall.StoneWall, "Wood": wall.WoodWall, "Sand": wall.SandWall, "Gold": wall.GoldWall,
                 "Molten": wall.MoltenWall}
        for floorType, wallKind in walls.items():
            with self.subTest(floorType):
                self.game.grid[self.target] = [FLOOR, 1]
                self.setFloorType(floorType)
                floorSwings = swingsToBreak(self.game, self.target, lambda spot: digging.digFloor(self.game, spot))
                self.game.grid[self.target] = [WALL, 1, wallKind()]
                wallSwings = swingsToBreak(self.game, self.target, lambda spot: self.game.onInteract())
                self.assertEqual(floorSwings, wallSwings)

    def test_a_better_pick_digs_faster(self):
        bareHanded = swingsToBreak(self.game, self.target, lambda spot: digging.digFloor(self.game, spot))
        self.game.grid[self.target] = [FLOOR, 1]
        self.game.player.getWallDamage = lambda: 5
        self.assertLess(swingsToBreak(self.game, self.target, lambda spot: digging.digFloor(self.game, spot)), bareHanded)

    def test_only_bare_floor_can_be_dug(self):
        for tile in ([WALL, 1, wall.StoneWall()], [PILE, 1, []], [expansion.HOLE, 1]):
            with self.subTest(tile[0]):
                self.game.grid[self.target] = tile
                self.game.enemyMove = False
                ctrlInteract(self.game)
                self.assertEqual(self.game.grid[self.target][0], tile[0])
                self.assertFalse(self.game.enemyMove, "nothing to dig: no turn spent")

    def test_a_half_dug_floor_stays_half_dug_when_you_come_back(self):
        ctrlInteract(self.game)
        hpLeft = digging.cracksHere(self.game)[self.target].hp
        self.game.goToNewLevel()
        self.assertEqual(digging.cracksHere(self.game), {})
        self.game.changeLevel(0)
        self.assertEqual(digging.cracksHere(self.game)[self.target].hp, hpLeft)

    def test_cracks_are_saved_with_the_game(self):
        ctrlInteract(self.game)
        hpLeft = digging.cracksHere(self.game)[self.target].hp
        saveFile = os.path.join(tempfile.mkdtemp(), "save.pkl")
        self.game.saveGame(saveFile)
        self.game.floorCracks = {}
        self.assertTrue(self.game.loadGame(saveFile))
        self.assertEqual(digging.cracksHere(self.game)[self.target].hp, hpLeft)

    def test_the_cracks_grow_light_medium_heavy_as_it_is_dug(self):
        stages = []
        while self.game.grid[self.target][0] == FLOOR:
            digging.digFloor(self.game, self.target)
            stages.append(digging.crackStages(self.game).get(self.target))
        self.assertEqual(stages[-1], None, "the last swing opens the hole")
        seen = [stage for index, stage in enumerate(stages[:-1]) if index == 0 or stage != stages[index - 1]]
        self.assertEqual(seen, [0, 1, 2])

    def test_a_cracked_floor_shows_its_cracks(self):
        digging.digFloor(self.game, self.target)
        self.assertIn(sprites.ROPE_COLORS["c"], tileColors(self.game, self.target))


class TrappedTests(unittest.TestCase):
    def test_trapped_in_a_plant_ctrl_interact_breaks_the_plant_not_the_floor(self):
        game = newGame()
        standInOpenFloor(game, facing=LEFT)
        game.currentLocation = [PLANT, 1, plants.Plant.grown("emberroot")]
        self.assertIsNotNone(game.stuckIn())
        ctrlInteract(game)
        self.assertIsNone(game.stuckIn())
        self.assertEqual(game.currentLocation[0], FLOOR)
        self.assertNotIn(game.PlayerLookPosition, digging.cracksHere(game), "the floor ahead wasn't touched")


if __name__ == "__main__":
    unittest.main()
