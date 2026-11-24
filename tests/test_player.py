"""The player: attributes and leveling, speed, equipment slots, damage, health, effects, potions, meals and the pouch."""
import random
import unittest

from cruel.entities import playerClass
from cruel.entities.playerClass import PlayerClass
from cruel.inventory import items, recipes, relics


def sword(bonus=3, scaling="strength"):
    return items.equipment("Damage", "Sword", "Hands", bonus, attributeScaling=scaling)


def pickAxe(bonus=2):
    return items.equipment("WallDamage", "Pick-Axe", "Hands", bonus, attributeScaling="strength")


def shield(bonus=2):
    return items.equipment("Defense", "Shield", "Hands", bonus, attributeScaling="strength")


def healingPotion(heal=4):
    return items.consumable("Healing Potion", heal, "Heal", attributeScaling="wisdom")


def potionBelt():
    return items.equipment(playerClass.POTION_STACK, "Potion Belt", "Belt", recipes.POTION_BELT_STACK)


def backpack():
    return items.equipment("Storage", "Backpack", "Back", recipes.BACKPACK_SLOTS)


def equip(player, item):
    """Puts item in the inventory and equips it from there, the way the Equipment window does."""
    player.inventory.append(item)
    player.equipItem(len(player.inventory) - 1)


class NewPlayerTests(unittest.TestCase):
    """What a fresh player starts with."""

    def test_a_new_player_starts_with_every_attribute_at_one_and_no_bonuses(self):
        player = PlayerClass()
        self.assertEqual(set(player.attributes.values()), {1})
        self.assertEqual(set(player.attributeBonuses.values()), {0})

    def test_a_new_player_has_ten_health_nothing_worn_and_no_gold(self):
        player = PlayerClass()
        self.assertEqual(player.getMaxHealth(), 10)
        self.assertEqual(player.getCurrentHealth(), 10)
        self.assertEqual(player.gold, 0)
        self.assertEqual(player.level, 0)
        self.assertTrue(all(worn == "None" for worn in player.equipment.values()))

    def test_a_new_player_has_every_slot_but_the_third_hand(self):
        player = PlayerClass()
        expectedSlots = [slot for slot in playerClass.SLOT_ORDER if slot != playerClass.EXTRA_HAND]
        self.assertEqual(list(player.equipment), expectedSlots)
        self.assertEqual(player.inventoryLimit, playerClass.BASE_INVENTORY)

    def test_bare_hands_hit_for_zero_to_one_and_dig_for_one(self):
        player = PlayerClass()
        self.assertEqual(player.getMinMaxDamage(), (0, 1))
        self.assertEqual(player.getWallDamage(), 1)

    def test_a_new_player_gets_exactly_one_action_a_turn(self):
        player = PlayerClass()
        self.assertEqual(player.getSpeed(), 1)
        self.assertEqual(player.actionsAllowed, 1)
        self.assertEqual(player.evasion(), 0)
        self.assertEqual(player.cleanDodge(), playerClass.CLEAN_DODGE_BASE)


class LevelUpTests(unittest.TestCase):
    """Spending gold to raise an attribute."""

    def test_leveling_up_needs_enough_gold(self):
        player = PlayerClass()
        player.gold = player.nextLevelGold - 1
        player.levelUp("strength")
        self.assertEqual(player.level, 0)
        self.assertEqual(player.attributes["strength"], 1)

    def test_leveling_up_spends_the_gold_and_raises_the_attribute_and_its_bonus(self):
        player = PlayerClass()
        self.assertEqual(player.nextLevelGold, 10)
        player.gold = 15
        player.levelUp("strength")
        self.assertEqual(player.level, 1)
        self.assertEqual(player.gold, 5)
        self.assertEqual(player.attributes["strength"], 2)
        self.assertEqual(player.attributeBonuses["strength"], 4)  # log2(2) * 4

    def test_each_level_costs_more(self):
        player = PlayerClass()
        costs = []
        for _ in range(5):
            costs.append(player.nextLevelGold)
            player.gold = player.nextLevelGold
            player.levelUp("wisdom")
        self.assertEqual(costs, sorted(costs))
        self.assertEqual(len(set(costs)), len(costs))

    def test_leveling_up_heals_you_fully(self):
        player = PlayerClass()
        player.damageTaken = 6
        player.gold = 100
        player.levelUp("dexterity")
        self.assertEqual(player.damageTaken, 0)

    def test_constitution_raises_max_health(self):
        player = PlayerClass()
        player.gold = 100
        player.levelUp("constitution")
        self.assertEqual(player.getMaxHealth(), 14)

    def test_dexterity_raises_speed_and_evasion(self):
        player = PlayerClass()
        player.gold = 100
        player.levelUp("dexterity")
        self.assertAlmostEqual(player.getSpeed(), 1 + 4 * playerClass.SPEED_PER_DEX_BONUS)
        self.assertAlmostEqual(player.evasion(), 4 * playerClass.EVASION_PER_DEX_BONUS)


