"""Enemies: every enemy's stats, the special ones (Dire Moles, the Unsealed, Fire Giants, Organizers), facing and drops."""
import random
import unittest
from types import SimpleNamespace

from cruel.core import gamemanager
from cruel.entities import enemies
from cruel.inventory import items, loot

ALL_ENEMY_CLASSES = [enemies.Goblin, enemies.GoblinChief, enemies.DireRat, enemies.DireMole, enemies.Unsealed,
                     enemies.FireGiant, enemies.GoblinBuilder, enemies.GoblinFarmer, *enemies.organizers]
ROW_LENGTH = 10


def faceToward(enemy, fromPosition, toPosition):
    """gameManager.faceToward on a 10-wide map, without building a whole game."""
    smallMap = SimpleNamespace(rowLength=ROW_LENGTH)
    gamemanager.gameManager.faceToward(smallMap, enemy, fromPosition, toPosition)


class EnemyStatTests(unittest.TestCase):
    """Every enemy builds with sane stats."""

    def setUp(self):
        random.seed(10)

    def test_every_enemy_has_sane_stats(self):
        for enemyClass in ALL_ENEMY_CLASSES:
            enemy = enemyClass()
            self.assertTrue(enemy.name, enemyClass)
            self.assertGreater(enemy.hp, 0, enemy.name)
            self.assertEqual(enemy.maxHp, enemy.hp, enemy.name)
            self.assertGreaterEqual(enemy.ac, 0, enemy.name)
            self.assertGreater(enemy.speed, 0, enemy.name)
            self.assertGreater(enemy.damage, 0, enemy.name)
            self.assertGreaterEqual(enemy.wallDamage, 0, enemy.name)
            self.assertGreater(enemy.gold, 0, enemy.name)
            self.assertGreater(enemy.visionRange, 0, enemy.name)
            self.assertTrue(0 <= enemy.evasion < 1, enemy.name)
            self.assertEqual(enemy.cleanDodge, enemies.CLEAN_DODGE_BASE, enemy.name)

    def test_every_enemy_starts_wild_and_calm(self):
        for enemyClass in ALL_ENEMY_CLASSES:
            enemy = enemyClass()
            self.assertIsNone(enemy.faction, enemy.name)
            self.assertIsNone(enemy.foe, enemy.name)
            self.assertEqual(enemy.materials, {}, enemy.name)
            self.assertEqual(enemy.actionPool, 0.0, enemy.name)
            self.assertTrue(enemy.move, enemy.name)

    def test_enemy_names_are_unique(self):
        enemyNames = [enemyClass().name for enemyClass in ALL_ENEMY_CLASSES]
        self.assertEqual(len(enemyNames), len(set(enemyNames)))

    def test_only_enemies_with_wall_damage_can_dig(self):
        for enemyClass in ALL_ENEMY_CLASSES:
            enemy = enemyClass()
            self.assertEqual(bool(enemy.dig), enemy.wallDamage > 0, enemy.name)

    def test_each_enemy_gets_its_own_stats(self):
        firstGoblin, secondGoblin = enemies.Goblin(), enemies.Goblin()
        firstGoblin.hp -= 3
        self.assertEqual(secondGoblin.hp, 5)


class SpecialEnemyTests(unittest.TestCase):
    """The enemies with their own abilities."""

    def test_a_goblin_carries_one_piece_of_goblin_gear(self):
        random.seed(2)
        for _ in range(10):
            goblin = enemies.Goblin()
            self.assertEqual(len(goblin.inventory), 1)
            self.assertIn(goblin.inventory[0], items.goblinEquipmentList)

    def test_quick_enemies_move_at_fast_speed(self):
        for enemyClass in (enemies.DireRat, enemies.GoblinChief, enemies.Unsealed):
            self.assertEqual(enemyClass().speed, enemies.FAST)

    def test_dire_rats_are_hard_to_hit_and_see_far(self):
        direRat = enemies.DireRat()
        self.assertGreater(direRat.evasion, 0)
        self.assertEqual(direRat.visionRange, 7)

    def test_dire_moles_burrow_and_feel_tremors(self):
        direMole = enemies.DireMole()
        self.assertTrue(direMole.burrow)
        self.assertTrue(direMole.tremorSense)
        self.assertFalse(enemies.Goblin().burrow)

    def test_the_unsealed_see_everything_and_shrug_off_fire(self):
        unsealed = enemies.Unsealed()
        self.assertTrue(unsealed.allSight)
        self.assertEqual(unsealed.fireResistPercent, 0.8)

    def test_organizers_have_their_own_patterns_and_start_with_no_plan(self):
        random.seed(4)
        patterns = []
        for organizerClass in enemies.organizers:
            organizer = organizerClass()
            self.assertIsInstance(organizer, enemies.Organizer)
            self.assertIn("Organizer", organizer.name)
            self.assertIsNone(organizer.plan)
            self.assertEqual(organizer.built, set())
            self.assertTrue(0 <= organizer.rest <= 8)
            patterns.append(organizer.pattern)
        self.assertEqual(sorted(patterns), ["circle", "plant", "spiral", "square"])

    def test_expansion_goblins_start_with_nothing_to_do(self):
        self.assertIsNone(enemies.GoblinBuilder().task)
        self.assertEqual(enemies.GoblinBuilder().rest, 0)
        self.assertEqual(enemies.GoblinFarmer().rest, 0)

    def test_spawn_tables_are_sane(self):
        self.assertTrue(enemies.lowerFloorEnemies)
        self.assertTrue(0 < enemies.ORGANIZER_CHANCE < 1)
        fewestGiants, mostGiants = enemies.GIANT_COUNT
        self.assertTrue(0 < fewestGiants <= mostGiants)
        nearestSpawn, farthestSpawn = enemies.GIANT_SPAWN
        self.assertTrue(0 < nearestSpawn <= farthestSpawn)


