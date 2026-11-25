"""Crafting: the recipe list, crafting stations, the quality roll for crafted gear and taking things apart."""
import random
import unittest

from cruel.entities.playerClass import PlayerClass
from cruel.entities import playerClass
from cruel.inventory import items, recipes, relics, resources
from cruel.world import plants

QUALITY_NAMES = [qualityName for qualityName, _ in recipes.QUALITIES]


def recipesOfKind(kind):
    return [recipe for recipe in recipes.RECIPES if recipe.kind == kind]


class RecipeListTests(unittest.TestCase):
    """Every recipe points at real materials, stations and effects."""

    def test_recipe_ids_are_unique(self):
        recipeIds = [recipe.id for recipe in recipes.RECIPES]
        self.assertEqual(len(recipeIds), len(set(recipeIds)))

    def test_every_ingredient_is_a_material_or_gold(self):
        for recipe in recipes.RECIPES:
            self.assertTrue(recipe.needs, recipe.id)
            for ingredient, count in recipe.needs.items():
                self.assertTrue(ingredient == "gold" or ingredient in resources.MATERIALS, (recipe.id, ingredient))
                self.assertGreater(count, 0, (recipe.id, ingredient))

    def test_every_recipe_is_made_at_a_known_station_and_takes_turns(self):
        for recipe in recipes.RECIPES:
            self.assertIn(recipe.station, recipes.STATION_INFO, recipe.id)
            self.assertGreater(recipe.turns, 0, recipe.id)

    def test_every_station_has_a_tab_name(self):
        self.assertEqual(set(recipes.TAB_NAMES), set(recipes.STATIONS))

    def test_material_recipes_make_real_materials(self):
        for recipe in recipesOfKind("material"):
            self.assertIn(recipe.makes, resources.MATERIALS, recipe.id)

    def test_plant_recipes_sow_real_plants(self):
        plantRecipes = recipesOfKind("plant")
        self.assertEqual({recipe.makes for recipe in plantRecipes}, set(plants.PLANTS))
        for recipe in plantRecipes:
            self.assertEqual(recipe.needs, {plants.PLANTS[recipe.makes]["seed"]: 1})

    def test_every_craftable_station_has_one_recipe_and_found_stations_have_none(self):
        for stationId, stationDetails in recipes.STATION_INFO.items():
            stationRecipe = recipes.stationRecipe(stationId)
            if stationId == "hand" or "found" in stationDetails:
                self.assertIsNone(stationRecipe, stationId)
            else:
                self.assertIsNotNone(stationRecipe, stationId)
                self.assertEqual(stationRecipe.makes, stationId)

    def test_every_station_can_be_reached_from_by_hand(self):
        reachable = {"hand"}
        for _ in range(len(recipes.STATIONS)):
            for recipe in recipesOfKind("station"):
                if recipe.station in reachable:
                    reachable.add(recipe.makes)
        foundStations = {stationId for stationId, stationDetails in recipes.STATION_INFO.items() if "found" in stationDetails}
        self.assertEqual(reachable | foundStations, set(recipes.STATIONS))

    def test_every_enchant_and_meal_buff_is_a_known_effect(self):
        for recipe in recipes.RECIPES:
            for enchant in recipe.enchants:
                self.assertIn(enchant, relics.EFFECTS, recipe.id)
        for mealId, _, _, needs, heal, buffs, _ in recipes.MEALS:
            self.assertGreater(heal, 0, mealId)
            for buff in buffs:
                self.assertIn(buff, relics.EFFECTS, mealId)

    def test_for_station_lists_only_that_stations_recipes(self):
        anvilRecipes = recipes.forStation("anvil")
        self.assertTrue(anvilRecipes)
        self.assertTrue(all(recipe.station == "anvil" for recipe in anvilRecipes))
        self.assertIn("iron_sword", [recipe.id for recipe in anvilRecipes])

    def test_fire_herbs_are_the_herbs_in_fire_recipes(self):
        self.assertEqual(recipes.FIRE_HERBS, {"emberroot"})

    def test_a_station_is_built_at_full_health(self):
        smelter = recipes.Station("smelter")
        self.assertEqual(smelter.name, "Smelter")
        self.assertEqual(smelter.hp, smelter.maxHp)
        self.assertEqual(smelter.maxHp, 60)
        self.assertTrue(smelter.claimed)
        self.assertFalse(recipes.Station("shrine", claimed=False).claimed)

    def test_setting_up_and_packing_take_the_stations_setup_turns(self):
        setupAnvil = recipes.setupRecipe("anvil")
        packAnvil = recipes.packRecipe("anvil")
        self.assertEqual((setupAnvil.id, setupAnvil.kind, setupAnvil.turns), ("setup_anvil", "setup", 2))
        self.assertEqual((packAnvil.id, packAnvil.kind, packAnvil.turns), ("pack_anvil", "pack", 2))
        self.assertEqual(setupAnvil.needs, {})


