"""Goblin Archers (enemies.GoblinArcher, ranged.py): who an arrow hits, what it does when it lands, a wild archer's
turn (shoot, step back or fight) and archers in expansion factions.

Integration tests: a real game, the player in a cleared row of floor with an archer five tiles to the left."""
import unittest
from unittest import mock

from cruel.entities import enemies
from cruel.world import expansion, organizers, ranged
from tests.helpers.gamemanager import ENEMY, FLOOR, RIGHT, WALL, clearAround, newGame, standInOpenFloor


class ArcherTest(unittest.TestCase):
    """You stand in open floor facing right; an archer stands five tiles to your left, on your row."""

    def setUp(self):
        game = self.game = newGame()
        self.here = standInOpenFloor(game, facing=RIGHT)
        self.rowLength = game.rowLength
        for step in range(-6, 3):  # a clear, visible strip three rows tall from the archer to past you
            clearAround(game, self.here + step)
        self.archerSpot = self.here - 5
        self.archer = self.putUnit(self.archerSpot, enemies.GoblinArcher())

    def putUnit(self, spot, unit):
        self.game.grid[spot] = [ENEMY, 1, unit]
        self.game.EnemyPositions.add(spot)
        return unit

    def putWall(self, spot):
        self.game.grid[spot] = [WALL, 1, self.game.createWall(spot, self.game.rooms)]

    def lineSpot(self, stepsFromArcher):
        return self.archerSpot + stepsFromArcher


class ShotRuleTests(ArcherTest):
    """rollShot: a stray share first, then each unit on the line, nearest first, then the target."""

    def roll(self, value, target=None):
        return ranged.rollShot(self.game, self.archerSpot, target or self.here, self.archer, roll=value)

    def test_with_a_clear_line_most_arrows_hit_the_target(self):
        self.assertEqual(self.roll(20), ("target", self.here))
        self.assertEqual(self.roll(99.9), ("target", self.here))

    def test_the_first_fifth_stray_onto_a_neighbor_of_the_target(self):
        kind, landing = self.roll(19.9)
        self.assertEqual(kind, "stray")
        self.assertIn(landing, self.game.eightAround(self.here))

    def test_a_stray_can_land_on_any_of_the_eight_neighbors(self):
        with mock.patch("random.choice", side_effect=lambda choices: choices[-1]) as choice:
            self.roll(0)
        self.assertEqual(sorted(choice.call_args[0][0]), sorted(self.game.eightAround(self.here)))
        self.assertEqual(len(choice.call_args[0][0]), 8)

    def test_a_goblin_on_the_line_takes_a_fifth_from_the_target(self):
        self.putUnit(self.lineSpot(2), enemies.Goblin())
        self.assertEqual(self.roll(20), ("line", self.lineSpot(2)))
        self.assertEqual(self.roll(39.9), ("line", self.lineSpot(2)))
        self.assertEqual(self.roll(40), ("target", self.here))

    def test_units_on_the_line_are_hit_nearest_first(self):
        self.putUnit(self.lineSpot(3), enemies.Goblin())
        self.putUnit(self.lineSpot(1), enemies.Goblin())
        self.assertEqual(self.roll(25), ("line", self.lineSpot(1)))
        self.assertEqual(self.roll(45), ("line", self.lineSpot(3)))
        self.assertEqual(self.roll(60), ("target", self.here))

    def test_a_hostile_unit_on_the_line_counts_the_same_as_a_friend(self):
        faction = expansion.newFaction(self.game, "warpaint")
        stranger = self.putUnit(self.lineSpot(2), enemies.Goblin())
        expansion.setFaction(stranger, faction)
        self.assertTrue(expansion.hostile(self.archer, stranger))
        self.assertEqual(self.roll(30), ("line", self.lineSpot(2)))

    def test_you_on_the_line_can_be_hit_when_it_shoots_past_you(self):
        goblinSpot = self.here + 2
        self.putUnit(goblinSpot, enemies.Goblin())
        self.archer.range = 8
        self.assertEqual(self.roll(30, target=goblinSpot), ("line", self.here))


class CanShootTests(ArcherTest):
    def test_it_shoots_you_from_five_tiles(self):
        self.assertTrue(ranged.canShoot(self.game, self.archerSpot, self.here, self.archer))

    def test_not_from_six(self):
        self.assertFalse(ranged.canShoot(self.game, self.archerSpot - 1, self.here, self.archer))

    def test_never_through_a_wall(self):
        self.putWall(self.lineSpot(2))
        self.assertFalse(ranged.canShoot(self.game, self.archerSpot, self.here, self.archer))

    def test_through_three_units_but_not_four(self):
        for step in (1, 2, 3):
            self.putUnit(self.lineSpot(step), enemies.Goblin())
        self.assertTrue(ranged.canShoot(self.game, self.archerSpot, self.here, self.archer))
        self.putUnit(self.lineSpot(4), enemies.Goblin())
        self.assertFalse(ranged.canShoot(self.game, self.archerSpot, self.here, self.archer))


