"""Dead bodies (bodies.py): a dying unit leaves its body instead of an item pile, holding its loot
(gameManager.leaveBody). Searching it rolls it over (searchBody), it stays when emptied, and it decays until it's gone
at bodies.DECAY_TURNS (stepBodies), by gameManager.worldTurn, which is saved.

Integration tests."""
import os
import random
import tempfile
import unittest
from unittest import mock

import pygame

from cruel.core import gamemanager
from cruel.entities.enemies import DireMole, DireRat, Goblin, GoblinChief
from cruel.inventory import items, relics, resources
from cruel.world import bodies, expansion, occupancy, plants, wall
from tests.helpers.gamemanager import CHEST, ENEMY, FLOOR, PILE, RIGHT, WALL, keyDown, newGame, standInOpenFloor


def potion():
    return items.consumable("Healing Potion", 3, "Heal")


def remainsOf(pile):
    """The materials lying in a pile: [(material, amount)]."""
    return [(item.materialId, item.amount) for item in pile.items if isinstance(item, resources.MaterialStack)]


class BodyTest(unittest.TestCase):
    def setUp(self):
        game = self.game = newGame()
        self.here = standInOpenFloor(game, facing=RIGHT)
        self.besideYou = self.here + 1
        game.messageBools = {name: False for name in game.messageBools}

    def putEnemy(self, spot, enemy):
        self.game.grid[spot] = [ENEMY, 1, enemy]
        self.game.EnemyPositions.add(spot)
        return enemy

    def killBesideYou(self, enemy=None, killer="player"):
        enemy = self.putEnemy(self.besideYou, enemy or Goblin())
        self.game.killEnemy(self.besideYou, killer=killer)
        return self.game.bodyAt(self.besideYou)

    def search(self):
        """Interact with what you face, the way the game loop would have it ready (roomItems)."""
        game = self.game
        game.setLookPosition()
        game.roomItems = game.getItemsFromGrid()
        keyDown(game, pygame.K_e)


class LeavingABodyTests(BodyTest):
    def test_a_kill_leaves_the_units_body(self):
        self.game.worldTurn = 37
        body = self.killBesideYou()
        self.assertEqual(self.game.grid[self.besideYou][0], PILE)
        self.assertIsInstance(body, bodies.Body)
        self.assertEqual((body.unitName, body.diedTurn, body.pose), ("Goblin", 37, "down"))

    def test_its_loot_is_on_the_body(self):
        goblin = Goblin()
        goblin.loot = [potion()]
        body = self.killBesideYou(goblin)
        self.assertEqual([item.name for item in body.items], ["Healing Potion"])

    def test_a_relic_it_drops_lies_on_its_body(self):
        with mock.patch("cruel.inventory.loot.roll", return_value=[("relic:lantern", 1)]):
            body = self.killBesideYou()
        self.assertEqual([getattr(item, "relicId", None) for item in body.items], ["lantern"])

    def test_with_nothing_to_drop_there_is_still_a_body(self):
        body = self.killBesideYou()
        self.assertEqual((body.items, body.gold), ([], 0))

    def test_killed_by_something_else_its_spilled_gold_lies_on_it(self):
        goblin = Goblin()
        goblin.gold = 200
        with mock.patch.object(gamemanager.gameManager, "splitSpoils", return_value=(15, 0)):
            body = self.killBesideYou(goblin, killer=None)
        self.assertEqual(body.gold, 15)

    def test_a_pile_already_there_is_gathered_into_the_body(self):
        game = self.game
        game.grid[self.besideYou] = [PILE, 1, items.ItemPile([potion()], gold=4)]
        game.enemyOccupiedItemSpaces[self.besideYou] = game.grid[self.besideYou]
        self.putEnemy(self.besideYou, Goblin())
        game.killEnemy(self.besideYou)
        body = game.bodyAt(self.besideYou)
        self.assertEqual(([item.name for item in body.items], body.gold), (["Healing Potion"], 4))

    def test_on_another_body_it_lies_on_the_nearest_floor(self):
        game = self.game
        first = self.killBesideYou()
        self.putEnemy(self.besideYou, DireRat())
        game.enemyOccupiedItemSpaces[self.besideYou] = [PILE, 1, first]  # (the rat stands on the goblin's body)
        game.killEnemy(self.besideYou)
        self.assertIs(game.bodyAt(self.besideYou), first)
        rats = [spot for spot in game.grid if game.bodyAt(spot) is not None and game.bodyAt(spot).unitName == "Dire Rat"]
        self.assertEqual(len(rats), 1)
        self.assertLessEqual(abs(rats[0] % game.rowLength - self.besideYou % game.rowLength), 1, "right beside it")

    def test_on_a_chest_it_lies_beside_it(self):
        game = self.game
        chestSpot = self.here - 1
        self.putEnemy(chestSpot, Goblin())
        game.enemyOccupiedItemSpaces[chestSpot] = [CHEST, 1, []]
        game.killEnemy(chestSpot)
        self.assertEqual(game.groundAt(chestSpot)[0], CHEST)
        self.assertEqual(sum(1 for spot in game.grid if game.bodyAt(spot) is not None), 1)

    def test_the_second_unit_on_a_space_leaves_its_body_too(self):
        game = self.game
        self.putEnemy(self.besideYou, DireRat())
        second = DireRat()
        occupancy.sharedTiles(game)[self.besideYou] = second
        game.killEnemy(self.besideYou, unit=second)
        body = game.bodyAt(self.besideYou)
        self.assertEqual(body.unitName, "Dire Rat")
        self.assertEqual(game.grid[self.besideYou][0], ENEMY, "the first one still stands on it")

    def test_bodies_lie_at_varied_angles_and_mirrored_or_not(self):
        random.seed(5)
        made = [bodies.Body("Goblin", 0) for _ in range(60)]
        self.assertEqual({body.quarterTurns for body in made}, {0, 1, 2, 3})
        self.assertEqual({body.mirrored for body in made}, {True, False})
        self.assertEqual({body.variant for body in made}, set(range(bodies.VARIANTS)))


