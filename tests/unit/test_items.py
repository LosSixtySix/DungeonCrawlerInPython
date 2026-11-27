"""Items: the equipment classes, the starting gear, randomly rolled gear and item piles on the floor."""
import random
import unittest

from cruel.inventory import items

VALID_SLOTS = {"Hands", "Head", "Neck", "Back", "Chest", "Belt", "Legs", "Feet", "Gloves"}


class EquipmentClassTests(unittest.TestCase):
    """The equipment, consumable and dual-bonus item classes."""

    def test_equipment_keeps_everything_it_was_made_with(self):
        blade = items.equipment("Damage", "Test Blade", "Hands", 4, "sharp", attributeScaling="strength")
        self.assertEqual(blade.Etype, "Damage")
        self.assertEqual(blade.name, "Test Blade")
        self.assertEqual(blade.slot, "Hands")
        self.assertEqual(blade.bonus, 4)
        self.assertEqual(blade.description, "sharp")
        self.assertEqual(blade.attributeScaling, "strength")

    def test_equipment_without_description_or_scaling_uses_defaults(self):
        helmet = items.equipment("Defense", "Plain Helm", "Head", 1)
        self.assertEqual(helmet.description, "None")
        self.assertIsNone(helmet.attributeScaling)

    def test_a_consumable_is_a_slotless_consume_item(self):
        tonic = items.consumable("Tonic", 3, "Heal", attributeScaling="wisdom")
        self.assertIsInstance(tonic, items.equipment)
        self.assertEqual(tonic.Etype, "Consume")
        self.assertIsNone(tonic.slot)
        self.assertEqual(tonic.bonus, 3)
        self.assertEqual(tonic.effect, "Heal")
        self.assertEqual(tonic.attributeScaling, "wisdom")

    def test_dual_equipment_carries_two_bonuses(self):
        warPick = items.dualEquipment("DaWa", "War Pick", "Hands", 4, 2, attributeScaling="strength")
        self.assertEqual(warPick.Etype, "DaWa")
        self.assertEqual(warPick.bonus, 4)
        self.assertEqual(warPick.b1, 4)
        self.assertEqual(warPick.b2, 2)

    def test_get_item_name_returns_the_items_name(self):
        self.assertEqual(items.getItemName(items.RustySword), "Rusty Sword")


class StartingGearTests(unittest.TestCase):
    """The gear and potions defined once at import time."""

    def test_the_starting_pick_is_a_weak_strength_scaling_hand_pick(self):
        startingPick = items.startingPick
        self.assertEqual(startingPick.Etype, "WallDamage")
        self.assertEqual(startingPick.slot, "Hands")
        self.assertEqual(startingPick.attributeScaling, "strength")
        self.assertIn(startingPick.bonus, (1, 2))

    def test_the_healing_potion_heals_one_to_five_scaled_by_wisdom(self):
        self.assertEqual(items.HealingPotion.Etype, "Consume")
        self.assertEqual(items.HealingPotion.effect, "Heal")
        self.assertEqual(items.HealingPotion.attributeScaling, "wisdom")
        self.assertTrue(1 <= items.HealingPotion.bonus <= 5)

    def test_the_door_potion_locates_the_door(self):
        self.assertEqual(items.LocateDoorPotion.effect, "DoorLocate")
        self.assertEqual(items.LocateDoorPotion.bonus, 0)

    def test_goblins_only_carry_hand_gear(self):
        self.assertTrue(items.goblinEquipmentList)
        for goblinGear in items.goblinEquipmentList:
            self.assertEqual(goblinGear.slot, "Hands")