class ActionTests(unittest.TestCase):
    """Actions each turn, and how fractional speed builds up into extra actions."""

    def test_with_one_action_every_action_ends_the_turn(self):
        player = PlayerClass()
        for _ in range(5):
            self.assertTrue(player.spendAction())

    def test_lightning_speed_gives_three_actions_a_turn(self):
        player = PlayerClass()
        player.equipment["Gloves"] = relics.make("lightning_vambraces")
        player.startRound()
        self.assertEqual(player.actionsAllowed, 3)
        self.assertFalse(player.spendAction())
        self.assertFalse(player.spendAction())
        self.assertTrue(player.spendAction())

    def test_fractional_speed_builds_into_an_extra_action(self):
        player = PlayerClass()
        player.attributeBonuses["dexterity"] = 25  # speed 1.25: one extra action every fourth turn
        player.actionPool = 0.0
        actionsPerTurn = []
        for _ in range(4):
            player.startRound()
            actionsPerTurn.append(player.actionsAllowed)
        self.assertEqual(actionsPerTurn, [1, 1, 1, 2])


class EquipmentTests(unittest.TestCase):
    """Putting gear on and taking it off."""

    def test_equipping_a_sword_raises_your_damage(self):
        player = PlayerClass()
        equip(player, sword(bonus=3))
        self.assertEqual(player.getMinMaxDamage(), (0, 4))
        self.assertEqual(player.inventory, [])
        self.assertTrue(player.actionMade)

    def test_strength_scaling_raises_both_ends_of_the_damage_range(self):
        player = PlayerClass()
        player.attributeBonuses["strength"] = 4
        equip(player, sword(bonus=3))
        self.assertEqual(player.getMinMaxDamage(), (4, 8))

    def test_dealt_damage_stays_in_the_range(self):
        random.seed(6)
        player = PlayerClass()
        player.attributeBonuses["strength"] = 4
        equip(player, sword(bonus=3))
        for _ in range(100):
            self.assertTrue(4 <= player.DealDamage() <= 8)

    def test_two_weapons_fill_both_hands_and_a_third_has_nowhere_to_go(self):
        player = PlayerClass()
        equip(player, sword(bonus=2))
        equip(player, sword(bonus=3))
        self.assertNotEqual(player.equipment["Right Hand"], "None")
        self.assertNotEqual(player.equipment["Left Hand"], "None")
        thirdSword = sword(bonus=9)
        equip(player, thirdSword)
        self.assertEqual(player.inventory, [thirdSword])
        self.assertEqual(player.getMinMaxDamage(), (0, 6))

    def test_a_pick_raises_wall_damage_with_strength(self):
        player = PlayerClass()
        player.attributeBonuses["strength"] = 4
        equip(player, pickAxe(bonus=2))
        self.assertEqual(player.getWallDamage(), 1 + 2 + 4)
        self.assertEqual(player.getMinMaxDamage(), (0, 1))  # a pick isn't a weapon

    def test_a_war_pick_both_fights_and_digs(self):
        player = PlayerClass()
        equip(player, items.dualEquipment("DaWa", "War Pick", "Hands", 4, 2, attributeScaling="strength"))
        self.assertEqual(player.getMinMaxDamage(), (0, 5))
        self.assertEqual(player.getWallDamage(), 3)

    def test_scaling_with_several_attributes_adds_them_together(self):
        player = PlayerClass()
        player.attributeBonuses["strength"] = 4
        player.attributeBonuses["intelligence"] = 6
        self.assertEqual(player.scalingBonus(relics.make("molten_blade")), 10)
        self.assertEqual(player.scalingBonus(sword(scaling=None)), 0)

    def test_a_shield_blocks_some_of_every_hit_but_never_all(self):
        player = PlayerClass()
        equip(player, shield(bonus=2))
        self.assertEqual(player.damageReduction(), 2)
        self.assertEqual(player.hitDamage(5), 3)
        self.assertEqual(player.hitDamage(1), 1)
        self.assertEqual(player.hitDamage(0), 0)

    def test_slots_for_hand_gear_and_other_gear(self):
        player = PlayerClass()
        self.assertEqual(player.slotsFor(sword()), ["Right Hand", "Left Hand"])
        helmet = items.equipment("Defense", "Helm", "Head", 1)
        self.assertEqual(player.slotsFor(helmet), ["Head"])
        self.assertEqual(player.slotsFor(items.equipment("Defense", "Tail Ring", "Tail", 1)), [])

    def test_unequipping_puts_the_item_back_in_the_inventory(self):
        player = PlayerClass()
        heldSword = sword()
        equip(player, heldSword)
        reason, spilled = player.unEquipItem("Right Hand")
        self.assertIsNone(reason)
        self.assertEqual(spilled, [])
        self.assertEqual(player.inventory, [heldSword])
        self.assertEqual(player.equipment["Right Hand"], "None")

    def test_unequipping_an_empty_slot_or_into_a_full_inventory_fails(self):
        player = PlayerClass()
        self.assertEqual(player.unEquipItem("Head"), ("Nothing there", []))
        equip(player, sword())
        player.inventory = [pickAxe() for _ in range(player.inventoryLimit)]
        self.assertEqual(player.unEquipItem("Right Hand"), ("Inventory full", []))
        self.assertNotEqual(player.equipment["Right Hand"], "None")

    def test_swapping_puts_the_old_item_where_the_new_one_was(self):
        player = PlayerClass()
        oldSword, newSword = sword(bonus=1), sword(bonus=5)
        equip(player, oldSword)
        player.inventory = [pickAxe(), newSword]
        spilled = player.swapEquip(1, "Right Hand")
        self.assertEqual(spilled, [])
        self.assertIs(player.equipment["Right Hand"], newSword)
        self.assertIs(player.inventory[1], oldSword)

    def test_the_burrowers_amulet_gives_burrow_while_worn(self):
        player = PlayerClass()
        equip(player, relics.make("burrowers_amulet"))
        self.assertTrue(player.burrow)
        self.assertTrue(player.hasEffect("burrow"))
        player.unEquipItem("Neck")
        self.assertFalse(player.burrow)
        self.assertFalse(player.hasEffect("burrow"))

    def test_health_gear_raises_max_health(self):
        player = PlayerClass()
        equip(player, items.equipment("Health", "Silver Amulet", "Neck", 3))
        self.assertEqual(player.getMaxHealth(), 13)

    def test_a_torch_in_hand_lights_further_and_can_be_seen(self):
        player = PlayerClass()
        self.assertFalse(player.holdingTorch())
        equip(player, items.equipment("Light", "Torch", "Hands", 2))
        self.assertTrue(player.holdingTorch())
        self.assertEqual(player.getVisionRange(), player.visionRange + 2)

    def test_clean_dodge_gear_adds_its_percent(self):
        player = PlayerClass()
        equip(player, items.equipment("CleanDodge", "Soft-Soled Boots", "Feet", 10))
        self.assertAlmostEqual(player.cleanDodge(), playerClass.CLEAN_DODGE_BASE + 0.10)


