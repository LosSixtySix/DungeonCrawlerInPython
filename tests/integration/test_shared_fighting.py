"""Fighting over a space two units share (occupancy.py): enemies hit the one with the lowest HP, area damage hits
everyone there, and you choose which to hit in the Attack which? window.

Integration tests; the rest are in tests/acceptance/test_shared_fighting.py."""
import random
import unittest
from unittest import mock
from cruel.entities import enemies
from cruel.world import expansion
from cruel.world import occupancy
from cruel.world import organizers
from tests.helpers.unit_sizes import OccupancyTest


class EnemyHitTests(OccupancyTest):
    def test_the_one_with_the_lowest_hp_is_hit(self):
        strong, weak = self.put(self.middle, enemies.DireRat()), self.put(self.middle, enemies.DireRat())
        strong.hp, weak.hp = 9, 2
        self.assertIs(occupancy.victimAt(self.game, self.middle, strong), weak)

    def test_a_tie_goes_either_way(self):
        first, second = self.put(self.middle, enemies.DireRat()), self.put(self.middle, enemies.DireRat())
        first.hp = second.hp = 5
        random.seed(1)
        hit = {id(occupancy.victimAt(self.game, self.middle, first)) for _ in range(40)}
        self.assertEqual(hit, {id(first), id(second)})

    def test_a_goblin_hitting_a_shared_space_hits_the_weaker_and_kills_only_it(self):
        strong, weak = self.put(self.middle, enemies.DireRat()), self.put(self.middle, enemies.DireRat())
        strong.hp, weak.hp = 9, 1
        goblin = enemies.Goblin()
        goblin.damage = 5
        with mock.patch.object(self.game, "enemyDodge", side_effect=lambda target, damage, position: damage):
            expansion.attack(self.game, self.middle - 1, goblin, strong, self.middle)
        self.assertEqual(strong.hp, 9)
        self.assertEqual(self.at(self.middle), [strong])

    def test_an_organizer_hits_the_weaker_too(self):
        strong, weak = self.put(self.middle, enemies.Goblin()), self.put(self.middle, enemies.Goblin())
        strong.hp, weak.hp = 9, 3
        organizer = enemies.SquareOrganizer()
        organizer.aggro, organizer.damage = strong, 1
        with mock.patch.object(self.game, "enemyDodge", side_effect=lambda target, damage, position: damage):
            organizers.attack(self.game, self.middle - 1, organizer, self.middle)
        self.assertEqual((strong.hp, weak.hp), (9, 2))


class AreaTests(OccupancyTest):
    def blast(self, effect, power=50):
        self.game.land({"landing": self.middle, "effect": effect, "power": power})

    def test_a_bomb_hits_both_on_a_space(self):
        self.put(self.middle, enemies.DireRat())
        self.put(self.middle, enemies.DireRat())
        with mock.patch("cruel.core.gamemanager.FLOOR_BREAK_CHANCE", 0):
            self.blast("Explosive")
        self.assertEqual(self.at(self.middle), [])

    def test_fire_and_magic_hit_both_on_a_space(self):
        for effect in ("Fire", "Magic"):
            with self.subTest(effect=effect):
                first, second = self.put(self.middle, enemies.Goblin()), self.put(self.middle, enemies.Goblin())
                first.hp = second.hp = 100
                self.blast(effect, power=5)
                self.assertLess(first.hp, 100)
                self.assertLess(second.hp, 100)
                for unit in (first, second):
                    if unit in self.at(self.middle):
                        self.game.killEnemy(self.middle, killer=None, unit=unit)

    def test_a_bomb_hits_a_small_unit_under_a_giant_too(self):
        giant = enemies.FireGiant()
        self.game.putGiant(self.game.grid, self.middle, giant)
        self.game.EnemyPositions.add(self.middle)
        rat = self.put(self.middle + 1, enemies.DireRat())
        rat.hp = 100
        with mock.patch("cruel.core.gamemanager.FLOOR_BREAK_CHANCE", 0):
            self.blast("Explosive", power=5)
        self.assertLess(rat.hp, 100)

    def test_a_second_unit_that_is_burning_burns(self):
        self.put(self.middle, enemies.Goblin())
        second = self.put(self.middle, enemies.Goblin())
        second.hp, second.burnTurns = 100, 3
        self.game.stepBurning()
        self.assertEqual(second.burnTurns, 2)
        self.assertLess(second.hp, 100)


if __name__ == "__main__":
    unittest.main()
