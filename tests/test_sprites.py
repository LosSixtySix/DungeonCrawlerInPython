"""The pixel-art sprites: the 10x10 pictures, their palettes, turning them to face a way, and building every
picture for a floor theme."""
import unittest

import pygame

from cruel.graphics import sprites
from cruel.world import plants
from cruel.world import themes

LEFT, RIGHT, UP, DOWN = 0, 1, 2, 3


def everyMapPicture():
    """(name, rows, palette) for every one-tile picture that has a fixed palette."""
    pictures = [("Player", sprites.PLAYER, None), ("Chest", sprites.CHEST, None), ("Moonbeam", sprites.MOONBEAM, None),
                ("Glowrock", sprites.GLOWROCK, sprites.GLOWROCK_COLORS), ("Spawner", sprites.SPAWNER, sprites.SPAWNER_COLORS),
                ("Camp Chest", sprites.CAMP_CHEST, None), ("Sprout", sprites.SPROUT, None),
                ("Young Plant", sprites.YOUNG_PLANT, None), ("Seed Pods", sprites.SEED_PODS, sprites.SEED_POD_COLORS)]
    pictures += [(name, rows, palette) for name, (rows, palette) in sprites.ENEMY_SPRITES.items()]
    pictures += [(name, rows, palette) for name, (rows, palette) in sprites.STATION_SPRITES.items()]
    pictures += [(f"Pile {number}", rows, None) for number, (rows, _) in enumerate(sprites.PILE_SPRITES)]
    pictures += [(f"Pit {number}", rows, None) for number, rows in enumerate(sprites.PIT_STYLES)]
    pictures += [(f"Bonfire {number}", rows, sprites.BONFIRE_COLORS) for number, rows in enumerate(sprites.BONFIRE)]
    pictures += [(kind, rows, None) for kind, rows in sprites.PLANT_SPRITES.items()]
    return pictures


class PictureShapeTests(unittest.TestCase):
    """Every picture is a 10x10 grid, and every letter in it has a color."""

    def test_every_map_picture_is_ten_by_ten(self):
        for name, rows, _ in everyMapPicture():
            with self.subTest(picture=name):
                self.assertEqual(len(rows), 10)
                for row in rows:
                    self.assertEqual(len(row), 10)

    def test_every_letter_in_a_fixed_palette_picture_has_a_color(self):
        paletteRoles = set(sprites.enemyRoles(themes.randomTheme("Mixed").colors, {}))
        for name, rows, palette in everyMapPicture():
            if palette is None:
                continue
            with self.subTest(picture=name):
                letters = {letter for row in rows for letter in row} - {"."}
                self.assertLessEqual(letters, set(palette) | paletteRoles)

    def test_the_fire_giant_is_twenty_by_twenty(self):
        self.assertEqual(len(sprites.FIRE_GIANT), 20)
        self.assertTrue(all(len(row) == 20 for row in sprites.FIRE_GIANT))


class TurningTests(unittest.TestCase):
    """Rotating pictures so the player and enemies face the way they're going."""

    def test_four_quarter_turns_come_back_to_the_start(self):
        self.assertEqual(sprites.rotateClockwise(sprites.GOBLIN, 4), sprites.GOBLIN)

    def test_one_quarter_turn_moves_the_top_row_to_the_right_column(self):
        rows = ["ab", "cd"]
        self.assertEqual(sprites.rotateClockwise(rows, 1), ["ca", "db"])
        self.assertEqual(sprites.rotateClockwise(rows, 0), rows)

    def test_an_enemy_facing_its_drawn_way_is_not_turned(self):
        goblinRows = sprites.ENEMY_SPRITES["Goblin"][0]
        self.assertEqual(sprites.baseFacing("Goblin"), DOWN)
        self.assertEqual(sprites.facingRows(goblinRows, "Goblin", DOWN), goblinRows)
        self.assertNotEqual(sprites.facingRows(goblinRows, "Goblin", UP), goblinRows)

    def test_facing_up_is_a_half_turn_from_facing_down(self):
        goblinRows = sprites.ENEMY_SPRITES["Goblin"][0]
        self.assertEqual(sprites.facingRows(goblinRows, "Goblin", UP), sprites.rotateClockwise(goblinRows, 2))

    def test_organizers_are_round_and_never_turn(self):
        self.assertFalse(sprites.turns("Spiral Organizer"))
        organizerRows = sprites.organizerPicture(next(iter(sprites.ORGANIZER_EMBLEMS.values())))
        self.assertEqual(sprites.facingRows(organizerRows, "Spiral Organizer", LEFT), organizerRows)