class SearchingTests(BodyTest):
    def test_searching_rolls_it_onto_its_side_or_back(self):
        body = self.killBesideYou()
        body.items.append(potion())
        self.search()
        self.assertIn(body.pose, ("side", "up"))
        self.assertIn("items", self.game.openWindows)

    def test_it_only_rolls_once(self):
        body = self.killBesideYou()
        body.items.append(potion())
        self.search()
        pose = body.pose
        for _ in range(10):
            self.game.closeWindow("items")
            self.search()
        self.assertEqual(body.pose, pose)

    def test_some_roll_onto_their_side_and_some_onto_their_back(self):
        random.seed(2)
        poses = set()
        for _ in range(30):
            body = bodies.Body("Goblin", 0)
            body.rollOver(0)
            poses.add(body.pose)
        self.assertEqual(poses, {"side", "up"})

    def test_an_empty_body_still_rolls_when_searched(self):
        body = self.killBesideYou()
        self.search()
        self.assertNotEqual(body.pose, "down")

    def test_taking_everything_leaves_the_body(self):
        game = self.game
        body = self.killBesideYou()
        body.items.append(potion())
        self.search()
        inventoryBefore = len(game.player.inventory)
        game.onPickUpItem()
        self.assertEqual(len(game.player.inventory), inventoryBefore + 1)
        self.assertIs(game.bodyAt(self.besideYou), body)
        self.assertEqual(body.items, [])

    def test_a_body_with_only_gold_pays_it_and_stays(self):
        game = self.game
        body = self.killBesideYou()
        body.gold = 9
        goldBefore = game.player.gold
        self.search()
        self.assertEqual(game.player.gold, goldBefore + 9)
        self.assertIs(game.bodyAt(self.besideYou), body)

    def test_goblins_emptying_a_body_leave_it(self):
        game = self.game
        body = self.killBesideYou()
        body.items.append(potion())
        scavenger = Goblin()
        scavenger.loot = []
        with mock.patch.object(expansion, "take", return_value=([], 0)):
            expansion.takeFrom(game, scavenger, self.besideYou)
        self.assertIs(game.bodyAt(self.besideYou), body)

    def test_standing_on_it_says_whose_body_it_is(self):
        game = self.game
        game.worldTurn = 0
        self.killBesideYou(GoblinChief())
        keyDown(game, pygame.K_d)  # step onto it
        self.assertTrue(bodies.isBody(game.currentLocation[2]))
        for turn, label in ((0, "Goblin Chieftain body"), (bodies.FRESH_TURNS, "Goblin Chieftain rotting body"),
                            (bodies.SKELETAL_TURNS, "Goblin Chieftain bones")):
            game.worldTurn = turn
            game.updateDoors()
            self.assertEqual(game.currentPosition, label)


