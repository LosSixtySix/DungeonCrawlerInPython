"""The Potion Of Darkvision: Dew brewed into sight that reaches far in the dark, by no light (enemies aren't drawn to
it), and still stops at walls.

Unit tests; the rest are in tests/integration/test_darkvision.py."""
import unittest
from cruel.entities.playerClass import PlayerClass
from cruel.inventory import recipes
from tests.helpers.darkvision import darkvisionPotion, drink, recipe


class PotionTests(unittest.TestCase):
    def test_it_is_brewed_from_dew_at_the_alchemists_set(self):
        brew = recipe("darkvision")
        self.assertEqual(brew.station, "alchemist")
        self.assertIn("dew", brew.needs)
        potion = darkvisionPotion()
        self.assertEqual(potion.name, "Potion Of Darkvision")
        self.assertEqual((potion.effect, potion.bonus), ("Darkvision", recipes.DARKVISION_TURNS))

    def test_drinking_it_gives_darkvision_for_its_turns_then_it_wears_off(self):
        player = PlayerClass()
        drink(player)
        self.assertTrue(player.hasEffect("darkvision"))
        self.assertEqual(player.potionTurns(), [("darkvision", recipes.DARKVISION_TURNS)])
        self.assertNotIn("darkvision", player.gearEffects())
        for _ in range(recipes.DARKVISION_TURNS - 1):
            self.assertEqual(player.stepBuffs(), [])
        self.assertEqual(player.stepBuffs(), ["darkvision"])
        self.assertFalse(player.hasEffect("darkvision"))

    def test_another_one_tops_it_up_and_a_meal_does_not_wash_it_out(self):
        player = PlayerClass()
        drink(player)
        for _ in range(10):
            player.stepBuffs()
        drink(player)
        self.assertEqual(player.potionTurns(), [("darkvision", recipes.DARKVISION_TURNS)])
        meal = next(cooked for cooked in recipes.RECIPES if cooked.kind == "potion" and cooked.station == "cooking_pot").makeItem(0, 0)
        player.eat(meal)
        self.assertTrue(player.hasEffect("darkvision"))


if __name__ == "__main__":
    unittest.main()