class QualityTests(unittest.TestCase):
    """The quality roll and how quality scales a crafted item's stats."""

    def test_with_no_intelligence_only_crude_and_common_can_roll(self):
        self.assertEqual(recipes.qualityOdds(0), [("Crude", 55), ("Common", 45), ("Fine", 0), ("Masterwork", 0)])

    def test_quality_odds_add_up_to_about_100(self):
        for intelligenceBonus in range(0, 40, 4):
            self.assertAlmostEqual(sum(percent for _, percent in recipes.qualityOdds(intelligenceBonus)), 100, delta=2)

    def test_intelligence_shifts_odds_away_from_crude(self):
        dullOdds = dict(recipes.qualityOdds(0))
        cleverOdds = dict(recipes.qualityOdds(12))
        self.assertLess(cleverOdds["Crude"], dullOdds["Crude"])
        self.assertGreater(cleverOdds["Masterwork"], dullOdds["Masterwork"])

    def test_crude_never_drops_below_five_weight(self):
        self.assertEqual(recipes.qualityWeights(1000)["Crude"], 5)

    def test_rolling_with_no_intelligence_never_gives_fine_or_better(self):
        random.seed(8)
        rolled = {recipes.rollQuality(0) for _ in range(300)}
        self.assertEqual(rolled, {"Crude", "Common"})

    def test_rolled_qualities_are_known_qualities(self):
        random.seed(9)
        for _ in range(200):
            self.assertIn(recipes.rollQuality(16), QUALITY_NAMES)

    def test_scale_stat_rounds_crude_down_and_the_rest_to_nearest(self):
        self.assertEqual(recipes.scaleStat(5, "Crude"), 3)        # 3.75 rounded down
        self.assertEqual(recipes.scaleStat(5, "Common"), 5)
        self.assertEqual(recipes.scaleStat(5, "Fine"), 6)         # 6.25
        self.assertEqual(recipes.scaleStat(5, "Masterwork"), 8)   # 7.5 rounds up

    def test_every_stat_is_at_least_one(self):
        self.assertEqual(recipes.scaleStat(1, "Crude"), 1)
        self.assertEqual(recipes.scaleStat(0, "Common"), 1)


