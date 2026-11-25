"""The Pheromone Crown, played: you kill the Queen in a real city, find her crown where she fell, put it on, and the
city comes for you.

Acceptance tests; the rest are in tests/unit/test_followers.py, tests/integration/test_followers.py."""
import unittest

from cruel.world import queen
from tests.helpers.queen import BesideTheQueen

PILE = 9


class CrownTests(BesideTheQueen):
    def test_her_crown_is_where_she_fell_and_wearing_it_the_city_comes_for_you(self):
        game = self.game
        self.queen.hp = 1
        game.player.DealDamage = lambda: 5
        game.enemyDodge = lambda target, damage, position: damage
        game.onInteract()
        self.assertIsNone(queen.courtOf(game), "she's dead")
        piles = [game.grid[tile][2] for tile in game.footprint(self.anchor, 2) if game.grid[tile][0] == PILE]
        crowns = [thing for pile in piles for thing in pile.items if getattr(thing, "relicId", None) == "pheromone_crown"]
        self.assertEqual(len(crowns), 1)
        game.player.equipment["Head"] = crowns[0]
        self.assertTrue(game.player.hasEffect("pheromones"))
        game.player.evasion = lambda: 0
        game.player.damageTaken = 0
        for _ in range(60):
            game.enemyTurn()
            if game.player.damageTaken:
                break
        self.assertGreater(game.player.damageTaken, 0, "the city's guards came for you")


if __name__ == "__main__":
    unittest.main()