class BackpackAndThirdHandTests(unittest.TestCase):
    """Gear that adds room, and what spills when it comes off."""

    def test_a_backpack_adds_a_row_of_inventory(self):
        player = PlayerClass()
        equip(player, backpack())
        self.assertEqual(player.inventoryLimit, playerClass.BASE_INVENTORY + recipes.BACKPACK_SLOTS)

    def test_taking_off_a_full_backpack_spills_what_no_longer_fits(self):
        player = PlayerClass()
        equip(player, backpack())
        player.inventory = [pickAxe() for _ in range(player.inventoryLimit)]
        reason, spilled = player.unEquipItem("Back")
        self.assertIsNone(reason)
        self.assertEqual(player.inventoryLimit, playerClass.BASE_INVENTORY)
        self.assertEqual(len(player.inventory), playerClass.BASE_INVENTORY)
        self.assertEqual(len(spilled), recipes.BACKPACK_SLOTS + 1)  # the extra row, and then the backpack itself

    def test_the_vestigial_hand_holds_a_third_weapon_that_falls_into_the_pack_when_removed(self):
        player = PlayerClass()
        equip(player, relics.make("vestigial_hand"))
        thirdSword = sword(bonus=4)
        for heldSword in (sword(), sword(), thirdSword):
            equip(player, heldSword)
        self.assertIs(player.equipment[playerClass.EXTRA_HAND], thirdSword)
        player.unEquipItem("Back")
        self.assertNotIn(playerClass.EXTRA_HAND, player.equipment)
        self.assertIn(thirdSword, player.inventory)