class ArrowHitTests(ArcherTest):
    """shoot: what an arrow does where it lands."""

    def shootLanding(self, kind, landing):
        with mock.patch.object(ranged, "rollShot", return_value=(kind, landing)), \
                mock.patch.object(self.game, "dodge", return_value=None):
            return ranged.shoot(self.game, self.archerSpot, self.archer, self.here)

    def test_an_arrow_that_hits_you_does_arrow_damage(self):
        player = self.game.player
        expected = player.hitDamage(self.archer.arrowDamage)
        before = player.damageTaken
        self.assertEqual(self.shootLanding("target", self.here), "player")
        self.assertEqual(player.damageTaken - before, expected)

    def test_the_arrow_flies_to_where_it_lands(self):
        self.shootLanding("target", self.here)
        [arrow] = self.game.arrows
        self.assertEqual((arrow["from"], arrow["to"], arrow["hit"]), (self.archerSpot, self.here, True))

    def test_a_goblin_on_its_side_that_it_hits_is_hurt_and_does_not_turn_on_it(self):
        goblin = self.putUnit(self.lineSpot(2), enemies.Goblin())
        goblin.hp = 10
        self.assertIs(self.shootLanding("line", self.lineSpot(2)), goblin)
        self.assertEqual(goblin.hp, 10 - self.archer.arrowDamage)
        self.assertIsNone(goblin.foe)

    def test_a_unit_it_is_hostile_to_fights_back(self):
        faction = expansion.newFaction(self.game, "warpaint")
        expansion.setFaction(self.archer, faction)
        wildGoblin = self.putUnit(self.lineSpot(2), enemies.Goblin())
        wildGoblin.hp = 10
        self.shootLanding("line", self.lineSpot(2))
        self.assertIs(wildGoblin.foe, self.archer)

    def test_a_stray_onto_a_unit_hits_it(self):
        neighbor = self.here + self.rowLength
        goblin = self.putUnit(neighbor, enemies.Goblin())
        goblin.hp = 10
        self.assertIs(self.shootLanding("stray", neighbor), goblin)
        self.assertEqual(goblin.hp, 10 - self.archer.arrowDamage)

    def test_a_stray_onto_empty_floor_is_wasted(self):
        player = self.game.player
        before = player.damageTaken
        self.assertIsNone(self.shootLanding("stray", self.here - self.rowLength))
        self.assertEqual(player.damageTaken, before)
        self.assertFalse(self.game.arrows[0]["hit"])

    def test_a_stray_hits_a_neighbor_even_behind_a_wall(self):
        neighbor = self.here + self.rowLength + 1
        for step in range(-4, 1):  # a wall all along the row below, between the archer and that neighbor
            self.putWall(self.here + self.rowLength + step)
        self.assertIsNone(ranged.shotLine(self.game, self.archerSpot, neighbor))
        goblin = self.putUnit(neighbor, enemies.Goblin())
        goblin.hp = 10
        self.assertIs(self.shootLanding("stray", neighbor), goblin)

    def test_a_faction_archers_arrow_is_fletched_in_its_cloth(self):
        expansion.setFaction(self.archer, expansion.newFaction(self.game, "tidewater"))
        self.shootLanding("target", self.here)
        self.assertEqual(self.game.arrows[0]["look"], "tidewater")


class HitPlayerTests(ArcherTest):
    def test_goblin_fear_does_not_stop_an_arrow(self):
        player = self.game.player
        before = player.damageTaken
        with mock.patch.object(player, "hasEffect", side_effect=lambda effect: effect == "goblin_fear"), \
                mock.patch.object(self.game, "dodge", return_value=None), mock.patch("random.random", return_value=0.0):
            self.game.hitPlayer(self.archer, self.archerSpot, damage=2, arrow=True)
        self.assertGreater(player.damageTaken, before)

    def test_goblin_fear_works_on_an_archer_up_close(self):
        player = self.game.player
        before = player.damageTaken
        with mock.patch.object(player, "hasEffect", side_effect=lambda effect: effect == "goblin_fear"), \
                mock.patch("random.random", return_value=0.0):
            self.game.hitPlayer(self.archer, self.here - 1)
        self.assertEqual(player.damageTaken, before)

    def test_demise_thorns_do_not_bite_back_at_an_arrow(self):
        with mock.patch.object(self.game.player, "hasEffect", side_effect=lambda effect: effect == "fed_thorns"), \
                mock.patch.object(self.game, "dodge", return_value=None), \
                mock.patch.object(self.game, "magicEnemy") as thorns:
            self.game.hitPlayer(self.archer, self.archerSpot, damage=2, arrow=True)
        thorns.assert_not_called()