class FireGiantTests(unittest.TestCase):
    """The Scorched Depths' Fire Giant."""

    def setUp(self):
        self.fireGiant = enemies.FireGiant()

    def test_a_fire_giant_fills_two_by_two_tiles(self):
        self.assertEqual(self.fireGiant.size, 2)
        self.assertIsNone(self.fireGiant.anchor)
        self.assertIsNone(self.fireGiant.home)

    def test_a_fire_giant_is_tougher_than_every_lower_floor_enemy(self):
        for enemyClass in enemies.lowerFloorEnemies:
            weakerEnemy = enemyClass()
            self.assertGreater(self.fireGiant.hp, weakerEnemy.hp)
            self.assertGreater(self.fireGiant.damage, weakerEnemy.damage)

    def test_a_fire_giant_is_slow_long_reaching_and_burns(self):
        self.assertLess(self.fireGiant.speed, 1)
        self.assertGreater(self.fireGiant.reach, 1)
        self.assertGreater(self.fireGiant.fireDamage, 0)
        self.assertTrue(0 < self.fireGiant.igniteChance <= 1)

    def test_fire_cannot_hurt_a_fire_giant(self):
        self.assertEqual(self.fireGiant.fireResistPercent, 1.0)

    def test_a_fire_giant_cannot_dig(self):
        self.assertFalse(self.fireGiant.dig)

    def test_a_fire_giant_pays_well_and_has_no_material_drops(self):
        self.assertEqual(self.fireGiant.gold, 60)
        self.assertEqual(loot.roll(loot.ENEMY_LOOT, self.fireGiant.name), [])


class FacingTests(unittest.TestCase):
    """Enemies turning to face the way they move (0 left, 1 right, 2 up, 3 down)."""

    def test_a_new_enemy_has_not_turned_yet(self):
        self.assertIsNone(getattr(enemies.Goblin(), "facing", None))

    def test_an_enemy_faces_the_way_it_moves(self):
        goblin = enemies.Goblin()
        start = 5 * ROW_LENGTH + 5
        for toPosition, expectedFacing in ((start - 1, 0), (start + 1, 1), (start - ROW_LENGTH, 2), (start + ROW_LENGTH, 3)):
            faceToward(goblin, start, toPosition)
            self.assertEqual(goblin.facing, expectedFacing)

    def test_staying_put_keeps_the_old_facing(self):
        goblin = enemies.Goblin()
        faceToward(goblin, 15, 16)
        faceToward(goblin, 16, 16)
        self.assertEqual(goblin.facing, 1)

    def test_a_diagonal_target_turns_toward_the_longer_side(self):
        goblin = enemies.Goblin()
        start = 5 * ROW_LENGTH + 5
        faceToward(goblin, start, start + 2 * ROW_LENGTH + 1)
        self.assertEqual(goblin.facing, 3)
        faceToward(goblin, start, start - ROW_LENGTH - 2)
        self.assertEqual(goblin.facing, 0)

    def test_a_fire_giant_turns_from_the_middle_of_its_body(self):
        fireGiant = enemies.FireGiant()
        fireGiant.anchor = 3 * ROW_LENGTH + 3  # it covers columns 3-4 of rows 3-4
        belowItsLeftFoot = 5 * ROW_LENGTH + 3
        faceToward(fireGiant, fireGiant.anchor, belowItsLeftFoot)
        self.assertEqual(fireGiant.facing, 3)
        rightOfItsHead = 3 * ROW_LENGTH + 6
        faceToward(fireGiant, fireGiant.anchor, rightOfItsHead)
        self.assertEqual(fireGiant.facing, 1)


class EnemyDropTests(unittest.TestCase):
    """What enemies drop when killed."""

    def test_every_lower_floor_enemy_has_a_drop_table(self):
        for enemyClass in enemies.lowerFloorEnemies + enemies.organizers + [enemies.Unsealed]:
            self.assertIn(enemyClass().name, loot.ENEMY_LOOT)

    def test_a_goblin_drops_only_bone_or_scrap(self):
        random.seed(12)
        for _ in range(100):
            for dropId, amount in loot.roll(loot.ENEMY_LOOT, enemies.Goblin().name):
                self.assertIn(dropId, ("bone", "scrap"))
                self.assertEqual(amount, 1)

    def test_the_plant_organizer_can_drop_thornward_gloves(self):
        random.seed(0)
        plantOrganizerName = enemies.PlantOrganizer().name
        everyDrop = {dropId for _ in range(400) for dropId, _ in loot.roll(loot.ENEMY_LOOT, plantOrganizerName)}
        self.assertIn("relic:thornward_gloves", everyDrop)


if __name__ == "__main__":
    unittest.main()
