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
    pictures += [(f"Pitch Bolt {number}", rows, sprites.PITCH_BOLT_COLORS) for number, rows in enumerate(sprites.PITCH_BOLT_FLIGHT)]
    pictures += [(f"{unit} body {pose}", rows, sprites.BODY_COLORS[unit])
                 for unit, poses in sprites.BODY_SPRITES.items() for pose, rows in poses.items()]
    pictures += [(f"Pitch Hit {number}", rows, sprites.PITCH_BOLT_COLORS) for number, rows in enumerate(sprites.PITCH_BOLT_HIT)]
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


class CauldronTests(unittest.TestCase):
    """The cauldron is drawn from above: the brew inside its rim, the coals glowing out past it on every side."""

    def test_the_fire_shows_on_every_side(self):
        rows = sprites.CAULDRON
        fire = set("fF")
        self.assertTrue(fire & set(rows[0]), "top")
        self.assertTrue(fire & set(rows[-1]), "bottom")
        self.assertTrue(fire & {row[0] for row in rows}, "left")
        self.assertTrue(fire & {row[-1] for row in rows}, "right")

    def test_the_brew_is_inside_the_rim(self):
        rows = sprites.CAULDRON
        for number, row in enumerate(rows):
            for column, letter in enumerate(row):
                if letter in "gGw":
                    self.assertIn(row[column - 1], "gGwiI", (number, column))
                    self.assertIn(row[column + 1], "gGwiI", (number, column))
                    self.assertIn(rows[number - 1][column], "gGwiI", (number, column))
                    self.assertIn(rows[number + 1][column], "gGwiI", (number, column))

    def test_it_has_a_bubble(self):
        self.assertIn("w", "".join(sprites.CAULDRON))


class AnvilTests(unittest.TestCase):
    """The anvil is drawn from above, like everything on the map: its face on a round stump, not its side."""

    def test_the_stump_shows_above_and_below_the_face(self):
        rows = sprites.ANVIL
        self.assertIn("n", rows[0] + rows[1], "stump past the top of the face")
        self.assertIn("n", rows[-2] + rows[-1], "stump past the bottom of the face")

    def test_the_horn_points_out_of_the_middle_of_the_left_side(self):
        leftColumn = [row[0] for row in sprites.ANVIL]
        tipRows = [number for number, letter in enumerate(leftColumn) if letter != "."]
        self.assertEqual(tipRows, [4], "only the horn's tip reaches the left edge")
        self.assertIn(sprites.ANVIL[4][1], "iI", "metal just inside the tip")

    def test_the_hardy_hole_is_in_the_face(self):
        faceRow = sprites.ANVIL[4]
        hole = faceRow.index("h")
        self.assertIn(faceRow[hole - 1], "iI")
        self.assertIn(faceRow[hole + 1], "iI")


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
        colors = {tuple(playerPicture.get_at((pixelX, pixelY)))[:3] for pixelX in range(10) for pixelY in range(10)}
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


class PitchBoltTests(unittest.TestCase):
    """The Sealed Pattern's Pitch Bolt: a bullet-sized drop whose glint turns round it, then a three-frame hit."""

    def test_in_flight_it_is_bullet_sized(self):
        for rows in sprites.PITCH_BOLT_FLIGHT:
            filled = [(x, y) for y, row in enumerate(rows) for x, letter in enumerate(row) if letter != "."]
            width = max(x for x, _ in filled) - min(x for x, _ in filled) + 1
            height = max(y for _, y in filled) - min(y for _, y in filled) + 1
            self.assertLessEqual((width, height), (4, 4))

    def test_the_glint_turns_round_it(self):
        glints = [next((x, y) for y, row in enumerate(rows) for x, letter in enumerate(row) if letter == "s")
                  for rows in sprites.PITCH_BOLT_FLIGHT]
        self.assertEqual(len(set(glints)), 4, "a different corner each frame")

    def test_no_seal_gold(self):
        self.assertEqual(set(sprites.PITCH_BOLT_COLORS), {"p", "P", "s"})

    def test_the_frames_follow_the_clock(self):
        frameSeconds = sprites.PITCH_BOLT_FRAME_MS / 1000
        self.assertEqual([sprites.pitchBoltFrame(step * frameSeconds + 0.001) for step in range(5)], [0, 1, 2, 3, 0])
        self.assertEqual([sprites.pitchHitFrame(age) for age in (-0.5, 0, 0.4, 0.7, 1.0)], [0, 0, 1, 2, 2])

    def test_they_are_built_for_every_theme(self):
        pygame.init()
        built = sprites.buildSprites(themes.randomTheme("Mixed").colors, 20)
        self.assertEqual(len(built["pitchBolt"]), 4)
        self.assertEqual(len(built["pitchHit"]), 3)


