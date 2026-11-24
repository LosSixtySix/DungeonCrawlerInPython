"""Loot: the drop tables for walls, enemies and plants, and the rolls that use them."""
import random
import unittest

from cruel.entities import enemies
from cruel.inventory import loot, relics, resources
from cruel.world import plants

ENEMY_CLASSES = [enemies.Goblin, enemies.GoblinChief, enemies.DireRat, enemies.DireMole, enemies.Unsealed,
                 enemies.FireGiant, enemies.GoblinBuilder, enemies.GoblinFarmer, enemies.DewGrub, *enemies.organizers]


class FixedRandom:
    """Stands in for the random module so a wall roll lands exactly where the test wants it."""

    def __init__(self, roll):
        self.roll = roll

    def random(self):
        return self.roll


class DropTableTests(unittest.TestCase):
    """Every drop table points at things that exist."""

    def test_every_wall_drops_a_real_material_or_gold(self):
        for wallName, materialId in loot.WALL_LOOT.items():
            if materialId != "gold":  # Gold Walls pay gold coins, which aren't a pouch material
                self.assertIn(materialId, resources.MATERIALS, wallName)

    def test_every_drop_line_is_a_real_drop_with_a_sane_chance_and_amount(self):
        for tabName, dropTable in loot.LOOT_TABS:
            if dropTable is loot.WALL_LOOT:
                continue
            for source, dropLines in dropTable.items():
                for dropId, chance, (fewest, most) in dropLines:
                    self.assertTrue(0 < chance <= 100, (source, dropId))
                    self.assertTrue(1 <= fewest <= most, (source, dropId))
                    if loot.isRelicDrop(dropId):
                        self.assertIn(dropId[len("relic:"):], relics.RELICS)
                    elif dropId != "gold":
                        self.assertIn(dropId, resources.MATERIALS)
                    self.assertTrue(loot.dropName(dropId))
                    self.assertEqual(len(loot.dropColor(dropId)), 3)

    def test_every_enemy_drop_table_belongs_to_a_real_enemy(self):
        enemyNames = {enemyClass().name for enemyClass in ENEMY_CLASSES}
        for enemyName in loot.ENEMY_LOOT:
            self.assertIn(enemyName, enemyNames)

    def test_every_plant_has_a_harvest_and_a_seed_table_and_crops_give_more(self):
        for plantInfo in plants.PLANTS.values():
            for suffix, part in (("harvest", "herb"), ("seeds", "seed")):
                source = f"{plantInfo['name']} ({suffix})"
                self.assertEqual(loot.PLANT_LOOT[source], [(plantInfo[part], 100, (1, 2))])
                cropRange = (1 + loot.PLANTED_BONUS, 2 + loot.PLANTED_BONUS)
                self.assertEqual(loot.CROP_LOOT[source], [(plantInfo[part], 100, cropRange)])

    def test_misspelled_enemy_names_get_a_nicer_display_name(self):
        self.assertEqual(loot.displayName("Goblin Chieftan"), "Goblin Chieftain")
        self.assertEqual(loot.displayName("Dire Rat"), "Dire Rat")

    def test_gold_relics_and_materials_have_their_own_names_and_colors(self):
        self.assertEqual(loot.dropName("gold"), "Gold")
        self.assertEqual(loot.dropColor("gold"), loot.GOLD_COLOR)
        self.assertEqual(loot.dropName("relic:horned_crown"), "Horned Crown")
        self.assertEqual(loot.dropColor("relic:horned_crown"), loot.RELIC_COLOR)
        self.assertEqual(loot.dropName("wood"), "Wood")
        self.assertEqual(loot.dropColor("wood"), resources.MATERIALS["wood"][2])

    def test_discovery_keys_name_the_source_and_then_each_drop(self):
        self.assertEqual(loot.discoveryKey("Goblin"), "Goblin")
        self.assertEqual(loot.discoveryKey("Goblin", "bone"), "Goblin:bone")


