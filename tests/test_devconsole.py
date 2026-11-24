"""The developer console (~): typing commands into a real game and reading what it writes back."""
import unittest

import tests  # noqa: F401
from tests import support
from cruel.core import devconsole


class ConsoleTestCase(unittest.TestCase):
    """A fresh game on the first floor, with helpers to type a command and read the new log lines."""

    def setUp(self):
        self.game = support.newGame()
        self.console = self.game.console

    def type(self, command):
        """Types command and presses Enter. Returns the (style, text) lines it added."""
        linesBefore = len(self.console.log)
        self.console.text = command
        self.console.submit()
        return self.console.log[linesBefore:]

    def assertLastLineIs(self, newLines, style):
        self.assertTrue(newLines, "the command wrote nothing")
        self.assertEqual(newLines[-1][0], style, newLines)


class CommandBasicsTests(ConsoleTestCase):
    """Help, unknown commands, aliases and clearing."""

    def test_help_lists_every_command(self):
        helpLines = self.type("/help")
        self.assertEqual(helpLines[0], ("input", "> /help"))
        helpText = "\n".join(text for _, text in helpLines)
        for _, usage, _ in self.console.commands.values():
            self.assertIn(usage, helpText)

    def test_an_unknown_command_writes_an_error(self):
        newLines = self.type("/fly")
        self.assertLastLineIs(newLines, "error")
        self.assertIn("fly", newLines[-1][1])

    def test_commands_work_without_the_slash_and_through_aliases(self):
        goldBefore = self.game.player.gold
        self.type("additem gold 5")
        self.assertEqual(self.game.player.gold, goldBefore + 5)

    def test_clear_empties_the_log(self):
        self.type("/help")
        self.type("/clear")
        self.assertEqual(self.console.log, [])

    def test_typed_commands_are_remembered_once(self):
        self.type("/help")
        self.type("/help")
        self.assertEqual(self.console.history, ["/help"])


class GiveTests(ConsoleTestCase):
    """/give: gold, materials, gear and relics."""

    def test_giving_gold_adds_it(self):
        goldBefore = self.game.player.gold
        self.assertLastLineIs(self.type("/give gold 25"), "good")
        self.assertEqual(self.game.player.gold, goldBefore + 25)

    def test_giving_a_material_puts_it_in_the_pouch(self):
        self.assertLastLineIs(self.type("/give wood 3"), "good")
        self.assertEqual(self.game.player.materials.get("wood"), 3)

    def test_giving_gear_puts_it_in_the_inventory(self):
        inventoryBefore = len(self.game.player.inventory)
        self.assertLastLineIs(self.type("/give stone_pick"), "good")
        self.assertEqual(len(self.game.player.inventory), inventoryBefore + 1)

    def test_giving_a_relic_puts_it_in_the_inventory(self):
        inventoryBefore = len(self.game.player.inventory)
        self.assertLastLineIs(self.type("/give lantern"), "good")
        self.assertEqual(len(self.game.player.inventory), inventoryBefore + 1)

    def test_an_unknown_item_or_bad_amount_is_an_error_and_gives_nothing(self):
        goldBefore = self.game.player.gold
        for badCommand in ("/give", "/give dragon_egg", "/give gold lots", "/give gold 0"):
            with self.subTest(badCommand=badCommand):
                self.assertLastLineIs(self.type(badCommand), "error")
        self.assertEqual(self.game.player.gold, goldBefore)

    def test_every_catalog_item_can_be_made(self):
        for itemId, (_, _, kind) in devconsole.itemCatalog().items():
            if kind in ("relic", "recipe"):
                with self.subTest(itemId=itemId):
                    self.assertIsNotNone(self.console.makeItem(itemId, kind))


class ToggleTests(ConsoleTestCase):
    """/peaceful, /reveal and /play switches."""

    def test_peaceful_toggles_and_takes_on_or_off(self):
        self.assertFalse(self.game.peaceful)
        self.type("/peaceful")
        self.assertTrue(self.game.peaceful)
        self.type("/peaceful off")
        self.assertFalse(self.game.peaceful)
        self.type("/aggro on")
        self.assertTrue(self.game.peaceful)
        self.assertLastLineIs(self.type("/peaceful maybe"), "error")

    def test_reveal_turns_the_whole_floor_visible(self):
        self.type("/reveal on")
        self.assertTrue(self.game.revealMap)
        self.type("/reveal off")
        self.assertFalse(self.game.revealMap)

    def test_play_starts_and_stops_watching(self):
        self.type("/play 40")
        self.assertEqual(self.game.autoPlay["ms"], 40)
        self.type("/play off")
        self.assertIsNone(self.game.autoPlay)
        self.assertLastLineIs(self.type("/play fast"), "error")


class FloorCommandTests(ConsoleTestCase):
    """/patience, /orefloor, /event and /enemy."""

    def test_patience_on_the_center_tile_drops_you_to_an_ore_floor(self):
        self.assertEqual(self.game.playerPositionFlat, self.game.centerTile())
        damageBefore = self.game.player.damageTaken
        self.assertLastLineIs(self.type("/patience"), "good")
        self.assertEqual(self.game.level, 1)
        self.assertGreater(self.game.player.damageTaken, damageBefore)

    def test_patience_off_the_center_tile_is_an_error(self):
        support.placePlayer(self.game, support.openTile(self.game, avoid=(self.game.centerTile(),)))
        self.assertLastLineIs(self.type("/patience"), "error")
        self.assertEqual(self.game.level, 0)

    def test_patience_below_the_first_floor_is_an_error(self):
        self.game.goToNewLevel()
        self.assertLastLineIs(self.type("/patience"), "error")

    def test_orefloor_sets_the_next_floor(self):
        oreFloorId, oreFloorName = next(iter(devconsole.oreFloorIds().items()))
        self.type(f"/orefloor {oreFloorId} mother")
        self.assertEqual(self.game.forcedOreFloor, (oreFloorName, True))

    def test_an_unknown_orefloor_is_an_error(self):
        newLines = self.type("/orefloor cheese")
        self.assertIn("error", [style for style, _ in newLines])
        self.assertIsNone(self.game.forcedOreFloor)

    def test_event_starts_a_floor_event_now(self):
        eventId = next(iter(devconsole.events.EVENTS))
        self.assertLastLineIs(self.type(f"/event {eventId}"), "good")
        self.assertEqual(self.game.floorEvents[self.game.level], {"id": eventId, "turnsLeft": 0, "active": True})

    def test_enemy_lists_every_kind_of_enemy(self):
        enemyText = "\n".join(text for _, text in self.type("/enemies"))
        for enemyId in devconsole.enemyCatalog():
            self.assertIn(enemyId, enemyText)


class AutofillTests(ConsoleTestCase):
    """Tab completion of commands and /give item ids."""

    def test_tab_completes_a_command(self):
        self.console.text = "/pat"
        self.console.autofill()
        self.assertEqual(self.console.text, "/patience ")

    def test_tab_completes_an_item_id_from_part_of_its_name(self):
        self.console.text = "/give stone_pi"
        self.console.autofill()
        self.assertEqual(self.console.text, "/give stone_pick ")


if __name__ == "__main__":
    unittest.main()