class SurfaceTests(unittest.TestCase):
    """Turning pictures into pygame Surfaces."""

    def setUp(self):
        self.theme = themes.randomTheme("Mixed")

    def test_a_surface_is_scaled_to_the_tile_size(self):
        chestPalette = sprites.chestRoles(self.theme.colors, *sprites.CURSED_CHEST_COLOR)
        for tileSize in (10, 14, 20):
            surface = sprites.makeSurface(sprites.CHEST, chestPalette, tileSize)
            self.assertEqual(surface.get_size(), (tileSize, tileSize))

    def test_dots_are_left_transparent(self):
        rows = ["." * 10] * 9 + ["a" * 10]
        surface = sprites.makeSurface(rows, {"a": (255, 0, 0)}, 10)
        self.assertEqual(surface.get_at((0, 0)).a, 0)
        self.assertEqual(tuple(surface.get_at((0, 9))), (255, 0, 0, 255))

    def test_a_shadow_falls_down_and_to_the_right(self):
        rows = ["a" + "." * 9] + ["." * 10] * 9
        surface = sprites.makeShadowed(rows, {"a": (255, 0, 0)}, 10)
        self.assertEqual(tuple(surface.get_at((0, 0))), (255, 0, 0, 255))
        shadow = surface.get_at((1, 1))
        self.assertEqual((shadow.r, shadow.g, shadow.b), (0, 0, 0))
        self.assertGreater(shadow.a, 0)

    def test_the_player_is_drawn_in_cobalt_blue(self):
        playerPicture = sprites.makePlayer(self.theme.colors, DOWN, 10)
        colors = {tuple(playerPicture.get_at((x, y)))[:3] for x in range(10) for y in range(10)}
        self.assertIn(sprites.PLAYER_COLOR, colors)

    def test_a_big_picture_is_cut_into_one_piece_per_tile(self):
        giantPalette = sprites.enemyRoles(self.theme.colors, sprites.FIRE_GIANT_COLORS)
        quarters = sprites.makeGiantQuarters(sprites.FIRE_GIANT, giantPalette, 12)
        self.assertEqual(len(quarters), 4)
        for quarter in quarters:
            self.assertEqual(quarter.get_size(), (12, 12))

    def test_pits_and_holes_draw_at_tile_size(self):
        floorColor = self.theme.colors["floorStone"]
        for style in range(len(sprites.PIT_STYLES)):
            self.assertEqual(sprites.makePit(style, floorColor, 10).get_size(), (10, 10))
        self.assertEqual(sprites.makeHole("ns", 3, floorColor, 10).get_size(), (10, 10))

    def test_hole_shapes_are_repeatable_and_open_sides_have_no_lip(self):
        self.assertEqual(sprites.holeRows("e", 5), sprites.holeRows("e", 5))
        allOpen = sprites.holeRows("nesw", 1)
        self.assertNotIn("f", "".join(allOpen))  # no broken floor lip when every side is more hole
        closed = sprites.holeRows("", 1)
        self.assertNotIn("k", closed[0])  # with no hole above, the top edge is a lip of floor, never the black depth


class BuildSpritesTests(unittest.TestCase):
    """buildSprites makes every picture a floor needs, for any theme."""

    def test_every_theme_builds_a_full_sprite_set(self):
        for floorType in ("Mixed", "All Gold", "Mostly Wood", "Geode", "Iron Lode"):
            theme = themes.randomTheme(floorType)
            with self.subTest(theme=theme.name):
                pictures = sprites.buildSprites(theme.colors, 10)
                self.assertEqual(len(pictures["chests"]), len(sprites.CHEST_COLORS))
                self.assertEqual(set(pictures["player"]), set(sprites.PLAYER_TURNS))
                self.assertEqual(set(pictures["enemies"]), set(sprites.ENEMY_SPRITES))
                self.assertEqual(len(pictures["unsealed"]), sprites.SHARD_FRAMES)
                self.assertEqual(set(pictures["plants"]), set(sprites.PLANT_SPRITES))
                self.assertEqual(set(pictures["stations"]), set(sprites.STATION_SPRITES))
                for facing in sprites.FACINGS:
                    self.assertEqual(pictures["enemies"]["Goblin"][facing].get_size(), (10, 10))

    def test_every_plant_kind_has_a_picture(self):
        self.assertEqual(set(sprites.PLANT_SPRITES), set(plants.PLANTS))


class PickerTests(unittest.TestCase):
    """The helpers that pick a chest color, pit style or Unsealed frame."""

    def test_a_chest_keeps_its_color_and_colors_vary(self):
        picks = [sprites.chestColorFor(position) for position in range(200)]
        self.assertEqual(picks, [sprites.chestColorFor(position) for position in range(200)])
        self.assertTrue(all(0 <= pick < len(sprites.CHEST_COLORS) for pick in picks))
        self.assertEqual(len(set(picks)), len(sprites.CHEST_COLORS))

    def test_a_door_keeps_its_pit_style(self):
        for position in (0, 17, 4021):
            style = sprites.pitStyleFor(position)
            self.assertEqual(style, sprites.pitStyleFor(position))
            self.assertIn(style, range(len(sprites.PIT_STYLES)))

    def test_the_unsealed_shards_go_all_the_way_round(self):
        self.assertEqual(sprites.shardFrameFor(0), 0)
        self.assertEqual(sprites.shardFrameFor(sprites.SHARD_TURN_SECONDS / 2), sprites.SHARD_FRAMES // 2)
        self.assertEqual(sprites.shardFrameFor(sprites.SHARD_TURN_SECONDS), 0)

    def test_unsealed_frames_differ_as_the_shards_turn(self):
        colors = themes.randomTheme("Mixed").colors
        firstFrame = sprites.unsealedFrame(colors, 0)
        self.assertEqual(len(firstFrame), 10)
        self.assertNotEqual(firstFrame, sprites.unsealedFrame(colors, sprites.SHARD_FRAMES // 8))


if __name__ == "__main__":
    pygame.init()
    unittest.main()