class BuildTests(unittest.TestCase):
    """Recipe.build: the finished item at each quality."""

    def setUp(self):
        random.seed(21)

    def test_every_item_and_potion_recipe_builds_at_every_quality(self):
        for recipe in recipesOfKind("item") + recipesOfKind("potion"):
            for quality in QUALITY_NAMES:
                crafted = recipe.build(quality)
                self.assertIsInstance(crafted, items.equipment, recipe.id)
                self.assertEqual(crafted.recipeId, recipe.id)
                self.assertEqual(crafted.quality, quality)
                if recipe.kind == "potion":
                    self.assertEqual(crafted.Etype, "Consume", recipe.id)
                elif playerClass.isGlowPouch(crafted):  # carried, not worn
                    self.assertIsNone(crafted.slot, recipe.id)
                else:
                    self.assertIn(crafted.slot, ("Hands", "Head", "Neck", "Back", "Chest", "Belt", "Legs", "Feet",
                                                 "Gloves"), recipe.id)

    def test_common_gear_has_no_prefix_and_its_listed_stats(self):
        ironSword = recipes.RECIPES_BY_ID["iron_sword"].build("Common")
        self.assertEqual(ironSword.name, "Iron Sword")
        self.assertEqual(ironSword.bonus, 5)
        self.assertEqual(ironSword.Etype, "Damage")
        self.assertEqual(ironSword.enchants, [])

    def test_other_qualities_are_named_and_scaled(self):
        fineSword = recipes.RECIPES_BY_ID["iron_sword"].build("Fine")
        self.assertEqual(fineSword.name, "Fine Iron Sword")
        self.assertEqual(fineSword.baseName, "Iron Sword")
        self.assertEqual(fineSword.bonus, 6)

    def test_masterwork_gear_gets_a_free_minor_enchantment(self):
        masterworkSword = recipes.RECIPES_BY_ID["iron_sword"].build("Masterwork")
        self.assertEqual(len(masterworkSword.enchants), 1)
        self.assertIn(masterworkSword.enchants[0], relics.MINOR_ENCHANTS)
        self.assertEqual(masterworkSword.description, relics.describe(masterworkSword.enchants))

    def test_enchanted_recipes_keep_their_enchant(self):
        ironPick = recipes.RECIPES_BY_ID["iron_pick"].build("Common")
        self.assertEqual(ironPick.enchants, ["extra_ore"])
        self.assertEqual(ironPick.description, relics.describe(["extra_ore"]))

    def test_the_war_pick_scales_both_its_bonuses(self):
        crudeWarPick = recipes.RECIPES_BY_ID["war_pick"].build("Crude")
        self.assertEqual(crudeWarPick.Etype, "DaWa")
        self.assertEqual((crudeWarPick.bonus, crudeWarPick.b2), (3, 1))

    def test_a_backpack_adds_a_full_row_whatever_its_quality(self):
        for quality in QUALITY_NAMES:
            backpack = recipes.RECIPES_BY_ID["backpack"].build(quality)
            self.assertEqual((backpack.Etype, backpack.slot, backpack.bonus), ("Storage", "Back", recipes.BACKPACK_SLOTS))

    def test_a_meal_heals_and_carries_its_buffs(self):
        roastMeat = recipes.RECIPES_BY_ID["roast_meat"].build("Common")
        self.assertEqual(roastMeat.effect, "Meal")
        self.assertEqual(roastMeat.bonus, 3)
        self.assertEqual(roastMeat.buffs, {"hardy": 80})

    def test_a_healing_potion_scales_with_wisdom(self):
        healingPotion = recipes.RECIPES_BY_ID["healing"].build("Common")
        self.assertEqual((healingPotion.effect, healingPotion.bonus, healingPotion.attributeScaling), ("Heal", 6, "wisdom"))

    def test_the_glowrock_recipe_makes_a_glowrock(self):
        self.assertTrue(items.isGlowrock(recipes.RECIPES_BY_ID["glowrock"].build("Common")))


class SalvageTests(unittest.TestCase):
    """Taking crafted or found gear apart for some of its materials."""

    def test_salvage_percent_grows_with_intelligence_up_to_a_cap(self):
        self.assertEqual(recipes.salvagePercent(1), recipes.SALVAGE_BASE)
        self.assertEqual(recipes.salvagePercent(0), recipes.SALVAGE_BASE)
        self.assertEqual(recipes.salvagePercent(11), recipes.SALVAGE_BASE + 10 * recipes.SALVAGE_PER_INT)
        self.assertEqual(recipes.salvagePercent(10 ** 6), recipes.SALVAGE_MOST)

    def test_a_crafted_item_finds_its_recipe(self):
        fineSword = recipes.RECIPES_BY_ID["iron_sword"].build("Fine")
        self.assertIs(recipes.recipeFor(fineSword), recipes.RECIPES_BY_ID["iron_sword"])

    def test_found_gear_uses_its_stand_in_recipe(self):
        rustySwordRecipe = recipes.recipeFor(items.RustySword)
        self.assertEqual(rustySwordRecipe.kind, "found")
        self.assertEqual(rustySwordRecipe.needs, {"scrap": 4, "handle": 1})

    def test_every_randomly_rolled_gear_name_can_be_salvaged(self):
        random.seed(3)
        for gear in items.createRandomStatItems(1, "V"):
            if gear.Etype != "Consume":
                self.assertIn(gear.name, recipes.FOUND_SALVAGE)

    def test_found_salvage_needs_are_real_materials(self):
        for itemName, (turns, needs) in recipes.FOUND_SALVAGE.items():
            for ingredient in needs:
                self.assertIn(ingredient, resources.MATERIALS, itemName)

    def test_an_unknown_item_has_no_recipe(self):
        self.assertIsNone(recipes.recipeFor(items.equipment("Damage", "Mystery Rock", "Hands", 1)))

    def test_salvage_shares_are_the_percent_of_each_ingredient_per_item_made(self):
        doorPotions = recipes.RECIPES_BY_ID["door_potion_2"]  # makes two potions at once
        self.assertEqual(recipes.salvageShares(doorPotions, 50), {"glass": 0.5, "glowcap": 0.5, "coal": 0.25})

    def test_rolled_salvage_is_the_share_rounded_up_or_down(self):
        chainmail = recipes.RECIPES_BY_ID["chainmail"]  # 5 iron ingots: 25% is 1.25
        random.seed(13)
        for _ in range(50):
            self.assertIn(recipes.rollSalvage(chainmail, 25).get("iron_ingot", 0), (1, 2))

    def test_salvage_recipes_cover_only_gear_made_at_that_station(self):
        ironSword = recipes.RECIPES_BY_ID["iron_sword"].build("Common")
        roastMeat = recipes.RECIPES_BY_ID["roast_meat"].build("Common")
        relic = relics.make("lantern")
        pack = [ironSword, roastMeat, relic, items.RustySword]
        anvilSalvage = recipes.salvageRecipes("anvil", pack)
        self.assertEqual([recipe.target for recipe in anvilSalvage], [ironSword])
        self.assertEqual(anvilSalvage[0].makes, "iron_sword")
        self.assertEqual(anvilSalvage[0].turns, 1)  # half of 3, rounded down
        workbenchSalvage = recipes.salvageRecipes("workbench", pack)
        self.assertEqual([recipe.target for recipe in workbenchSalvage], [items.RustySword])
        self.assertEqual(recipes.salvageRecipes("cooking_pot", pack), [])  # meals can't be uncooked