class EffectTests(unittest.TestCase):
    """Effect tags from worn relics, enchantments and meal buffs."""

    def test_effects_come_from_relic_powers_and_enchants(self):
        player = PlayerClass()
        enchantedSword = sword()
        enchantedSword.enchants = ["lucky", "bright"]
        player.equipment["Right Hand"] = enchantedSword
        player.equipment["Head"] = relics.make("horned_crown")
        self.assertEqual(sorted(player.effects()), ["bright", "goblin_fear", "lucky"])
        self.assertTrue(player.hasEffect("goblin_fear"))
        self.assertFalse(player.hasEffect("ward"))

    def test_the_same_effect_twice_counts_twice(self):
        player = PlayerClass()
        for slot in ("Right Hand", "Left Hand"):
            brightSword = sword()
            brightSword.enchants = ["bright"]
            player.equipment[slot] = brightSword
        self.assertEqual(player.countEffect("bright"), 2)
        self.assertEqual(player.getVisionRange(), player.visionRange + 2)

    def test_gear_effects_leave_out_meal_buffs(self):
        player = PlayerClass()
        player.equipment["Head"] = relics.make("horned_crown")
        player.buffs = {"fed_guard": 10}
        self.assertEqual(sorted(player.effects()), ["fed_guard", "goblin_fear"])
        self.assertEqual(player.gearEffects(), ["goblin_fear"])

    def test_hardy_raises_max_health_and_fed_effects_raise_their_stats(self):
        player = PlayerClass()
        player.buffs = {"hardy": 5, "fed_strength": 5, "fed_dig": 5, "fed_guard": 5, "fed_fire": 5}
        self.assertEqual(player.getMaxHealth(), 12)
        self.assertEqual(player.getMinMaxDamage(), (2, 3))
        self.assertEqual(player.getWallDamage(), 3)
        self.assertEqual(player.damageReduction(), 1)
        self.assertEqual(player.fireResistance(), 2)

    def test_resistances_come_from_gear(self):
        player = PlayerClass()
        equip(player, items.equipment("FireRes", "Ember Ward Amulet", "Neck", 3))
        equip(player, items.equipment("MagicRes", "Warded Cloak", "Chest", 2))
        self.assertEqual(player.fireResistance(), 3)
        self.assertEqual(player.magicResistance(), 2)


class HealthAndGoldTests(unittest.TestCase):
    """Damage taken, healing, death and gold."""

    def test_taking_damage_lowers_current_health(self):
        player = PlayerClass()
        player.takeDamage(4)
        self.assertEqual(player.getCurrentHealth(), 6)

    def test_armor_takes_some_off_damage_taken(self):
        player = PlayerClass()
        equip(player, shield(bonus=2))
        player.takeDamage(5)
        self.assertEqual(player.damageTaken, 3)

    def test_enough_damage_brings_health_to_zero_or_below(self):
        player = PlayerClass()
        player.takeDamage(player.getMaxHealth())
        self.assertLessEqual(player.getCurrentHealth(), 0)

    def test_gold_can_be_gained_and_spent(self):
        player = PlayerClass()
        player.alterGold(25)
        player.alterGold(-10)
        self.assertEqual(player.gold, 15)
        self.assertEqual(player.have("gold"), 15)


