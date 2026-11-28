"""The Room window (R) shows where you stand as "(x: 0, y: 0)", counted from the map's top-left corner.

Integration tests."""
import unittest

from tests.support import newGame, placePlayer


class RoomPositionTests(unittest.TestCase):
    def setUp(self):
        self.game = newGame()

    def positionRow(self):
        rows = self.game.windowSpec("room")["rows"]
        return next(value for label, value in rows if label == "Position")

    def test_the_top_left_corner_is_x_0_y_0(self):
        self.game.playerPositionFlat = 0
        self.assertEqual(self.positionRow(), "(x: 0, y: 0)")

    def test_x_is_the_column_and_y_is_the_row(self):
        spot = 7 * self.game.rowLength + 3
        placePlayer(self.game, spot)
        self.assertEqual(self.positionRow(), "(x: 3, y: 7)")

    def test_it_is_the_last_row_of_the_room_window(self):
        self.assertEqual(self.game.windowSpec("room")["rows"][-1][0], "Position")


if __name__ == "__main__":
    unittest.main()