class BodyTests(unittest.TestCase):
    """Dead bodies (bodies.py): the hand-drawn ones from the design sheet, the ones made from a unit's own picture,
    and how they look as they decay."""

    def test_the_drawn_units_have_every_pose(self):
        self.assertEqual(set(sprites.BODY_SPRITES), {"Goblin", "Goblin Chieftain", "Dire Rat", "Dire Mole", "Unsealed"})
        for unit, poses in sprites.BODY_SPRITES.items():
            self.assertEqual(set(poses), {"down", "side", "up", "bones"}, unit)

    def test_no_body_has_eyes(self):
        for unit, colors in sprites.BODY_COLORS.items():
            self.assertNotIn("e", colors, unit)

    def test_the_poses_differ(self):
        for unit, poses in sprites.BODY_SPRITES.items():
            self.assertEqual(len({tuple(poses[pose]) for pose in ("down", "side", "up")}), 3, unit)

    def test_enemy_names_find_their_bodies(self):
        self.assertIs(sprites.bodyPictures("Goblin Chieftan")[0], sprites.BODY_SPRITES["Goblin Chieftain"])
        self.assertIs(sprites.bodyPictures("Goblin Farmer")[0], sprites.BODY_SPRITES["Goblin"])

    def test_other_units_get_a_body_made_from_their_picture(self):
        rows, colors = sprites.ENEMY_SPRITES["Dweller Guard"]
        poses, bodyColors = sprites.bodyPictures("Dweller Guard")
        self.assertEqual(poses["down"], sprites.rotateClockwise(rows, 1))
        self.assertEqual(poses["up"], sprites.rotateClockwise(rows, 2))
        self.assertTrue(set("".join(poses["bones"])) <= {".", "o"})
        self.assertIn("o", "".join(poses["bones"]))
        self.assertLessEqual(set(colors), set(bodyColors))

    def test_a_giant_is_shrunk_to_one_tile(self):
        poses, _ = sprites.bodyPictures("Fire Giant")
        self.assertEqual((len(poses["down"]), len(poses["down"][0])), (10, 10))

    def test_anything_unknown_leaves_a_goblins_body(self):
        self.assertIs(sprites.bodyPictures("Nobody")[0], sprites.BODY_SPRITES["Goblin"])

    def test_fresh_it_looks_as_drawn(self):
        rows, palette, solid = sprites.bodyLook("Goblin", "side", 0, 0)
        self.assertEqual(rows, sprites.BODY_SPRITES["Goblin"]["side"])
        self.assertEqual(palette["c"], sprites.BODY_COLORS["Goblin"]["c"])
        self.assertEqual(solid, 1)

    def test_it_rots_then_turns_to_bones_then_fades(self):
        from cruel.world import bodies
        fresh = sprites.BODY_COLORS["Goblin"]["c"]
        rotted = sprites.bodyLook("Goblin", "down", bodies.ROT_FULL_TURNS, 0)[1]["c"]
        self.assertNotEqual(rotted, fresh)
        self.assertEqual(sprites.bodyLook("Goblin", "down", bodies.ROT_FULL_TURNS, 0)[1]["o"], sprites.BONE_COLORS["o"], "bones don't rot")
        halfway = sprites.bodyLook("Goblin", "down", (bodies.ROT_FULL_TURNS + bodies.SKELETAL_TURNS) // 2, 0)[0]
        down, bones = sprites.BODY_SPRITES["Goblin"]["down"], sprites.BODY_SPRITES["Goblin"]["bones"]
        fromBones = sum(1 for y in range(10) for x in range(10) if down[y][x] != bones[y][x] and halfway[y][x] == bones[y][x])
        differing = sum(1 for y in range(10) for x in range(10) if down[y][x] != bones[y][x])
        self.assertTrue(0.3 * differing < fromBones < 0.7 * differing, (fromBones, differing))
        self.assertEqual(sprites.bodyLook("Goblin", "down", bodies.SKELETAL_TURNS, 0)[0], bones)
        self.assertEqual(sprites.bodyLook("Goblin", "down", bodies.CRUMBLE_TURNS, 0)[2], 1)
        self.assertAlmostEqual(sprites.bodyLook("Goblin", "down", (bodies.CRUMBLE_TURNS + bodies.DECAY_TURNS) // 2, 0)[2], 0.5)

    def test_variants_lose_different_pixels_first(self):
        from cruel.world import bodies
        age = (bodies.ROT_FULL_TURNS + bodies.SKELETAL_TURNS) // 2
        looks = {tuple(sprites.bodyLook("Goblin", "down", age, variant)[0]) for variant in range(bodies.VARIANTS)}
        self.assertEqual(len(looks), bodies.VARIANTS)

    def test_it_is_drawn_turned_and_mirrored(self):
        pygame.init()
        colors = themes.randomTheme("Mixed").colors
        plain = sprites.makeBody(colors, "Goblin", "down", 0, 0, 0, False, 10)
        turned = sprites.makeBody(colors, "Goblin", "down", 0, 0, 1, False, 10)
        mirrored = sprites.makeBody(colors, "Goblin", "down", 0, 0, 0, True, 10)
        def pixels(surface):
            return [tuple(surface.get_at((x, y))) for y in range(10) for x in range(10)]
        self.assertNotEqual(pixels(plain), pixels(turned))
        self.assertNotEqual(pixels(plain), pixels(mirrored))
        from cruel.world import bodies
        crumbling = sprites.makeBody(colors, "Goblin", "bones", (bodies.CRUMBLE_TURNS + bodies.DECAY_TURNS) // 2, 0, 0, False, 10)
        self.assertEqual(crumbling.get_alpha(), 127)
