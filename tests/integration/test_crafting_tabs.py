"""The Crafting window's station tabs (renderer.drawCraft, craftTabsShown): a strip that scrolls left and right,
so the tabs always stay inside the window's top, with the selected one in view and an arrow at an end with more.

Integration tests."""
import random
import unittest

from cruel.inventory import recipes
from tests.support import newGame

LEFT, RIGHT = -1, 1


class StripTests(unittest.TestCase):
    """craftTabsShown on its own: tab widths in, the run drawn out."""

    def setUp(self):
        self.painter = newGame().painter
        self.gap = self.painter.CRAFT_TAB_GAP

    def span(self, widths, first, last):
        return sum(widths[first:last + 1]) + self.gap * (last - first)

    def test_all_of_them_when_they_fit(self):
        widths = [50] * 4
        self.assertEqual(self.painter.craftTabsShown(widths, 2, 1000), (0, 3))

    def test_the_selected_tab_is_always_in_view_and_they_fit(self):
        widths = [40, 80, 60, 90, 70, 50, 100, 60]
        for selected in range(len(widths)):
            first, last = self.painter.craftTabsShown(widths, selected, 200)
            self.assertLessEqual(first, selected)
            self.assertGreaterEqual(last, selected)
            self.assertLessEqual(self.span(widths, first, last), 200)

    def test_it_stays_put_while_the_selected_tab_is_in_view(self):
        widths = [50] * 10
        first, _ = self.painter.craftTabsShown(widths, 9, 200)  # (scrolled right to the end)
        self.assertGreater(first, 0)
        self.assertEqual(self.painter.craftTabsShown(widths, first, 200, first)[0], first, "going back left inside the view")
        self.assertEqual(self.painter.craftTabsShown(widths, first - 1, 200, first)[0], first - 1, "one past the left end")

    def test_no_empty_room_at_the_right_that_earlier_tabs_could_fill(self):
        widths = [50] * 10
        first, last = self.painter.craftTabsShown(widths, 9, 200, 9)
        self.assertEqual(last, 9)
        self.assertGreater(self.span(widths, first - 1, last), 200)


class WindowTests(unittest.TestCase):
    """The real Crafting window, every station's tab selected in turn."""

    def setUp(self):
        random.seed(2)
        self.game = newGame()
        self.game.setPositionsVisible()
        self.game.openWindow("crafting")

    def drawnTabs(self):
        self.game.draw()
        rect = self.game.windowRects["crafting"]
        first, last = self.game.painter.craftTabsDrawn
        names = [recipes.TAB_NAMES[station] for station in recipes.STATIONS]
        left = rect.x + self.game.painter.PAD + self.game.painter.CRAFT_TAB_ARROW
        right = left + sum(self.game.painter.craftTabWidth(name) for name in names[first:last + 1]) \
            + self.game.painter.CRAFT_TAB_GAP * (last - first)
        return rect, first, last, left, right

    def test_every_tab_stays_inside_the_window_and_the_selected_one_shows(self):
        for station in range(len(recipes.STATIONS)):
            self.game.craftTab = station
            rect, first, last, left, right = self.drawnTabs()
            self.assertTrue(first <= station <= last)
            self.assertGreaterEqual(left, rect.x)
            self.assertLessEqual(right, rect.right - self.game.painter.PAD - self.game.painter.CRAFT_TAB_ARROW)

    def test_moving_right_scrolls_the_strip_to_the_last_station_and_back(self):
        self.game.focus = "crafting"
        for _ in recipes.STATIONS:
            self.game.moveSelection(RIGHT, 0)
            self.drawnTabs()
        self.assertEqual(self.game.craftTab, len(recipes.STATIONS) - 1)
        _, first, last, _, _ = self.drawnTabs()
        self.assertEqual(last, len(recipes.STATIONS) - 1)
        for _ in recipes.STATIONS:
            self.game.moveSelection(LEFT, 0)
            self.drawnTabs()
        self.assertEqual(self.drawnTabs()[1], 0, "back at the first station")

    def test_there_are_more_tabs_than_fit_at_once(self):
        """(otherwise the strip never scrolls: this guards the other tests' worth)"""
        names = [recipes.TAB_NAMES[station] for station in recipes.STATIONS]
        widths = [self.game.painter.craftTabWidth(name) for name in names]
        room = self.game.painter.CRAFT_W - 2 * self.game.painter.PAD - 2 * self.game.painter.CRAFT_TAB_ARROW
        self.assertGreater(sum(widths) + self.game.painter.CRAFT_TAB_GAP * (len(widths) - 1), room)


if __name__ == "__main__":
    unittest.main()
