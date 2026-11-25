"""The Dwellers' works floors growing: young Dew Grubs, farmers moving grubs between pens and building new pens
(dewgrubs.py), and new storehouses when the chests are full (dwellerbuilding.py).

Acceptance tests; the rest are in tests/integration/test_dweller_growth.py."""
import random
import unittest
from cruel.world import dwellerfarming
from cruel.world import dwellerwork
from cruel.world import mineshafts
from tests.helpers.metropolis import cityGame
from tests.helpers.mineshafts import climbDown
from tests.helpers.dweller_work import dewMade


# ---------------------------------------------------------------- whole floors

class GrowingFloorTests(unittest.TestCase):
    def runFloor(self, kind, turns, seed=11):
        random.seed(seed)
        game = cityGame(seed)
        climbDown(game, kind)
        game.floorEvents.pop(game.level, None)  # (no Expansion or Overgrowth: just the works)
        for _ in range(turns):
            game.enemyTurn()
        return game

    def test_a_farm_keeps_its_grubs_fed_grows_its_herd_and_makes_dew(self):
        game = self.runFloor("farm", 1500, seed=7)
        grubs = dwellerwork.grubsHere(game)
        self.assertGreater(len(grubs), sum(mineshafts.GRUBS_PER_PEN), "the herd has grown")
        self.assertTrue(all(grub.hunger < dwellerfarming.STARVE_TURNS for _, grub in grubs))
        self.assertGreater(dewMade(game), 0)


if __name__ == "__main__":
    unittest.main()