class RelicStationTests(unittest.TestCase):
    """The Shrine of Unmaking's and the Gilded Forge's recipes."""

    def test_the_shrine_scraps_relics_only(self):
        lantern = relics.make("lantern")
        shrineRecipes = recipes.relicStationRecipes("shrine", [lantern, items.RustySword])
        self.assertEqual([(recipe.kind, recipe.target) for recipe in shrineRecipes], [("scrap", lantern)])
        self.assertEqual(shrineRecipes[0].needs, {"gold": recipes.SCRAP_GOLD})

    def test_the_forge_rekindles_relics_but_not_bound_ones(self):
        lantern = relics.make("lantern")
        moltenBlade = relics.make("molten_blade")
        forgeRecipes = recipes.relicStationRecipes("forge", [lantern, moltenBlade])
        self.assertEqual([(recipe.kind, recipe.target) for recipe in forgeRecipes], [("rekindle", lantern)])

    def test_the_forge_reforges_masterwork_gear_only(self):
        random.seed(1)
        masterworkSword = recipes.RECIPES_BY_ID["iron_sword"].build("Masterwork")
        commonSword = recipes.RECIPES_BY_ID["iron_sword"].build("Common")
        forgeRecipes = recipes.relicStationRecipes("forge", [masterworkSword, commonSword])
        self.assertEqual([(recipe.kind, recipe.target) for recipe in forgeRecipes], [("reforge", masterworkSword)])


class CraftingCostTests(unittest.TestCase):
    """Recipes against the player's pouch: having and spending what a recipe needs."""

    def test_a_player_with_the_materials_can_afford_the_workbench_and_spending_empties_the_pouch(self):
        player = PlayerClass()
        workbench = recipes.RECIPES_BY_ID["workbench"]
        self.assertFalse(player.hasMaterials(workbench.needs))
        player.addMaterial("wood", 6)
        player.addMaterial("stone", 4)
        self.assertTrue(player.hasMaterials(workbench.needs))
        self.assertFalse(player.hasMaterials(workbench.needs, times=2))
        player.spendMaterials(workbench.needs)
        self.assertEqual(player.materials, {})

    def test_gold_in_a_recipe_comes_out_of_the_players_gold(self):
        player = PlayerClass()
        gildedPick = recipes.RECIPES_BY_ID["gilded_pick"]
        player.addMaterial("handle", 1)
        player.addMaterial("iron_ingot", 3)
        player.gold = 40
        self.assertTrue(player.hasMaterials(gildedPick.needs))
        player.spendMaterials(gildedPick.needs)
        self.assertEqual(player.gold, 5)

    def test_charcoal_stands_in_for_missing_coal(self):
        player = PlayerClass()
        ironIngot = recipes.RECIPES_BY_ID["iron_ingot"]
        player.addMaterial("iron_ore", 2)
        player.addMaterial("charcoal", resources.CHARCOAL_PER_COAL)
        self.assertTrue(player.hasMaterials(ironIngot.needs))
        player.spendMaterials(ironIngot.needs)
        self.assertEqual(player.materials, {})


if __name__ == "__main__":
    unittest.main()