class WallDropTests(unittest.TestCase):
    """What breaking a wall gives, and how Wisdom helps."""

    def test_only_names_ending_in_vein_are_veins(self):
        self.assertTrue(loot.isVein("Iron Vein"))
        self.assertFalse(loot.isVein("Stone Wall"))

    def test_walls_give_zero_to_two_veins_one_to_three_and_gold_walls_exactly_one(self):
        self.assertEqual(loot.wallRange("Stone Wall"), (0, 2))
        self.assertEqual(loot.wallRange("Copper Vein"), (1, 3))
        self.assertEqual(loot.wallRange("Gold Wall"), (1, 1))

    def test_wall_odds_always_add_up_to_100_percent(self):
        for wisdom in range(1, 40):
            self.assertAlmostEqual(sum(loot.wallOdds(wisdom)), 100)

    def test_one_wisdom_or_less_gives_the_base_odds(self):
        self.assertEqual(loot.wallOdds(1), loot.WALL_AMOUNTS)
        self.assertEqual(loot.wallOdds(0), loot.WALL_AMOUNTS)

    def test_wisdom_lowers_the_chance_of_nothing_down_to_a_floor(self):
        self.assertAlmostEqual(loot.wallOdds(3)[0], loot.WALL_AMOUNTS[0] - 2 * loot.WISDOM_LUCK)
        self.assertLess(loot.wallOdds(5)[0], loot.wallOdds(2)[0])
        self.assertEqual(loot.wallOdds(1000)[0], loot.LEAST_NOTHING)

    def test_odds_taken_from_nothing_are_shared_in_the_15_to_5_ratio(self):
        chanceOfOne, chanceOfTwo = loot.wallOdds(1000)[1:]
        self.assertAlmostEqual(chanceOfOne / chanceOfTwo, 3)

    def test_every_wall_drop_is_its_material_in_its_range(self):
        random.seed(7)
        for wallName in loot.WALL_LOOT:
            fewest, most = loot.wallRange(wallName)
            for _ in range(50):
                drops = loot.rollWall(wallName, 1)
                if not drops:
                    self.assertEqual(fewest, 0, wallName)
                    continue
                [(materialId, amount)] = drops
                self.assertEqual(materialId, loot.WALL_LOOT[wallName])
                self.assertTrue(max(1, fewest) <= amount <= most, wallName)

    def test_a_gold_wall_always_gives_exactly_one_gold(self):
        random.seed(1)
        for _ in range(20):
            self.assertEqual(loot.rollWall("Gold Wall", 1), [("gold", 1)])

    def test_an_unknown_wall_gives_nothing(self):
        self.assertEqual(loot.rollWall("Not A Wall", 5), [])

    def test_the_roll_picks_least_middle_or_most(self):
        realRandom = loot.random
        try:
            loot.random = FixedRandom(0.0)
            self.assertEqual(loot.rollWall("Stone Wall", 1), [])
            self.assertEqual(loot.rollWall("Iron Vein", 1), [("iron_ore", 1)])
            loot.random = FixedRandom(0.85)
            self.assertEqual(loot.rollWall("Stone Wall", 1), [("stone", 1)])
            loot.random = FixedRandom(0.99)
            self.assertEqual(loot.rollWall("Iron Vein", 1), [("iron_ore", 3)])
        finally:
            loot.random = realRandom

    def test_more_wisdom_gives_more_stone_on_average(self):
        def stoneFromWalls(wisdom):
            random.seed(99)
            return sum(amount for _ in range(2000) for _, amount in loot.rollWall("Stone Wall", wisdom))
        self.assertGreater(stoneFromWalls(10), stoneFromWalls(1))


class EnemyDropTests(unittest.TestCase):
    """loot.roll on the enemy table."""

    def test_a_certain_drop_always_drops(self):
        random.seed(3)
        for _ in range(30):
            unsealedDrops = dict(loot.roll(loot.ENEMY_LOOT, "Unsealed"))
            self.assertIn("gold", unsealedDrops)
            self.assertTrue(10 <= unsealedDrops["gold"] <= 20)

    def test_every_drop_comes_from_its_table_in_range(self):
        random.seed(4)
        for enemyName, dropLines in loot.ENEMY_LOOT.items():
            amountRanges = {dropId: amountRange for dropId, _, amountRange in dropLines}
            for _ in range(30):
                for dropId, amount in loot.roll(loot.ENEMY_LOOT, enemyName):
                    fewest, most = amountRanges[dropId]
                    self.assertTrue(fewest <= amount <= most, (enemyName, dropId))

    def test_an_enemy_without_a_table_drops_nothing(self):
        self.assertEqual(loot.roll(loot.ENEMY_LOOT, "Nobody"), [])

    def test_drop_chance_is_roughly_the_listed_percent(self):
        random.seed(11)
        kills = 4000
        meatDrops = sum(any(dropId == "meat" for dropId, _ in loot.roll(loot.ENEMY_LOOT, "Dire Rat"))
                        for _ in range(kills))
        self.assertTrue(0.45 < meatDrops / kills < 0.55)


class PlantPickTests(unittest.TestCase):
    """What picking a ripe plant gives."""

    def test_plant_source_names_the_plant_and_its_stage(self):
        bloodcap = plants.Plant("bloodcap")
        self.assertEqual(loot.plantSource(bloodcap, "harvest"), "Bloodcap (harvest)")
        self.assertEqual(loot.plantSource(bloodcap, "seed"), "Bloodcap (seeds)")

    def test_a_wild_plant_gives_one_or_two_of_its_herb_or_seed(self):
        random.seed(2)
        for kind, plantInfo in plants.PLANTS.items():
            wildPlant = plants.Plant(kind)
            for _ in range(10):
                [(herbId, herbCount)] = loot.rollPick(wildPlant, "harvest")
                self.assertEqual(herbId, plantInfo["herb"])
                self.assertIn(herbCount, (1, 2))
                [(seedId, seedCount)] = loot.rollPick(wildPlant, "seed")
                self.assertEqual(seedId, plantInfo["seed"])
                self.assertIn(seedCount, (1, 2))

    def test_a_planted_crop_gives_one_more(self):
        random.seed(2)
        glowcapCrop = plants.Plant("glowcap", planted=True)
        for _ in range(20):
            [(herbId, herbCount)] = loot.rollPick(glowcapCrop, "harvest")
            self.assertEqual(herbId, "glowcap")
            self.assertIn(herbCount, (2, 3))


if __name__ == "__main__":
    unittest.main()