class RollAnimationTests(unittest.TestCase):
    def test_the_roll_passes_through_each_pose(self):
        body = bodies.Body("Goblin", 0)
        with mock.patch.object(bodies.rand, "choice", return_value="up"):
            body.rollOver(1000)
        frame = bodies.ROLL_FRAME_MS
        poses = [body.poseAt(1000 + step * frame + 10)[0] for step in range(4)]
        self.assertEqual(poses, ["down", "side", "up", "up"])
        self.assertTrue(body.poseAt(1000 + frame - 10)[1], "lifted just before it turns")
        self.assertFalse(body.poseAt(1000 + 3 * frame)[1], "down again at the end")
        self.assertTrue(body.rolling(1000 + 10))
        self.assertFalse(body.rolling(1000 + 10 * frame))

    def test_a_roll_onto_its_side_stops_there(self):
        body = bodies.Body("Goblin", 0)
        with mock.patch.object(bodies.rand, "choice", return_value="side"):
            body.rollOver(0)
        self.assertEqual([body.poseAt(step * bodies.ROLL_FRAME_MS + 10)[0] for step in range(3)], ["down", "side", "side"])

    def test_after_loading_a_save_it_just_lies_in_its_pose(self):
        body = bodies.Body("Goblin", 0)
        body.rollOver(50_000)
        self.assertEqual(body.poseAt(10), (body.pose, False), "(the clock starts over when the game loads)")

    def test_a_saved_body_never_plays_its_roll_again(self):
        import pickle
        body = bodies.Body("Goblin", 0)
        body.rollOver(50_000)
        loaded = pickle.loads(pickle.dumps(body))
        self.assertEqual(loaded.pose, body.pose)
        self.assertIsNone(loaded.rolledAtMs)
        for later in (50_000, 50_000 + bodies.ROLL_FRAME_MS):  # (when the new session's clock comes round to that time)
            self.assertEqual(loaded.poseAt(later), (body.pose, False))
            self.assertFalse(loaded.rolling(later))
        self.assertFalse(loaded.rollOver(60_000), "and searching it again doesn't roll it")

    def test_the_screen_animates_while_a_searched_body_rolls(self):
        test = BodyTest("run")
        test.setUp()
        body = test.killBesideYou()
        with mock.patch("pygame.time.get_ticks", return_value=5000):
            test.search()
            self.assertTrue(test.game.animating())
        with mock.patch("pygame.time.get_ticks", return_value=5000 + 10 * bodies.ROLL_FRAME_MS):
            self.assertFalse(test.game.rollingBody())
        self.assertNotEqual(body.pose, "down")


class DecayTests(BodyTest):
    def test_the_world_clock_counts_every_turn(self):
        game = self.game
        before = game.worldTurn
        for _ in range(3):
            game.enemyTurn()
        self.assertEqual(game.worldTurn, before + 3)

    def test_it_is_gone_after_1000_turns(self):
        game = self.game
        game.worldTurn = 0
        self.killBesideYou()
        game.worldTurn = bodies.DECAY_TURNS - 2
        game.enemyTurn()
        self.assertIsNotNone(game.bodyAt(self.besideYou), "turn 999: still there")
        game.enemyTurn()
        self.assertIsNone(game.bodyAt(self.besideYou))
        self.assertEqual(game.grid[self.besideYou][0], PILE, "an item pile is left")
        self.assertEqual(remainsOf(game.grid[self.besideYou][2]), [("bone", 1)])

    def test_what_was_still_on_it_is_left_in_the_pile_with_its_bones(self):
        game = self.game
        game.worldTurn = 0
        body = self.killBesideYou()
        body.items.append(potion())
        body.gold = 6
        game.worldTurn = bodies.DECAY_TURNS
        game.stepBodies()
        pile = game.grid[self.besideYou][2]
        self.assertFalse(bodies.isBody(pile))
        self.assertEqual(([item.name for item in pile.items if not isinstance(item, resources.MaterialStack)], pile.gold),
                         (["Healing Potion"], 6))
        self.assertEqual(remainsOf(pile), [("bone", 1)])

    def test_a_body_under_you_or_an_enemy_decays_too(self):
        game = self.game
        game.worldTurn = 0
        game.currentLocation = [PILE, 1, bodies.Body("Goblin", 0)]
        game.grid[self.here] = [1, 1, game.currentLocation[2]]
        enemySpot = self.here - 1
        game.enemyOccupiedItemSpaces[enemySpot] = [PILE, 1, bodies.Body("Goblin", 0)]
        self.putEnemy(enemySpot, Goblin())
        game.worldTurn = bodies.DECAY_TURNS
        game.stepBodies()
        for ground in (game.currentLocation, game.enemyOccupiedItemSpaces[enemySpot]):
            self.assertEqual(ground[0], PILE)
            self.assertFalse(bodies.isBody(ground[2]))
            self.assertEqual(remainsOf(ground[2]), [("bone", 1)])

    def test_the_clock_is_saved(self):
        game = self.game
        game.worldTurn = 432
        saveFile = os.path.join(tempfile.mkdtemp(), "bodies-save.pkl")
        gamemanager.gameManager.saveGame(game, saveFile)
        loaded = newGame()
        self.assertTrue(loaded.loadGame(saveFile))
        self.assertEqual(loaded.worldTurn, 432)

    def test_it_draws_as_it_decays(self):
        game = self.game
        painter = game.painter
        game.worldTurn = 0
        body = self.killBesideYou()
        looks = []
        for age in (0, 300, 550, 800, 950):
            game.worldTurn = age
            game.draw()
            looks.append(painter.bodyLook(body))
            self.assertIn(painter.bodyPicture(body), painter.bodyPictures.values())
        self.assertEqual(len({look[3] for look in looks}), 5, "a different picture at each stage")


