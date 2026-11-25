"""Relics: the found-only items, their powers, which chests can hold them and the Gilded Forge's powers."""
import random
import unittest

from cruel.entities.playerClass import PlayerClass, SLOT_ORDER
from cruel.inventory import items, relics


class RelicTableTests(unittest.TestCase):
    """The RELICS table and the effect tables it relies on."""

    def test_every_relic_has_a_known_slot_and_power(self):
        validSlots = {"Hands", "Head", "Neck", "Back", "Chest", "Belt", "Legs", "Feet", "Gloves"}
        for relicId, relicInfo in relics.RELICS.items():
            self.assertIn(relicInfo["slot"], validSlots, relicId)
            self.assertIn(relicInfo["power"], relics.EFFECTS, relicId)
            self.assertGreaterEqual(relicInfo["bonus"], 0, relicId)

    def test_chest_relics_are_real_relics_and_the_molten_blade_is_not_one(self):
        chestRelicIds = [relicId for relicId, _, _ in relics.CHEST_RELICS]
        for relicId in chestRelicIds:
            self.assertIn(relicId, relics.RELICS)
        self.assertNotIn("molten_blade", chestRelicIds)

    def test_forge_powers_have_titles_and_effects(self):
        for power in relics.FORGE_POWERS:
            self.assertIn(power, relics.POWER_TITLES)
            self.assertIn(power, relics.EFFECTS)
        self.assertNotIn("burrow", relics.FORGE_POWERS)

    def test_minor_enchants_drawbacks_and_renames_point_at_known_effects(self):
        for tag in relics.MINOR_ENCHANTS + list(relics.DRAWBACKS) + list(relics.RENAMED_POWERS.values()):
            self.assertIn(tag, relics.EFFECTS)

    def test_effect_name_and_description(self):
        self.assertEqual(relics.effectName("half_swings"), "Mole-King")
        self.assertEqual(relics.effectName("not_a_power"), "not_a_power")
        self.assertEqual(relics.describe(["burrow", "far_sight"]), "Burrow through soft walls; +3 vision")
        self.assertEqual(relics.describe(["not_a_power"]), "")


class MakeRelicTests(unittest.TestCase):
    """relics.make: a fresh item for a relic id."""

    def test_every_relic_can_be_made(self):
        for relicId, relicInfo in relics.RELICS.items():
            relic = relics.make(relicId)
            self.assertTrue(relics.isRelic(relic))
            self.assertEqual(relic.relicId, relicId)
            self.assertEqual(relic.name, relicInfo["name"])
            self.assertEqual(relic.baseName, relicInfo["name"])
            self.assertEqual(relic.relicPower, relicInfo["power"])
            self.assertEqual(relic.slot, relicInfo["slot"])
            self.assertEqual(relic.bonus, relicInfo["bonus"])

    def test_each_made_relic_is_a_new_object(self):
        self.assertIsNot(relics.make("lantern"), relics.make("lantern"))

    def test_fighting_relics_scale_with_strength_and_others_with_nothing(self):
        self.assertEqual(relics.make("hollow_blade").attributeScaling, "strength")
        self.assertEqual(relics.make("horned_crown").attributeScaling, "strength")
        self.assertIsNone(relics.make("lantern").attributeScaling)
        self.assertIsNone(relics.make("seal_fragment").attributeScaling)

    def test_the_molten_blade_scales_with_strength_and_intelligence(self):
        self.assertEqual(relics.make("molten_blade").attributeScaling, ("strength", "intelligence"))

    def test_plain_gear_is_not_a_relic(self):
        self.assertFalse(relics.isRelic(items.RustySword))


