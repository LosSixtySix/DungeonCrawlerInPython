"""Organizers: the enemies that clear a spot and build spirals, rings, squares and Demise gliders (organizers.py).

Unit tests; the rest are in tests/integration/test_organizers.py."""
import random
import unittest
from cruel.world import organizers


class ShapeTests(unittest.TestCase):
    """The pattern shapes, as offsets from their center."""

    def test_a_spiral_has_one_wall_per_step_of_each_longer_leg(self):
        walls, inside = organizers.spiralShape(3)
        self.assertEqual(len(walls), 1 + 2 + 3 + 4)
        self.assertEqual(inside, set())

    def test_a_ring_is_hollow_with_exactly_one_compass_doorway(self):
        random.seed(1)
        radius = 5
        walls, inside = organizers.circleShape(radius)
        compassPoints = {(radius, 0), (-radius, 0), (0, radius), (0, -radius)}
        self.assertEqual(len(compassPoints - walls), 1)
        self.assertFalse(walls & inside)
        self.assertIn((0, 0), inside)

    def test_a_square_is_an_outline_with_a_doorway_in_one_side(self):
        random.seed(2)
        walls, inside = organizers.squareShape(5)
        self.assertEqual(len(walls), 16 - 1)
        self.assertEqual(len(inside), 9)
        doorways = {(0, -2), (0, 2), (-2, 0), (2, 0)} - walls
        self.assertEqual(len(doorways), 1)

    def test_a_glider_has_five_cells_all_on_its_wood(self):
        cells, wood = organizers.gliderShape(1, 1)
        self.assertEqual(len(cells), 5)
        self.assertTrue(cells <= wood)
        pointedLeftUp, _ = organizers.gliderShape(-1, -1)
        self.assertEqual(pointedLeftUp, {(-column, -row) for column, row in cells})

    def test_a_margin_adds_every_tile_around_the_shape(self):
        self.assertEqual(len(organizers.withMargin({(0, 0)})), 9)
        self.assertEqual(len(organizers.withMargin({(0, 0), (1, 0)})), 12)


if __name__ == "__main__":
    unittest.main()
