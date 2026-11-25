"""Crafting materials: the materials list, material stacks on the floor and the pouch limits."""
import unittest

from cruel.entities.playerClass import PlayerClass
from cruel.inventory import resources


class MaterialTableTests(unittest.TestCase):
    """The MATERIALS table and its groups."""

    def test_every_material_has_a_name_a_known_group_and_a_color(self):
        for materialId, (materialName, group, color) in resources.MATERIALS.items():
            self.assertTrue(materialName, materialId)
            self.assertIn(group, resources.GROUPS, materialId)
            self.assertEqual(len(color), 3, materialId)
            self.assertTrue(all(0 <= channel <= 255 for channel in color), materialId)

    def test_material_names_are_unique(self):
        materialNames = [materialName for materialName, _, _ in resources.MATERIALS.values()]
        self.assertEqual(len(materialNames), len(set(materialNames)))

    def test_every_group_has_materials(self):
        usedGroups = {group for _, group, _ in resources.MATERIALS.values()}
        self.assertEqual(usedGroups, set(resources.GROUPS))

    def test_gold_is_not_a_material_but_still_has_a_name(self):
        self.assertNotIn("gold", resources.MATERIALS)
        self.assertEqual(resources.materialName("gold"), "Gold")

    def test_material_name_looks_up_the_display_name(self):
        self.assertEqual(resources.materialName("copper_ore"), "Copper Ore")
        with self.assertRaises(KeyError):
            resources.materialName("unobtainium")

    def test_the_leather_pouch_limit_is_bigger_than_the_starting_one(self):
        self.assertGreater(resources.BIG_POUCH_LIMIT, resources.POUCH_LIMIT)
        self.assertGreater(resources.CHARCOAL_PER_COAL, 0)


class MaterialStackTests(unittest.TestCase):
    """Materials or gold lying in a pile on the floor."""

    def test_a_stack_is_named_by_its_amount_and_material(self):
        boneStack = resources.MaterialStack("bone", 3)
        self.assertEqual(boneStack.materialId, "bone")
        self.assertEqual(boneStack.amount, 3)
        self.assertEqual(boneStack.Etype, "Material")
        self.assertEqual(boneStack.name, "3 Bone")

    def test_a_stacks_name_follows_its_amount(self):
        boneStack = resources.MaterialStack("bone", 3)
        boneStack.amount = 1
        self.assertEqual(boneStack.name, "1 Bone")

    def test_a_gold_stack_is_named_gold(self):
        self.assertEqual(resources.MaterialStack("gold", 12).name, "12 Gold")


class PouchTests(unittest.TestCase):
    """How many of each material fit in the player's pouch."""

    def test_a_new_player_has_the_starting_pouch_limit(self):
        self.assertEqual(PlayerClass().pouchLimit, resources.POUCH_LIMIT)

    def test_the_pouch_stops_each_material_at_its_limit(self):
        player = PlayerClass()
        self.assertEqual(player.addMaterial("wood", 60), 60)
        self.assertEqual(player.addMaterial("wood", 60), resources.POUCH_LIMIT - 60)
        self.assertEqual(player.materials["wood"], resources.POUCH_LIMIT)
        self.assertEqual(player.addMaterial("wood", 5), 0)

    def test_each_material_has_its_own_limit(self):
        player = PlayerClass()
        player.addMaterial("wood", resources.POUCH_LIMIT)
        self.assertEqual(player.addMaterial("stone", 5), 5)

    def test_the_leather_pouch_raises_the_limit(self):
        player = PlayerClass()
        player.pouchLimit = resources.BIG_POUCH_LIMIT
        self.assertEqual(player.addMaterial("sand", 500), resources.BIG_POUCH_LIMIT)

    def test_adding_nothing_leaves_no_empty_entry(self):
        player = PlayerClass()
        self.assertEqual(player.addMaterial("wood", 0), 0)
        self.assertNotIn("wood", player.materials)


if __name__ == "__main__":
    unittest.main()