class WildTurnTests(ArcherTest):
    """ranged.wildTurn: a wild archer that sees you."""

    def test_it_shoots_you_from_range_and_stays_put(self):
        with mock.patch.object(ranged, "shoot") as shoot:
            self.assertEqual(ranged.wildTurn(self.game, self.archerSpot, self.archer), self.archerSpot)
        shoot.assert_called_once_with(self.game, self.archerSpot, self.archer, self.here)

    def test_behind_a_wall_it_does_not_shoot(self):
        self.putWall(self.lineSpot(2))
        with mock.patch.object(ranged, "shoot") as shoot:
            ranged.wildTurn(self.game, self.archerSpot, self.archer)
        shoot.assert_not_called()

    def test_too_close_it_steps_back(self):
        nearSpot = self.here - 2
        self.game.grid[self.archerSpot] = [FLOOR, 1]
        self.putUnit(nearSpot, self.archer)
        moveTo = ranged.wildTurn(self.game, nearSpot, self.archer)
        self.assertIn(moveTo, self.game.neighbors(nearSpot))
        self.assertGreater(ranged.distance(self.game, moveTo, self.here), 2)
        self.assertTrue(ranged.canShoot(self.game, moveTo, self.here, self.archer), "it picks a spot it can shoot from")

    def test_cornered_beside_you_it_fights_hand_to_hand(self):
        besideSpot = self.here - 1
        self.game.grid[self.archerSpot] = [FLOOR, 1]
        self.putUnit(besideSpot, self.archer)
        for wallSpot in (besideSpot - 1, besideSpot - self.rowLength, besideSpot + self.rowLength):
            self.putWall(wallSpot)
        self.assertIsNone(ranged.wildTurn(self.game, besideSpot, self.archer))

    def test_in_peaceful_mode_it_leaves_you_alone(self):
        self.game.peaceful = True
        self.assertIsNone(ranged.wildTurn(self.game, self.archerSpot, self.archer))

    def test_its_turn_on_the_floor_shoots_you(self):
        player = self.game.player
        before = player.damageTaken
        with mock.patch.object(ranged, "rollShot", return_value=("target", self.here)), \
                mock.patch.object(self.game, "dodge", return_value=None):
            position = self.game.unitTurn(self.archerSpot, self.archer, organizers.gather(self.game), expansion.beginTurn(self.game))
        self.assertEqual(position, self.archerSpot)
        self.assertGreater(player.damageTaken, before)


class FactionArcherTests(ArcherTest):
    def setUp(self):
        super().setUp()
        self.faction = expansion.newFaction(self.game, "ochre", neutral=True)
        expansion.setFaction(self.archer, self.faction)

    def test_it_shoots_a_wild_goblin_in_range_instead_of_moving(self):
        wildGoblin = self.putUnit(self.lineSpot(4), enemies.Goblin())
        context = expansion.beginTurn(self.game)
        self.assertEqual(ranged.factionTarget(self.game, self.archerSpot, self.archer, context), self.lineSpot(4))
        with mock.patch.object(ranged, "shoot") as shoot:
            self.assertEqual(expansion.takeTurn(self.game, self.archerSpot, self.archer, context), self.archerSpot)
        shoot.assert_called_once_with(self.game, self.archerSpot, self.archer, self.lineSpot(4))
        self.assertIsNotNone(wildGoblin)

    def test_it_leaves_its_own_side_alone(self):
        friend = self.putUnit(self.lineSpot(3), enemies.Goblin())
        expansion.setFaction(friend, self.faction)
        self.assertIsNone(ranged.factionTarget(self.game, self.archerSpot, self.archer, expansion.beginTurn(self.game)))


class WildFoeTests(ArcherTest):
    def test_a_wild_archer_fighting_back_shoots_its_foe_from_range(self):
        foe = self.putUnit(self.lineSpot(4), enemies.Goblin())
        expansion.setFaction(foe, expansion.newFaction(self.game, "ember"))
        self.archer.foe = foe
        with mock.patch.object(ranged, "shoot") as shoot:
            position = expansion.otherTurn(self.game, self.archerSpot, self.archer, expansion.beginTurn(self.game))
        self.assertEqual(position, self.archerSpot)
        shoot.assert_called_once_with(self.game, self.archerSpot, self.archer, self.lineSpot(4))


class SpawnerTests(ArcherTest):
    def test_a_spawner_can_make_an_archer_who_joins_a_squad(self):
        faction = expansion.newFaction(self.game, "warpaint")
        spot = self.here + self.rowLength * 2
        self.game.grid[spot] = [FLOOR, 1]
        archer = expansion.spawn(self.game, spot, "Goblin Archer", faction)
        self.assertIsInstance(archer, enemies.GoblinArcher)
        self.assertEqual(archer.faction, faction.id)
        self.assertTrue(any(archer in squad.members for squad in faction.squads))


if __name__ == "__main__":
    unittest.main()
