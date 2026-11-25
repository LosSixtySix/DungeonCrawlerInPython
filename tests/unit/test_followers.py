"""The Pheromone Crown and followers (followers.py, relics.py): the crown itself, and who can follow you or is
hostile to you.

Unit tests; the rest are in tests/integration/test_followers.py, tests/acceptance/test_followers.py."""
import unittest

from cruel.entities import enemies
from cruel.entities import playerClass
from cruel.inventory import relics
from cruel.world import dwellers
from cruel.world import followers


class CrownTests(unittest.TestCase):
    def test_the_crown_is_a_head_relic_with_two_defense_and_its_power(self):
        crown = relics.make("pheromone_crown")
        self.assertEqual((crown.name, crown.slot, crown.Etype, crown.bonus, crown.relicPower),
                         ("Pheromone Crown", "Head", "Defense", 2, "pheromones"))
        self.assertIn("pheromones", relics.BOUND_POWERS, "the Gilded Forge can't take its power away")
        self.assertNotIn("pheromone_crown", [relicId for relicId, _, _ in relics.CHEST_RELICS], "only the Queen has it")

    def test_wearing_it_is_half_an_action_faster(self):
        player = playerClass.PlayerClass()
        before = player.getSpeed()
        player.equipment["Head"] = relics.make("pheromone_crown")
        self.assertAlmostEqual(player.getSpeed(), before + 0.5)

    def test_the_queen_always_drops_it(self):
        self.assertEqual([item.relicId for item in enemies.DwellerQueen().loot], ["pheromone_crown"])


class WhoTests(unittest.TestCase):
    def test_who_can_follow_you(self):
        royal = enemies.RoyalGuard()
        for unit, can in ((enemies.DwellerCitizen(), True), (enemies.DwellerNoble(), True), (enemies.DwellerGuard(), True),
                          (royal, True), (enemies.DwellerMerchant(), False), (enemies.DwellerQueen(), False),
                          (enemies.DwellerEgg(), False), (enemies.DewGrub(), False), (enemies.Goblin(), False)):
            self.assertEqual(followers.canFollow(unit), can, unit.name)
        royal.follower = True
        self.assertFalse(followers.canFollow(royal), "not one that already does")

    def test_what_a_follower_goes_after(self):
        calm, hostile, follower = enemies.DwellerGuard(), enemies.DwellerGuard(), enemies.DwellerCitizen()
        hostile.hostile = True
        follower.follower = follower.hostile = True
        egg = enemies.DwellerEgg()
        egg.hostile = True
        self.assertEqual([followers.hostileToYou(None, unit) for unit in (calm, hostile, follower, egg, enemies.Goblin())],
                         [False, True, False, False, True])

    def test_the_city_treats_a_follower_as_its_enemy(self):
        citizen = enemies.DwellerCitizen()
        self.assertFalse(dwellers.isCityEnemy(citizen))
        citizen.follower = True
        self.assertTrue(dwellers.isCityEnemy(citizen))


if __name__ == "__main__":
    unittest.main()
