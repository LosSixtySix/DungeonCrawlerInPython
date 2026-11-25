"""Ward (Warded Chainmail's enchantment): it blocks a hit completely, then needs relics.WARD_RECHARGE_TURNS turns to
recharge before it blocks another (PlayerClass.wardCanBlock, blockWithWard, stepWard; gameManager.hitPlayer).

Integration tests."""
import unittest
from unittest import mock

from cruel.entities.enemies import Goblin
from cruel.inventory import recipes, relics
from tests.helpers.gamemanager import ENEMY, newGame, standInOpenFloor

RECHARGE = relics.WARD_RECHARGE_TURNS


class WardTest(unittest.TestCase):
    def setUp(self):
        game = self.game = newGame()
        self.here = standInOpenFloor(game)
        self.enemySpot = self.here + 1
        self.goblin = Goblin()
        self.goblin.damage = 4
        game.grid[self.enemySpot] = [ENEMY, 1, self.goblin]
        game.EnemyPositions.add(self.enemySpot)
        player = self.player = game.player
        player.equipment["Chest"] = recipes.RECIPES_BY_ID["warded_chainmail"].build("Common")
        player.syncSlots()

    def hit(self):
        """The goblin swings and doesn't miss. Returns the damage you took."""
        before = self.player.damageTaken
        with mock.patch.object(self.game, "dodge", return_value=None):
            self.game.hitPlayer(self.goblin, self.enemySpot)
        return self.player.damageTaken - before

    def passTurns(self, turns):
        for _ in range(turns):
            self.game.enemyTurn()


class WardTests(WardTest):
    def test_the_recharge_is_ten_turns(self):
        self.assertEqual(RECHARGE, 10)

    def test_it_blocks_the_first_hit_completely(self):
        self.assertEqual(self.hit(), 0)

    def test_the_next_hit_lands_while_it_recharges(self):
        self.hit()
        self.assertGreater(self.hit(), 0)

    def test_it_blocks_again_after_ten_turns(self):
        self.hit()
        self.game.EnemyPositions.discard(self.enemySpot)  # (so the turns pass quietly)
        self.passTurns(RECHARGE - 1)
        self.assertFalse(self.player.wardCanBlock(), "one turn short")
        self.passTurns(1)
        self.assertTrue(self.player.wardCanBlock())
        self.assertEqual(self.hit(), 0)

    def test_a_new_floor_does_not_recharge_it(self):
        self.hit()
        self.game.afterLevelChange()
        self.assertFalse(self.player.wardCanBlock())

    def test_without_ward_nothing_is_blocked(self):
        self.player.equipment["Chest"] = "None"
        self.player.syncSlots()
        self.assertGreater(self.hit(), 0)

    def test_its_description_says_how_it_works(self):
        self.assertEqual(relics.EFFECTS["ward"][1], "Blocks a hit completely, then is ready again 10 turns later")

    def test_a_save_from_before_starts_with_it_ready(self):
        del self.player.wardCooldown
        self.assertTrue(self.player.wardCanBlock())
        self.player.stepWard()
        self.assertEqual(self.player.wardCooldown, 0)


if __name__ == "__main__":
    unittest.main()