class ConsumableTests(unittest.TestCase):
    """Drinking potions from the inventory."""

    def test_a_healing_potion_heals_with_wisdom_and_is_used_up(self):
        player = PlayerClass()
        player.attributeBonuses["wisdom"] = 2
        player.damageTaken = 8
        player.addItemToInventory(healingPotion(heal=4))
        player.useConsumable(0)
        self.assertEqual(player.damageTaken, 2)
        self.assertEqual(player.inventory, [])
        self.assertTrue(player.actionMade)

    def test_healing_never_goes_past_full_health(self):
        player = PlayerClass()
        player.damageTaken = 1
        player.addItemToInventory(healingPotion(heal=5))
        player.useConsumable(0)
        self.assertEqual(player.damageTaken, 0)

    def test_the_door_potion_reveals_the_door(self):
        player = PlayerClass()
        player.addItemToInventory(items.consumable("Potion Of Door", 0, "DoorLocate"))
        player.useConsumable(0)
        self.assertTrue(player.seeDoor)
        self.assertEqual(player.inventory, [])

    def test_using_gear_as_a_consumable_does_nothing(self):
        player = PlayerClass()
        player.inventory = [sword()]
        player.useConsumable(0)
        self.assertEqual(len(player.inventory), 1)
        self.assertFalse(player.actionMade)


class PotionStackTests(unittest.TestCase):
    """Potions stacking in one slot while a Potion Belt is worn."""

    def test_without_a_belt_each_potion_takes_its_own_slot(self):
        player = PlayerClass()
        player.addItemToInventory(healingPotion())
        player.addItemToInventory(healingPotion())
        self.assertEqual(len(player.inventory), 2)
        self.assertEqual(player.potionStackLimit(), 1)

    def test_with_a_belt_matching_potions_share_a_slot_up_to_the_limit(self):
        player = PlayerClass()
        equip(player, potionBelt())
        for _ in range(recipes.POTION_BELT_STACK + 1):
            player.addItemToInventory(healingPotion())
        self.assertEqual([playerClass.countOf(slot) for slot in player.inventory], [recipes.POTION_BELT_STACK, 1])

    def test_different_potions_do_not_stack(self):
        player = PlayerClass()
        equip(player, potionBelt())
        player.addItemToInventory(healingPotion(heal=4))
        player.addItemToInventory(healingPotion(heal=5))
        self.assertEqual(len(player.inventory), 2)

    def test_drinking_from_a_stack_takes_one(self):
        player = PlayerClass()
        equip(player, potionBelt())
        player.damageTaken = 9
        for _ in range(3):
            player.addItemToInventory(healingPotion(heal=1))
        player.useConsumable(0)
        self.assertEqual(playerClass.countOf(player.inventory[0]), 2)
        self.assertEqual(player.damageTaken, 8)

    def test_room_for_counts_space_left_on_stacks(self):
        player = PlayerClass()
        equip(player, potionBelt())
        player.addItemToInventory(healingPotion())
        freeSlots = player.inventoryLimit - 1
        self.assertEqual(player.roomFor(healingPotion()), freeSlots * recipes.POTION_BELT_STACK + recipes.POTION_BELT_STACK - 1)
        self.assertEqual(player.roomFor(sword()), freeSlots)

    def test_removing_the_belt_splits_stacks_back_into_slots(self):
        player = PlayerClass()
        equip(player, potionBelt())
        for _ in range(3):
            player.addItemToInventory(healingPotion())
        reason, spilled = player.unEquipItem("Belt")
        self.assertIsNone(reason)
        self.assertEqual(spilled, [])
        potions = [slot for slot in player.inventory if playerClass.isPotion(slot)]
        self.assertEqual([playerClass.countOf(potion) for potion in potions], [1, 1, 1])

    def test_meals_are_not_potions(self):
        roastMeat = recipes.RECIPES_BY_ID["roast_meat"].build("Common")
        self.assertFalse(playerClass.isPotion(roastMeat))
        self.assertTrue(playerClass.isPotion(healingPotion()))
        self.assertFalse(playerClass.isPotion("None"))


