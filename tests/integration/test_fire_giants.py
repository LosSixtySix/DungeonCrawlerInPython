"""Fire Giants: 2x2 enemies on the Scorched Depths. They spawn near and guard the center chest, reach 3 tiles,
take one hit from an explosion and ignore fire. Also covers enemies turning to face the way they step."""
import pickle
import random
import unittest

from tests import support
from cruel.entities import enemies

ENEMY = 5
FACING_LEFT, FACING_RIGHT, FACING_UP, FACING_DOWN = 0, 1, 2, 3


def giantsOn(game):
    """Every Fire Giant on the floor, with the tiles it covers."""
    found = {}
    for spot, tile in game.grid.items():
        if tile[0] == ENEMY and len(tile) > 2 and isinstance(tile[2], enemies.FireGiant):
            giant = tile[2]
            found.setdefault(id(giant), (giant, set()))[1].add(spot)
    return list(found.values())


def scorchedGame():
    random.seed(7)
    game = support.newGame(level=1)
    game.enterScorched()
    return game


def tilesApart(game, spot, other):
    return max(abs(spot % game.rowLength - other % game.rowLength), abs(spot // game.rowLength - other // game.rowLength))


class FireGiantTest(unittest.TestCase):
    """Fire Giants on the Scorched Depths."""

    def assertGiantsAreWhole(self, game):
        """Each giant fills exactly its four tiles, and only its anchor (top-left) tile is listed as an enemy."""
        for giant, coveredTiles in giantsOn(game):
            self.assertEqual(coveredTiles, set(game.footprint(giant.anchor)))
            self.assertIn(giant.anchor, game.EnemyPositions)
            self.assertFalse((coveredTiles - {giant.anchor}) & game.EnemyPositions)

    def test_two_or_three_giants_spawn_whole(self):
        game = scorchedGame()
        self.assertIn(len(giantsOn(game)), (2, 3))
        self.assertGiantsAreWhole(game)

    def test_giants_spawn_near_the_center_chest(self):
        game = scorchedGame()
        farthest = enemies.GIANT_SPAWN[1] + 2  # (+2: the anchor is one corner of a 2x2 body)
        for giant, _ in giantsOn(game):
            self.assertLessEqual(tilesApart(game, giant.anchor, game.centerTile()), farthest)

    def test_a_giant_comes_for_you_and_hits_you(self):
        game = scorchedGame()
        giant = giantsOn(game)[0][0]
        support.placePlayer(game, game.openSpot(giant.anchor - 6))
        game.player.damageTaken = -1000  # so the player can't die during the test
        turnsItMoved = turnsItHitYou = 0
        for _ in range(60):
            damageBefore, anchorBefore = game.player.damageTaken, giant.anchor
            game.MoveEnemies()
            self.assertGiantsAreWhole(game)
            turnsItMoved += giant.anchor != anchorBefore
            turnsItHitYou += game.player.damageTaken > damageBefore
        self.assertGreater(turnsItMoved, 0)
        self.assertGreater(turnsItHitYou, 0)

    def test_an_explosion_hits_a_giant_once_and_fire_does_nothing(self):
        game = scorchedGame()
        giant = giantsOn(game)[1][0]
        hpBefore = giant.hp
        game.land({"landing": giant.anchor, "effect": "Explosive", "power": 5})
        self.assertTrue(giant.hp == hpBefore - 5 or giant.hp <= 0, "one hit, not one per tile")
        hpBefore = giant.hp
        game.land({"landing": giant.anchor, "effect": "Fire", "power": 5})
        self.assertEqual(giant.hp, hpBefore)

    def test_saving_keeps_one_giant_across_its_four_tiles(self):
        game = scorchedGame()
        giant = giantsOn(game)[0][0]
        reloadedGrid = pickle.loads(pickle.dumps(game.grid))
        giantsAfterReload = {id(reloadedGrid[spot][2]) for spot in game.footprint(giant.anchor)}
        self.assertEqual(len(giantsAfterReload), 1)

    def test_a_giant_reaches_three_tiles_but_not_four(self):
        game = scorchedGame()
        giant = giantsOn(game)[0][0]
        for spot, tile in game.grid.items():  # clear the floor: no walls, chests or doors in the way
            if tile[0] in (2, 3, 4):
                game.grid[spot] = [0, 1]
        for otherGiant, _ in giantsOn(game):
            if otherGiant is not giant:
                game.liftGiant(game.grid, otherGiant)
        game.liftGiant(game.grid, giant)
        anchor = 40 + 30 * game.rowLength
        game.currentLocation = [0, 1]
        game.player.evasion = lambda: 0

        for distance, shouldHit in ((3, True), (4, False)):
            game.putGiant(game.grid, anchor, giant)
            game.EnemyPositions = {anchor}
            game.playerPositionFlat = anchor + 1 + distance  # to the right of its right-hand column
            game.player.damageTaken = 0
            giant.actionPool = 0.99
            game.MoveEnemies()
            self.assertEqual(game.player.damageTaken > 0, shouldHit, f"player {distance} tiles away")
            game.liftGiant(game.grid, giant)

    def test_enemies_face_the_way_they_step(self):
        game = support.newGame()
        goblin = enemies.Goblin()
        start = 5000
        for step, expectedFacing in ((1, FACING_RIGHT), (-1, FACING_LEFT),
                                     (-game.rowLength, FACING_UP), (game.rowLength, FACING_DOWN)):
            game.faceToward(goblin, start, start + step)
            self.assertEqual(goblin.facing, expectedFacing)


if __name__ == "__main__":
    unittest.main()