class UnderAPlantTests(BodyTest):
    """Overgrowth: a plant that kills a unit grows over its body (gameManager.buryUnderPlant). The body lies under it,
    drawn beneath the plant, until the plant is gone (uncoverBodies)."""

    def growOverBody(self):
        game = self.game
        body = self.killBesideYou()
        body.items.append(potion())
        plantTile = [8, 1, plants.Plant.grown("hearthmoss")]
        game.buryUnderPlant(self.besideYou, plantTile)
        game.grid[self.besideYou] = plantTile
        return body, plantTile[2]

    def test_the_body_lies_under_the_plant(self):
        body, plant = self.growOverBody()
        self.assertIs(plant.bodyUnder, body)
        self.assertIsNone(self.game.bodyAt(self.besideYou))
        self.game.uncoverBodies()
        self.assertEqual(self.game.grid[self.besideYou][0], 8, "the plant stays while it's there")

    def test_when_the_plant_is_gone_the_body_is_there_again(self):
        game = self.game
        body, _ = self.growOverBody()
        game.grid[self.besideYou] = [FLOOR, 1]  # (picked, burnt or pulled up)
        game.uncoverBodies()
        self.assertIs(game.bodyAt(self.besideYou), body)
        self.assertEqual([item.name for item in body.items], ["Healing Potion"])

    def test_it_shows_at_once_after_picking_the_plant(self):
        game = self.game
        body, _ = self.growOverBody()
        game.grid[self.besideYou] = [FLOOR, 1]
        game.change = True
        game.uncoverBodies()
        game.draw()
        self.assertIs(game.bodyAt(self.besideYou), body)

    def test_it_is_found_again_after_loading(self):
        game = self.game
        body, _ = self.growOverBody()
        saveFile = os.path.join(tempfile.mkdtemp(), "plant-body.pkl")
        gamemanager.gameManager.saveGame(game, saveFile)
        loaded = newGame()
        self.assertTrue(loaded.loadGame(saveFile))
        self.assertEqual(list(loaded.coveredBodiesHere()), [self.besideYou])
        loaded.grid[self.besideYou] = [FLOOR, 1]
        loaded.uncoverBodies()
        self.assertEqual(loaded.bodyAt(self.besideYou).unitName, "Goblin")

    def test_it_is_drawn_beneath_the_plant(self):
        game = self.game
        body, plant = self.growOverBody()
        painter = game.painter
        with mock.patch.object(painter, "blitPile", wraps=painter.blitPile) as blitPile:
            game.draw()
        self.assertIn(body, [call.args[0] for call in blitPile.call_args_list])
        before = painter.tileSignature(game.grid, self.besideYou, game.rooms, 0, self.here, 5, (0, 0, 1))[0]
        game.worldTurn += bodies.SKELETAL_TURNS
        game.draw()
        after = painter.tileSignature(game.grid, self.besideYou, game.rooms, 0, self.here, 5, (0, 0, 1))[0]
        self.assertNotEqual(before, after, "it's redrawn as the body under it decays")

    def test_under_a_unit_still_standing_there_too(self):
        game = self.game
        body = self.killBesideYou()
        self.putEnemy(self.besideYou, Goblin())
        game.enemyOccupiedItemSpaces[self.besideYou] = [PILE, 1, body]
        plantTile = [8, 1, plants.Plant.grown("hearthmoss")]
        game.buryUnderPlant(self.besideYou, plantTile)
        self.assertIs(plantTile[2].bodyUnder, body)

    def test_a_body_under_a_plant_still_decays(self):
        game = self.game
        game.worldTurn = 0
        body, plant = self.growOverBody()
        game.worldTurn = bodies.DECAY_TURNS
        game.stepBodies()
        self.assertIsNone(plant.bodyUnder)
        self.assertEqual(game.grid[self.besideYou][0], 8, "the plant stays")
        grounds = [game.groundAt(spot) for spot in game.grid]
        spilled = [item.name for ground in grounds if ground[0] == PILE for item in ground[2].items]
        self.assertIn("Healing Potion", spilled, "what was on it spills beside the plant")
        self.assertIn(("bone", 1), [stack for ground in grounds if ground[0] == PILE for stack in remainsOf(ground[2])], "with its bones")


