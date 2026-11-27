"""The Goblin Archer's numbers (enemies.GoblinArcher), where it spawns, and the shot odds (ranged.targetShare)."""
import unittest

from cruel.entities import enemies
from cruel.world import expansion, ranged


class StatTests(unittest.TestCase):
    """The numbers from its design sheet."""

    def test_its_stats(self):
        archer = enemies.GoblinArcher()
        self.assertEqual((archer.hp, archer.ac, archer.speed, archer.damage, archer.wallDamage, archer.gold),
                         (4, 9, 1, 1, 1, 7))
        self.assertEqual((archer.arrowDamage, archer.range, archer.keepAway, archer.visionRange), (2, 5, 2, 6))
        self.assertEqual((archer.strayChance, archer.lineShare), (20, 20))

    def test_it_is_a_small_ranged_goblin_that_can_dig(self):
        archer = enemies.GoblinArcher()
        self.assertTrue(ranged.isRanged(archer))
        self.assertEqual(archer.unitSize, "small")
        self.assertTrue(archer.dig)
        self.assertIn(archer.name, expansion.GOBLIN_NAMES)

    def test_other_enemies_are_not_ranged(self):
        self.assertFalse(ranged.isRanged(enemies.Goblin()))


class SpawnTests(unittest.TestCase):
    def test_it_turns_up_wild_on_new_floors(self):
        self.assertIn(enemies.GoblinArcher, enemies.lowerFloorEnemies)

    def test_spawners_make_one_sixteen_times_in_a_hundred(self):
        odds = dict(expansion.SPAWN_ODDS)
        self.assertEqual(odds, {"Goblin": 50, "Goblin Chieftan": 20, "Goblin Archer": 16, "Goblin Builder": 8, "Goblin Farmer": 6})
        self.assertEqual(sum(odds.values()), 100)
        self.assertIs(expansion.UNIT_CLASSES["Goblin Archer"], enemies.GoblinArcher)

    def test_it_fights_in_squads(self):
        self.assertNotIn("Goblin Archer", expansion.WORKERS)


class TargetShareTests(unittest.TestCase):
    """Out of 100: 20 stray, 20 taken by each unit on the line, the rest for the target."""

    def test_the_target_share_falls_a_fifth_for_each_unit_on_the_line(self):
        archer = enemies.GoblinArcher()
        self.assertEqual([ranged.targetShare(archer, units) for units in range(5)], [80, 60, 40, 20, 0])


if __name__ == "__main__":
    unittest.main()