class MealTests(unittest.TestCase):
    """Eating meals and their buffs wearing off."""

    def makeMeal(self, mealId):
        return recipes.RECIPES_BY_ID[mealId].build("Common")

    def test_eating_heals_and_starts_the_buffs(self):
        player = PlayerClass()
        player.damageTaken = 5
        player.addItemToInventory(self.makeMeal("roast_meat"))
        player.useConsumable(0)
        self.assertEqual(player.damageTaken, 2)
        self.assertEqual(player.buffs, {"hardy": 80})
        self.assertEqual(player.meal, "Roast Meat")
        self.assertEqual(player.mealTurns(), 80)

    def test_a_new_meal_replaces_the_last_ones_buffs_but_not_its_drawbacks(self):
        player = PlayerClass()
        player.eat(self.makeMeal("demise_stew"))
        player.eat(self.makeMeal("roast_meat"))
        self.assertEqual(set(player.buffs), {"hardy", "fed_sick"})
        self.assertEqual(player.drawbacks(), [("fed_sick", 60)])

    def test_buffs_wear_off_and_the_meal_is_forgotten(self):
        player = PlayerClass()
        player.eat(self.makeMeal("glowcap_broth"))
        player.buffs["far_sight"] = 2
        self.assertEqual(player.stepBuffs(), [])
        self.assertEqual(player.stepBuffs(), ["far_sight"])
        self.assertEqual(player.buffs, {})
        self.assertIsNone(player.meal)

    def test_losing_hardy_never_kills_you(self):
        player = PlayerClass()
        player.eat(self.makeMeal("roast_meat"))
        player.buffs["hardy"] = 1
        player.damageTaken = player.getMaxHealth() - 1  # on 1 HP of 12
        player.stepBuffs()
        self.assertEqual(player.getCurrentHealth(), 1)

    def test_quickstep_skewers_raise_clean_dodge(self):
        player = PlayerClass()
        player.eat(self.makeMeal("quickstep_skewers"))
        self.assertAlmostEqual(player.cleanDodge(), playerClass.CLEAN_DODGE_BASE + playerClass.FOOTWORK_CLEAN_DODGE)


class PouchTests(unittest.TestCase):
    """Having and spending materials, with Charcoal covering for Coal."""

    def test_have_counts_every_three_charcoal_as_a_coal(self):
        player = PlayerClass()
        player.addMaterial("coal", 1)
        player.addMaterial("charcoal", 7)
        self.assertEqual(player.have("coal"), 3)
        self.assertEqual(player.have("charcoal"), 7)
        self.assertEqual(player.have("wood"), 0)

    def test_spending_coal_uses_real_coal_before_charcoal(self):
        player = PlayerClass()
        player.addMaterial("coal", 1)
        player.addMaterial("charcoal", 7)
        player.spendMaterials({"coal": 2})
        self.assertEqual(player.materials, {"charcoal": 4})

    def test_has_materials_checks_every_need_times_over(self):
        player = PlayerClass()
        player.addMaterial("wood", 4)
        self.assertTrue(player.hasMaterials({"wood": 2}, times=2))
        self.assertFalse(player.hasMaterials({"wood": 2}, times=3))
        self.assertFalse(player.hasMaterials({"wood": 1, "stone": 1}))


class MovementTests(unittest.TestCase):
    """Which tile types the player can walk onto."""

    def test_floor_is_walkable_but_blocked_tile_types_are_not(self):
        player = PlayerClass()
        self.assertTrue(player.checkValidMoveLocation(0))
        for blockedTile in (2, 3, 5, None):
            self.assertFalse(player.checkValidMoveLocation(blockedTile))


if __name__ == "__main__":
    unittest.main()