class RandomStatItemTests(unittest.TestCase):
    """createRandomStatItems: batches of gear with rolled bonuses."""

    def setUp(self):
        random.seed(1234)

    def test_varied_quality_makes_nine_items_per_round(self):
        self.assertEqual(len(items.createRandomStatItems(3, "V")), 27)

    def test_low_quality_makes_three_weak_hand_items_per_round(self):
        lowQualityGear = items.createRandomStatItems(4, "L")
        self.assertEqual(len(lowQualityGear), 12)
        for gear in lowQualityGear:
            self.assertTrue(1 <= gear.bonus <= 3, gear.name)
            self.assertEqual(gear.slot, "Hands")

    def test_varied_gear_has_valid_slots_and_bonuses(self):
        for gear in items.createRandomStatItems(20, "V"):
            if gear.Etype == "Consume":
                self.assertIn(gear.effect, ("Heal", "DoorLocate"))
                continue
            self.assertIn(gear.slot, VALID_SLOTS)
            self.assertEqual(gear.attributeScaling, "strength")
            self.assertTrue(1 <= gear.bonus <= 5, gear.name)
            if gear.Etype == "DaWa":
                self.assertTrue(3 <= gear.b1 <= 5)
                self.assertTrue(1 <= gear.b2 <= 3)

    def test_strong_gear_rolls_three_to_five(self):
        strongNames = ("Sword", "Steel Pick-Axe", "Tear Sheild")
        for gear in items.createRandomStatItems(30, "V"):
            if gear.name in strongNames:
                self.assertTrue(3 <= gear.bonus <= 5, gear.name)

    def test_unfinished_qualities_and_zero_rounds_make_nothing(self):
        self.assertEqual(items.createRandomStatItems(2, "H"), [])
        self.assertEqual(items.createRandomStatItems(2, "M"), [])
        self.assertEqual(items.createRandomStatItems(0, "V"), [])

    def test_every_rolled_item_is_its_own_object(self):
        gearBatch = items.createRandomStatItems(2, "L")
        self.assertEqual(len({id(gear) for gear in gearBatch}), len(gearBatch))


class GlowrockAndPileTests(unittest.TestCase):
    """Item piles on the floor and the Glowrocks that light them."""

    def makeGlowrock(self):
        return items.consumable("Glowrock", 0, items.GLOW)

    def test_only_a_glow_effect_counts_as_a_glowrock(self):
        self.assertTrue(items.isGlowrock(self.makeGlowrock()))
        self.assertFalse(items.isGlowrock(items.HealingPotion))
        self.assertFalse(items.isGlowrock(items.RustySword))  # plain gear has no effect attribute at all

    def test_a_new_pile_is_empty_with_a_valid_look(self):
        random.seed(5)
        pile = items.ItemPile()
        self.assertEqual(pile.items, [])
        self.assertEqual(pile.gold, 0)
        self.assertIn(pile.look, range(items.PILE_LOOKS))

    def test_a_pile_copies_its_item_list_and_keeps_its_look_and_gold(self):
        droppedItems = [items.RustySword]
        pile = items.ItemPile(droppedItems, look=2, gold=7)
        droppedItems.append(items.Pick)
        self.assertEqual(pile.items, [items.RustySword])
        self.assertEqual(pile.look, 2)
        self.assertEqual(pile.gold, 7)

    def test_a_pile_glows_when_it_holds_a_glowrock(self):
        self.assertTrue(items.pileGlows(items.ItemPile([items.RustySword, self.makeGlowrock()])))
        self.assertFalse(items.pileGlows(items.ItemPile([items.RustySword])))
        self.assertFalse(items.pileGlows(object()))

    def test_a_pile_is_only_glowrocks_when_it_has_nothing_else_and_no_gold(self):
        self.assertTrue(items.onlyGlowrocks(items.ItemPile([self.makeGlowrock(), self.makeGlowrock()])))
        self.assertFalse(items.onlyGlowrocks(items.ItemPile([self.makeGlowrock()], gold=1)))
        self.assertFalse(items.onlyGlowrocks(items.ItemPile([self.makeGlowrock(), items.RustySword])))
        self.assertFalse(items.onlyGlowrocks(items.ItemPile()))

    def test_pile_limits_are_positive(self):
        self.assertGreater(items.PILE_LIMIT, 0)
        self.assertGreater(items.PILE_GOLD_LIMIT, 0)


if __name__ == "__main__":
    unittest.main()