class InsideAWallTests(BodyTest):
    """A burrower that dies inside a wall with nothing on it leaves its body inside the wall (gameManager.entomb).
    Once the wall is broken, any way, the body falls to the floor there (uncoverBodies)."""

    def killMoleInWall(self, drops=()):
        game = self.game
        self.wall = wall.StoneWall()
        self.putEnemy(self.besideYou, DireMole())
        game.enemyOccupiedItemSpaces[self.besideYou] = [WALL, 1, self.wall]
        with mock.patch("cruel.inventory.loot.roll", return_value=list(drops)):
            game.killEnemy(self.besideYou, killer="player")
        return bodies.bodyInside(self.wall)

    def bodiesOnTheFloor(self):
        return [spot for spot in self.game.grid if self.game.bodyAt(spot) is not None]

    def test_its_body_stays_inside_the_wall(self):
        body = self.killMoleInWall()
        self.assertEqual(self.game.grid[self.besideYou][:3], [WALL, 1, self.wall], "the wall still stands")
        self.assertIsInstance(body, bodies.Body)
        self.assertEqual(body.unitName, "Dire Mole")
        self.game.uncoverBodies()
        self.assertEqual(self.bodiesOnTheFloor(), [], "it isn't pushed out onto the floor")

    def test_when_the_wall_breaks_the_body_falls_to_that_floor(self):
        game = self.game
        body = self.killMoleInWall()
        game.breakWall(self.besideYou)
        game.uncoverBodies()
        self.assertIs(game.bodyAt(self.besideYou), body)

    def test_any_way_the_wall_goes(self):
        game = self.game
        body = self.killMoleInWall()
        game.grid[self.besideYou] = [FLOOR, 1]  # (blasted, dug through by an enemy...)
        game.uncoverBodies()
        self.assertIs(game.bodyAt(self.besideYou), body)

    def test_with_loot_on_it_the_wall_crumbles_and_the_body_lies_there(self):
        game = self.game
        self.killMoleInWall(drops=[("relic:lantern", 1)])
        self.assertIsNone(bodies.bodyInside(self.wall))
        body = game.bodyAt(self.besideYou)
        self.assertIsNotNone(body)
        self.assertEqual(body.unitName, "Dire Mole")

    def test_a_burrower_passing_through_keeps_it_inside(self):
        game = self.game
        body = self.killMoleInWall()
        tunnel = game.grid[self.besideYou]
        self.putEnemy(self.besideYou, DireMole())
        game.enemyOccupiedItemSpaces[self.besideYou] = tunnel
        game.uncoverBodies()
        self.assertIs(bodies.bodyInside(self.wall), body)
        self.assertEqual(self.bodiesOnTheFloor(), [])

    def test_it_is_found_again_after_loading(self):
        game = self.game
        self.killMoleInWall()
        saveFile = os.path.join(tempfile.mkdtemp(), "wall-body.pkl")
        gamemanager.gameManager.saveGame(game, saveFile)
        loaded = newGame()
        self.assertTrue(loaded.loadGame(saveFile))
        self.assertEqual(list(loaded.coveredBodiesHere()), [self.besideYou])
        loaded.grid[self.besideYou] = [FLOOR, 1]
        loaded.uncoverBodies()
        self.assertEqual(loaded.bodyAt(self.besideYou).unitName, "Dire Mole")

    def test_it_decays_inside_and_falls_out_as_bones(self):
        game = self.game
        game.worldTurn = 0
        body = self.killMoleInWall()
        game.worldTurn = bodies.DECAY_TURNS
        game.stepBodies()
        self.assertIs(bodies.bodyInside(self.wall), body, "the bones stay inside until the wall breaks")
        game.grid[self.besideYou] = [FLOOR, 1]
        game.uncoverBodies()
        ground = game.groundAt(self.besideYou)
        self.assertEqual(ground[0], PILE)
        self.assertFalse(bodies.isBody(ground[2]))
        self.assertEqual(remainsOf(ground[2]), [("bone", 1)])


if __name__ == "__main__":
    unittest.main()
