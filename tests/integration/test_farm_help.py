"""A city keeping its farm running (queen.sendFarmHands, joinWorks): sending idle citizens down when the farm is
short of farmers, and what they do when they get there.

Integration tests; the rest are in tests/acceptance/test_farm_help.py."""
import os
import tempfile
import unittest
from unittest import mock

from cruel.core import gamemanager
from cruel.entities import enemies
from cruel.world import dwellerfarming
from cruel.world import dwellers
from cruel.world import livingfloors
from cruel.world import queen
from tests import support
from tests.helpers.metropolis import cityGame


class FarmersWantedTests(unittest.TestCase):
    def test_a_keeper_for_every_five_grubs_and_a_grower_for_every_twenty_field_tiles(self):
        self.assertEqual(queen.farmersWanted({"grubs": 11, "fieldTiles": 40}), 3 + 2)
        self.assertEqual(queen.farmersWanted({"grubs": 0, "fieldTiles": 0}), 2, "at least one of each")
        self.assertEqual(queen.farmersWanted({"grubs": dwellerfarming.KEEPER_HERD, "fieldTiles": 20}), 2)


class SendingTests(unittest.TestCase):
    def setUp(self):
        self.game = cityGame()
        self.game.enemyTurn()  # (the farm counts itself on its first turn)
        self.shaft = queen.shaftsHere(self.game, "farm")[0]
        self.farmKey = (self.game.level, self.shaft)
        self.record = self.game.workCensus[self.farmKey]

    def short(self, farmers=0):
        self.record.update(farmer=farmers, grubs=10, fieldTiles=40)  # (4 wanted)

    def onCensusTurn(self):
        self.game.turnCount += queen.CENSUS_TURNS - self.game.turnCount % queen.CENSUS_TURNS

    def sent(self):
        return [unit for _, unit in dwellers.cityDwellers(self.game) if getattr(unit, "joining", None) == "farm"]

    def test_short_of_farmers_it_sends_the_idle_citizen_nearest_the_farm_shaft(self):
        game = self.game
        self.short()
        self.onCensusTurn()
        citizen = queen.sendFarmHands(game)
        self.assertEqual(self.sent(), [citizen])
        idle = [(spot, unit) for spot, unit in dwellers.cityDwellers(game) if queen.idleCitizen(unit) or unit is citizen]
        nearest = min(idle, key=lambda found: dwellers.distance(game, found[0], self.shaft))[1]
        self.assertIs(citizen, nearest)

    def test_one_at_a_time_on_census_turns_only(self):
        self.short()
        self.onCensusTurn()
        self.game.turnCount += 1
        self.assertIsNone(queen.sendFarmHands(self.game))
        self.onCensusTurn()
        queen.sendFarmHands(self.game)
        self.assertEqual(len(self.sent()), 1)

    def test_not_when_the_farm_has_enough_counting_those_on_their_way(self):
        game = self.game
        self.short(farmers=3)
        self.onCensusTurn()
        self.assertIsNotNone(queen.sendFarmHands(game), "3 of 4: one more")
        self.onCensusTurn()
        self.assertIsNone(queen.sendFarmHands(game), "the one on its way makes 4")
        walker = self.sent()[0]
        walker.joining = None
        livingfloors.arrivals(game)[self.farmKey] = [(walker, self.shaft)]
        walker.joining = "farm"
        self.assertIsNone(queen.sendFarmHands(game), "nor while it's climbing down")

    def test_it_keeps_its_last_citizens(self):
        game = self.game
        self.short()
        idle = [unit for _, unit in dwellers.cityDwellers(game) if unit.role == "citizen" and unit.work is None]
        for unit in idle[queen.CITY_CITIZENS_KEPT:]:
            unit.work = "dew"
        self.onCensusTurn()
        self.assertIsNone(queen.sendFarmHands(game))

    def test_only_an_idle_citizen_goes(self):
        busy = [enemies.DwellerCitizen() for _ in range(5)]
        busy[0].work = "dew"
        busy[1].joining = "mine"
        busy[2].hostile = True
        busy[3].follower = True
        busy[4].heldEgg = enemies.DwellerEgg()
        self.assertFalse(any(queen.idleCitizen(unit) for unit in busy))
        self.assertFalse(queen.idleCitizen(enemies.DwellerGuard()))
        self.assertTrue(queen.idleCitizen(enemies.DwellerCitizen()))

    def test_a_sent_citizen_walks_down_and_becomes_a_farmer(self):
        game = self.game
        self.short()
        self.onCensusTurn()
        citizen = queen.sendFarmHands(game)
        with mock.patch.object(dwellers, "IDLE_CHANCE", 0), mock.patch.object(queen, "sendFarmHands", lambda game: None):
            for _ in range(300):
                game.enemyTurn()
                if citizen.work == "farm":
                    break
        self.assertEqual(citizen.work, "farm")
        self.assertIn(citizen.farmRole, ("keeper", "grower"))


class JoiningTests(unittest.TestCase):
    def setUp(self):
        self.game = cityGame()
        self.game.enemyTurn()
        self.farmKey = (self.game.level, queen.shaftsHere(self.game, "farm")[0])

    def newcomer(self):
        citizen = enemies.DwellerCitizen()
        citizen.joining = "farm"
        return citizen

    def test_it_keeps_the_grubs_if_they_need_more_keepers_or_else_grows(self):
        game = self.game
        with livingfloors.awayFloor(game, self.farmKey):
            farmers = [unit for _, unit in dwellers.cityDwellers(game) if unit.work == "farm"]
            grubs = sum(1 for _, unit in dwellers.cityDwellers(game) if unit.role == "grub")
            for farmer in farmers:
                farmer.farmRole = "grower"
            keeperNeeded = self.newcomer()
            queen.joinWorks(game, game.sideFloor[1], keeperNeeded)
            self.assertEqual(keeperNeeded.farmRole, "keeper")
            for farmer in farmers:
                farmer.farmRole = "keeper"
            enough = self.newcomer()
            queen.joinWorks(game, game.sideFloor[1], enough)
            self.assertEqual(enough.farmRole, "grower" if len(farmers) * dwellerfarming.KEEPER_HERD >= grubs else "keeper")

    def test_with_no_farmer_left_it_takes_up_the_farm_from_its_census(self):
        game = self.game
        with livingfloors.awayFloor(game, self.farmKey):
            fields = next(unit for _, unit in dwellers.cityDwellers(game) if unit.work == "farm").fields
            for spot, unit in list(dwellers.cityDwellers(game)):
                if unit.work == "farm":
                    game.killEnemy(spot, killer=None, unit=unit)
            newcomer = self.newcomer()
            queen.joinWorks(game, game.sideFloor[1], newcomer)
            self.assertIs(newcomer.fields, fields)
            self.assertTrue(newcomer.pens)

    def test_it_counts_at_once_so_no_one_else_is_sent_for_it(self):
        game = self.game
        record = game.workCensus[self.farmKey]
        before = record["farmer"]
        with livingfloors.awayFloor(game, self.farmKey):
            queen.joinWorks(game, game.sideFloor[1], self.newcomer())
        self.assertEqual(record["farmer"], before + 1)

    def test_what_the_farm_shares_is_saved_with_the_game(self):
        game = self.game
        path = os.path.join(tempfile.mkdtemp(), "save.pkl")
        gamemanager.gameManager.saveGame(game, path)
        loaded = support.newGame()
        self.assertTrue(loaded.loadGame(path))
        self.assertIn("fields", queen.sharedOf(loaded)[self.farmKey])


if __name__ == "__main__":
    unittest.main()
