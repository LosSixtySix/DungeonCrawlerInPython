"""Symmetric shadowcasting (sight.fieldOfView): what can be seen from a tile, on small maps built by hand.

Unit tests; the rest are in tests/integration/test_sight.py."""
import random
import unittest

from cruel.world import sight

SIZE = 31


def view(walls, origin, reach, size=SIZE):
    """Seen tiles as (column, row), on a size x size map with walls at the (column, row)s given."""
    blocked = {column + row * size for column, row in walls}
    seen = sight.fieldOfView(origin[0] + origin[1] * size, reach, size, size, lambda spot: spot in blocked)
    return {(spot % size, spot // size) for spot in seen}


def circle(origin, reach, size=SIZE):
    return {(column, row) for row in range(size) for column in range(size)
            if (column - origin[0]) ** 2 + (row - origin[1]) ** 2 <= reach * reach + reach}


class OpenGroundTests(unittest.TestCase):
    def test_on_open_ground_every_tile_in_range_is_seen_with_no_holes(self):
        for reach in (2, 5, 8, 12):
            self.assertEqual(view(set(), (15, 15), reach), circle((15, 15), reach))

    def test_the_map_edge_stops_it(self):
        seen = view(set(), (1, 1), 6)
        self.assertTrue(all(0 <= column < SIZE and 0 <= row < SIZE for column, row in seen))
        self.assertIn((0, 0), view(set(), (0, 0), 3))


class WallTests(unittest.TestCase):
    def test_a_wall_is_seen_and_hides_what_is_behind_it(self):
        seen = view({(18, 15)}, (15, 15), 8)
        self.assertIn((18, 15), seen)
        self.assertNotIn((19, 15), seen)
        self.assertNotIn((22, 15), seen)
        self.assertIn((19, 13), seen, "off to the side of it is still seen")

    def test_a_wall_in_view_shows_whole(self):
        wallLine = {(column, 10) for column in range(5, 26)}
        seen = view(wallLine, (15, 15), 8)
        inRange = {spot for spot in wallLine if spot in circle((15, 15), 8)}
        self.assertEqual(seen & wallLine, inRange, "every tile of the wall face in range")

    def test_light_never_slips_between_walls_that_only_touch_at_a_corner(self):
        diagonal = {(10 + step, 10 + step) for step in range(12)}
        seen = view(diagonal, (18, 14), 10)  # (on one side of the diagonal)
        otherSide = {(column, row) for column, row in circle((18, 14), 10) if row > column and (column, row) not in diagonal}
        self.assertFalse(seen & otherSide)

    def test_a_line_straight_along_a_diagonal_stops_at_a_pinch(self):
        pinch = {(18, 17), (17, 18)}  # (touching at the corner the diagonal from (15, 15) passes through)
        seen = view(pinch, (15, 15), 8)
        self.assertIn((17, 17), seen)
        self.assertNotIn((18, 18), seen)
        self.assertNotIn((20, 20), seen)
        self.assertIn((18, 18), view({(18, 17)}, (15, 15), 8), "one of them alone doesn't stop it")

    def test_from_inside_a_one_wide_corridor_you_see_along_it(self):
        walls = {(column, row) for column in range(SIZE) for row in (14, 16)}
        seen = view(walls, (5, 15), 12)
        self.assertTrue({(column, 15) for column in range(5, 18)} <= seen)
        self.assertNotIn((5, 13), seen)


class SymmetryTests(unittest.TestCase):
    def test_if_you_see_a_floor_tile_it_sees_you(self):
        random.seed(5)
        for trial in range(9):
            walls = {(column, row) for row in range(SIZE) for column in range(SIZE) if random.random() < (0.1, 0.25, 0.4)[trial % 3]}
            origin = (15, 15)
            walls.discard(origin)
            for column, row in view(walls, origin, 9):
                if (column, row) in walls or (column, row) == origin:
                    continue
                self.assertIn(origin, view(walls, (column, row), 9), f"{(column, row)} can't see back")


class UnitTests(unittest.TestCase):
    """Units block sight for anyone else, but only show when the line to them is clear (no wholeFace)."""

    def sees(self, walls, looker, other):
        blocked = {column + row * SIZE for column, row in walls} | {other[0] + other[1] * SIZE}
        seen = sight.fieldOfView(looker[0] + looker[1] * SIZE, 9, SIZE, SIZE, lambda spot: spot in blocked,
                                 lambda spot: spot != other[0] + other[1] * SIZE)
        return other[0] + other[1] * SIZE in seen

    def test_if_you_see_an_enemy_it_sees_you(self):
        random.seed(8)
        for _ in range(4):
            walls = {(column, row) for row in range(SIZE) for column in range(SIZE) if random.random() < 0.25}
            you = (15, 15)
            walls.discard(you)
            for column in range(7, 24):
                for row in range(7, 24):
                    if (column, row) in walls or (column, row) == you:
                        continue
                    self.assertEqual(self.sees(walls, you, (column, row)), self.sees(walls, (column, row), you), (column, row))

    def test_a_unit_round_a_corner_is_not_seen_just_because_the_floor_beside_it_is(self):
        walls = {(18, row) for row in range(10, 15)}  # (a wall between you and the unit, the floor below it open)
        self.assertFalse(self.sees(walls, (15, 12), (20, 12)))


if __name__ == "__main__":
    unittest.main()
