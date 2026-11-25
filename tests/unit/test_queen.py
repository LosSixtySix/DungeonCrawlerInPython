"""The Dweller Queen's court (queen.py, enemies.DwellerQueen, RoyalGuard, RoyalPupa): what each unit is, and the
rules that need no game.

Unit tests; the rest are in tests/integration/test_queen.py, tests/acceptance/test_queen.py."""
import unittest
from unittest import mock

from cruel.entities import enemies
from cruel.graphics import sprites
from cruel.world import dwellers
from cruel.world import metropolis
from cruel.world import occupancy
from cruel.world import queen


class UnitTests(unittest.TestCase):
    def test_the_queen_is_a_large_two_by_two_dweller(self):
        dwellerQueen = enemies.DwellerQueen()
        self.assertTrue(dwellers.isDweller(dwellerQueen))
        self.assertEqual(occupancy.sizeOf(dwellerQueen), occupancy.LARGE)
        self.assertEqual(dwellerQueen.size, 2)
        self.assertEqual((dwellerQueen.hp, dwellerQueen.ac, dwellerQueen.damage, dwellerQueen.reach, dwellerQueen.gold),
                         (120, 16, 8, 2, 150))
        self.assertTrue(queen.isQueen(dwellerQueen))

    def test_a_royal_guard_is_a_stronger_guard_on_a_leash(self):
        guard, royal = enemies.DwellerGuard(), enemies.RoyalGuard()
        self.assertEqual(royal.role, "guard")
        self.assertTrue(queen.isRoyal(royal) and not queen.isRoyal(guard))
        self.assertGreater(royal.hp, guard.hp)
        self.assertGreater(royal.ac, guard.ac)
        self.assertGreater(royal.damage, guard.damage)
        self.assertEqual((royal.hp, royal.ac, royal.damage, royal.gold, royal.leash), (30, 17, 7, 15, 8))
        self.assertEqual(royal.speed, guard.speed)

    def test_a_pupa_cannot_fight(self):
        pupa = enemies.RoyalPupa(40, post=12)
        self.assertEqual((pupa.hp, pupa.damage, pupa.turnsLeft, pupa.post), (20, 0, 40, 12))
        self.assertTrue(queen.isPupa(pupa) and queen.takesTurn(pupa))
        self.assertFalse(dwellers.canBeMoved(pupa))

    def test_nobody_can_move_the_queen_out_of_their_way(self):
        self.assertFalse(dwellers.canBeMoved(enemies.DwellerQueen()))
        self.assertTrue(dwellers.canBeMoved(enemies.DwellerCitizen()))


class SpriteTests(unittest.TestCase):
    def test_the_queen_is_drawn_over_two_by_two_tiles(self):
        rows, colors = sprites.GIANT_SPRITES["Dweller Queen"]
        self.assertEqual((len(rows), {len(row) for row in rows}), (20, {20}))
        self.assertTrue(set("".join(rows)) - {".", "k"} <= set(colors))

    def test_the_royal_guard_is_the_guard_in_royal_colors(self):
        rows, colors = sprites.ENEMY_SPRITES["Royal Guard"]
        self.assertEqual(rows, sprites.DWELLER_GUARD)
        self.assertNotEqual(colors, sprites.DWELLER_GUARD_COLORS)
        self.assertIn("Royal Pupa", sprites.ENEMY_SPRITES)


class BodyDistanceTests(unittest.TestCase):
    def test_distance_from_the_nearest_tile_of_her_body(self):
        rowLength, anchor = 20, 5 + 5 * 20  # her body: (5, 5) to (6, 6)
        self.assertEqual(metropolis.bodyDistance(rowLength, anchor, 2, 6 + 6 * 20), 0)
        self.assertEqual(metropolis.bodyDistance(rowLength, anchor, 2, 7 + 6 * 20), 1)
        self.assertEqual(metropolis.bodyDistance(rowLength, anchor, 2, 8 + 8 * 20), 2)
        self.assertEqual(metropolis.bodyDistance(rowLength, anchor, 2, 3 + 5 * 20), 2)


class LeashTests(unittest.TestCase):
    def test_a_royal_guard_goes_no_further_than_its_leash_from_its_post(self):
        game = mock.Mock(rowLength=100)
        royal = enemies.RoyalGuard()
        royal.home = 10 + 10 * 100
        self.assertTrue(dwellers.withinLeash(game, royal, 18 + 10 * 100))
        self.assertFalse(dwellers.withinLeash(game, royal, 19 + 10 * 100))
        guard = enemies.DwellerGuard()
        guard.home = royal.home
        self.assertTrue(dwellers.withinLeash(game, guard, 60 + 10 * 100), "an ordinary guard has no leash")


if __name__ == "__main__":
    unittest.main()
