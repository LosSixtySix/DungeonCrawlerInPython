"""Room nodes: splitting a floor's tiles into round clumps that become its rooms (connectingEmptyRooms.py)."""
import random
import unittest

from cruel.world import connectingEmptyRooms as rooms

ROW_LENGTH = 20
ROW_COUNT = 15


def emptyGrid():
    return {position: [0, 0] for position in range(ROW_LENGTH * ROW_COUNT)}


class CreateNodesTests(unittest.TestCase):
    """createNodes: the floor's tiles carved into nodes."""

    def test_every_tile_lands_in_exactly_one_node(self):
        random.seed(1)
        grid = emptyGrid()
        nodes = rooms.createNodes(grid, ROW_LENGTH, 3)
        allTiles = [position for node in nodes for position in node]
        self.assertEqual(len(allTiles), len(grid))
        self.assertEqual(set(allTiles), set(grid))

    def test_nodes_are_no_bigger_than_a_circle_of_the_radius(self):
        random.seed(2)
        radius = 3
        circleSize = len(rooms.getCirclePoints(7 * ROW_LENGTH + 10, radius, emptyGrid(), ROW_LENGTH, set()))
        for node in rooms.createNodes(emptyGrid(), ROW_LENGTH, radius):
            self.assertLessEqual(len(node), circleSize)
            rowNumbers = [position // ROW_LENGTH for position in node]
            self.assertLessEqual(max(rowNumbers) - min(rowNumbers), 2 * radius)


class CirclePointsTests(unittest.TestCase):
    """getCirclePoints: the tiles of one round node."""

    def test_a_radius_of_zero_is_just_the_center(self):
        center = 5 * ROW_LENGTH + 5
        self.assertEqual(rooms.getCirclePoints(center, 0, emptyGrid(), ROW_LENGTH, set()), {center})

    def test_a_circle_holds_the_tiles_within_its_radius(self):
        center = 7 * ROW_LENGTH + 10
        circle = rooms.getCirclePoints(center, 2, emptyGrid(), ROW_LENGTH, set())
        self.assertIn(center + 2, circle)
        self.assertIn(center - 2 * ROW_LENGTH, circle)
        self.assertNotIn(center + 3, circle)
        self.assertNotIn(center + 2 + 2 * ROW_LENGTH, circle)  # the corner is further than 2 away

    def test_tiles_already_used_or_off_the_map_are_left_out(self):
        center = 0
        usedTile = 1
        circle = rooms.getCirclePoints(center, 2, emptyGrid(), ROW_LENGTH, {usedTile})
        self.assertNotIn(usedTile, circle)
        self.assertTrue(all(position >= 0 for position in circle))


class NeighborTests(unittest.TestCase):
    """getNNeighbors: the square of tiles around a tile."""

    def test_a_tile_in_the_middle_has_eight_neighbors_plus_itself(self):
        middle = 5 * ROW_LENGTH + 5
        found = rooms.getNNeighbors(middle, set(emptyGrid()), 1, ROW_LENGTH)
        self.assertEqual(len(found), 9)

    def test_neighbors_in_the_same_row_do_not_wrap_around_the_map_edge(self):
        leftEdgeTile = 5 * ROW_LENGTH
        found = rooms.getNNeighbors(leftEdgeTile, set(emptyGrid()), 1, ROW_LENGTH)
        self.assertNotIn(leftEdgeTile - 1, found)  # the last tile of the row above
        self.assertIn(leftEdgeTile + 1, found)

    def test_a_larger_radius_reaches_along_rows_columns_and_diagonals(self):
        middle = 7 * ROW_LENGTH + 10
        found = rooms.getNNeighbors(middle, set(emptyGrid()), 2, ROW_LENGTH)
        self.assertEqual(len(found), 1 + 8 * 2)  # it looks along 8 directions, not the whole square
        self.assertIn(middle + 2 * ROW_LENGTH + 2, found)


if __name__ == "__main__":
    unittest.main()