class ChestRelicTests(unittest.TestCase):
    """Which relics a chest can hold on a given floor."""

    def test_floor_zero_of_a_normal_floor_holds_no_relics(self):
        self.assertEqual(relics.chestRelics(0, "Stone"), [])

    def test_the_seal_fragment_only_appears_on_all_gold_floors(self):
        self.assertIn("seal_fragment", relics.chestRelics(0, "All Gold"))
        self.assertNotIn("seal_fragment", relics.chestRelics(20, "Stone"))

    def test_deeper_floors_unlock_more_relics(self):
        self.assertNotIn("hollow_blade", relics.chestRelics(7, "Stone"))
        self.assertIn("hollow_blade", relics.chestRelics(8, "Stone"))
        self.assertLess(len(relics.chestRelics(2, "Stone")), len(relics.chestRelics(8, "Stone")))


class ForgePowerTests(unittest.TestCase):
    """The Gilded Forge turning gear into relics and rekindling powers."""

    def test_giving_a_power_renames_the_item_and_keeps_its_stats(self):
        sword = items.equipment("Damage", "Iron Sword", "Hands", 5, attributeScaling="strength")
        relics.givePower(sword, "lifedrinker")
        self.assertTrue(relics.isRelic(sword))
        self.assertEqual(sword.name, "Iron Sword of Thirst")
        self.assertEqual(sword.baseName, "Iron Sword")
        self.assertEqual((sword.bonus, sword.slot), (5, "Hands"))
        self.assertEqual(sword.description, relics.describe(["lifedrinker"]))

    def test_rekindling_does_not_stack_titles(self):
        sword = items.equipment("Damage", "Iron Sword", "Hands", 5)
        relics.givePower(sword, "lifedrinker")
        relics.givePower(sword, "gold_double")
        self.assertEqual(sword.name, "Iron Sword of Greed")

    def test_a_powered_items_description_lists_its_enchants_too(self):
        sword = items.equipment("Damage", "Iron Sword", "Hands", 5)
        sword.enchants = ["lucky"]
        relics.givePower(sword, "far_sight")
        self.assertEqual(sword.description, relics.describe(["far_sight", "lucky"]))

    def test_a_new_power_is_always_a_different_forge_power(self):
        random.seed(17)
        hornedCrown = relics.make("horned_crown")
        for _ in range(50):
            newPower = relics.newPower(hornedCrown)
            self.assertIn(newPower, relics.FORGE_POWERS)
            self.assertNotEqual(newPower, hornedCrown.relicPower)


class WornRelicTests(unittest.TestCase):
    """Relic powers showing up on the player while worn."""

    def wear(self, player, relicId, slot):
        player.equipment[slot] = relics.make(relicId)
        player.syncSlots()

    def test_a_worn_relic_gives_its_power(self):
        player = PlayerClass()
        self.assertFalse(player.hasEffect("half_swings"))
        self.wear(player, "mole_claws", "Gloves")
        self.assertTrue(player.hasEffect("half_swings"))

    def test_the_lantern_adds_its_light_to_vision(self):
        player = PlayerClass()
        visionBefore = player.getVisionRange()
        self.wear(player, "lantern", "Right Hand")
        self.assertEqual(player.getVisionRange(), visionBefore + 3)

    def test_the_vestigial_hand_grows_a_third_hand_slot(self):
        player = PlayerClass()
        self.assertNotIn("Third Hand", player.equipment)
        self.wear(player, "vestigial_hand", "Back")
        self.assertIn("Third Hand", player.equipment)
        self.assertEqual(list(player.equipment), [slot for slot in SLOT_ORDER if slot in player.equipment])

    def test_lightning_vambraces_add_speed(self):
        player = PlayerClass()
        speedBefore = player.getSpeed()
        self.wear(player, "lightning_vambraces", "Gloves")
        self.assertEqual(player.getSpeed(), speedBefore + relics.LIGHTNING_SPEED)

    def test_the_molten_blade_makes_you_fire_immune(self):
        player = PlayerClass()
        self.assertFalse(player.fireImmune())
        self.wear(player, "molten_blade", "Right Hand")
        self.assertTrue(player.fireImmune())
        self.assertGreaterEqual(player.fireResistance(), 10 ** 6)


if __name__ == "__main__":
    unittest.main()
