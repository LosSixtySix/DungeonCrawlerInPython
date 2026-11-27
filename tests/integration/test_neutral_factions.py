"""Neutral goblin factions in the Expansion event (expansion.py, "Neutral factions"): some factions leave you alone,
camp far from the others, never raid, only defend their camp, and turn on you for a while if you provoke them."""
import random
import unittest
from unittest import mock

from cruel.entities import enemies
from cruel.inventory import resources
from cruel.world import expansion
from cruel.world import wall
from tests import support
from tests.helpers.expansion import blankFloor, middleOf

FLOOR, PLAYER, WALL, CHEST, ENEMY = 0, 1, 2, 3, 5
FACING_LEFT = 0


def addBonfire(game, faction, spot):
    expansion.place(game, spot, expansion.Structure("bonfire", faction.id))
    faction.bonfires.append(spot)
    if faction.first is None:
        faction.first = spot


def addGoblin(game, faction, spot, kind=enemies.Goblin, squad=None):
    """A goblin of faction standing on spot, in squad if one is given."""
    goblin = kind()
    goblin.hp = goblin.maxHp = 500  # tough enough to survive any test's hits
    expansion.setFaction(goblin, faction)
    game.grid[spot] = [ENEMY, 1, goblin]
    game.EnemyPositions.add(spot)
    if squad is not None:
        squad.members.append(goblin)
        goblin.squad = squad
    return goblin


def addSquad(game, faction, spot, marching=False):
    """A chief and a goblin of faction next to each other at spot, as one squad."""
    squad = expansion.Squad(marching=marching)
    faction.squads.append(squad)
    chief = addGoblin(game, faction, spot, enemies.GoblinChief, squad)
    addGoblin(game, faction, spot + 1, enemies.Goblin, squad)
    return squad, chief


def addCampChest(game, faction, spot, things=()):
    chest = expansion.CampChest(faction.id, faction.look, list(things))
    game.grid[spot] = [CHEST, 1, chest]
    expansion.chests(game, faction).add(spot)
    return chest


def standFacing(game, spot):
    """Puts the player just right of spot, facing it."""
    support.placePlayer(game, spot + 1)
    game.grid[spot + 1] = [PLAYER, 1]
    game.currentLocation = [FLOOR, 1]
    game.player.playerDirection = FACING_LEFT
    game.setLookPosition()


def popupTexts(game):
    return [popup[0] for popup in game.popups]


class NeutralFactionTest(unittest.TestCase):
    """A blank floor with one neutral faction camped in the middle."""

    def setUp(self):
        random.seed(5)
        expansion.PEACE.clear()
        self.game = support.newGame()
        blankFloor(self.game)
        self.campCenter = middleOf(self.game)
        self.neutralFaction = expansion.newFaction(self.game, "ochre", neutral=True)
        addBonfire(self.game, self.neutralFaction, self.campCenter)

    def tearDown(self):
        expansion.PEACE.clear()


class WhoIsNeutralTests(NeutralFactionTest):
    """Which factions come out neutral."""

    def test_about_a_third_of_new_factions_are_neutral(self):
        neutralCount = sum(expansion.newFaction(self.game, "ashen").neutral for _ in range(2000))
        self.assertAlmostEqual(neutralCount / 2000, expansion.NEUTRAL_CHANCE, delta=0.04)

    def test_the_starting_war_band_can_be_neutral_or_not(self):
        for chance, expectNeutral in ((1.0, True), (0.0, False)):
            game = support.newGame()
            blankFloor(game)
            with mock.patch.object(expansion, "NEUTRAL_CHANCE", chance):
                self.assertTrue(expansion.spawnWarband(game))
            warband = next(iter(expansion.camp(game)["factions"].values()))
            self.assertEqual(warband.neutral, expectNeutral)

    def test_a_schisms_new_half_can_be_neutral(self):
        parentFaction = expansion.newFaction(self.game, "warpaint", neutral=False)
        parentCamp = 5 * self.game.rowLength + 5
        addBonfire(self.game, parentFaction, parentCamp)
        for offset in (0, 3, 6):
            addSquad(self.game, parentFaction, parentCamp + 2 * self.game.rowLength + offset)
        for offset in (0, 2):
            addGoblin(self.game, parentFaction, parentCamp + 4 * self.game.rowLength + offset, enemies.GoblinBuilder)
            addGoblin(self.game, parentFaction, parentCamp + 5 * self.game.rowLength + offset, enemies.GoblinFarmer)
        units = expansion.factionUnits(self.game, parentFaction)
        with mock.patch.object(expansion, "NEUTRAL_CHANCE", 1.0):
            self.assertTrue(expansion.schism(self.game, parentFaction, units))
        newHalf = max(expansion.camp(self.game)["factions"].values(), key=lambda faction: faction.id)
        self.assertTrue(newHalf.neutral)
        self.assertIsNotNone(newHalf.migrating, "it marches off to a camp of its own")

    def test_a_faction_from_a_save_before_neutral_factions_is_hostile(self):
        oldFaction = expansion.newFaction(self.game, "ashen", neutral=False)
        del oldFaction.neutral, oldFaction.grudge
        goblin = addGoblin(self.game, oldFaction, self.campCenter + 30)
        self.assertFalse(expansion.isNeutral(oldFaction))
        self.assertTrue(expansion.huntsPlayer(self.game, goblin))

    def test_goblins_that_fall_to_the_floor_below_stay_neutral(self):
        goblin = addGoblin(self.game, self.neutralFaction, self.campCenter + 3)
        expansion.dropOut(self.game, goblin)
        self.game.camps = {0: expansion.camp(self.game)}  # what was floor 0's camp state...
        self.game.level = 1                          # ...seen from the floor below
        expansion.land(self.game, goblin, self.campCenter + 3)
        landedFaction = expansion.faction(self.game, goblin)
        self.assertIsNot(landedFaction, self.neutralFaction)
        self.assertTrue(landedFaction.neutral)


class CampPlacementTests(NeutralFactionTest):
    """A neutral faction camps as far from the others as it can."""

    def test_a_neutral_war_band_arrives_as_far_as_it_can_from_other_camps(self):
        hostileFaction = expansion.newFaction(self.game, "warpaint", neutral=False)
        hostileCamp = 10 * self.game.rowLength + 10
        addBonfire(self.game, hostileFaction, hostileCamp)
        self.game.camps[self.game.level]["factions"].pop(self.neutralFaction.id)  # only the hostile camp is on this floor
        self.game.grid[self.campCenter] = [FLOOR, 0]
        otherCamps = expansion.campsAround(self.game)
        farthestPossible = max(expansion.distanceFromCamps(self.game, spot, otherCamps)
                               for spot in expansion.outOfSightSpots(self.game, 10))

        with mock.patch.object(expansion, "NEUTRAL_CHANCE", 1.0):
            self.assertTrue(expansion.spawnWarband(self.game))
        warband = max(expansion.camp(self.game)["factions"].values(), key=lambda faction: faction.id)
        closestGoblin = min(expansion.dist(self.game, spot, hostileCamp) for spot, _ in expansion.factionUnits(self.game, warband))
        self.assertGreater(closestGoblin, farthestPossible - 5, "the war band lands at the far side of the floor")

    def test_a_neutral_half_picks_the_farthest_spot_it_weighs(self):
        allCamps = expansion.campsAround(self.game)
        with mock.patch.object(expansion, "FAR_SPOTS_WEIGHED", 10 ** 6):  # weigh every spot on the floor
            farthestSpot = expansion.farAway(self.game, self.campCenter, farthest=True)
        validSpots = [spot for spot, tile in self.game.grid.items() if tile[0] == FLOOR
                      and expansion.distanceFromCamps(self.game, spot, allCamps) >= expansion.SCHISM_DISTANCE
                      and expansion.dist(self.game, spot, self.game.playerPositionFlat) >= expansion.SCHISM_CLEAR]
        bestDistance = max(expansion.distanceFromCamps(self.game, spot, allCamps) for spot in validSpots)
        self.assertEqual(expansion.distanceFromCamps(self.game, farthestSpot, allCamps), bestDistance)

    def test_with_no_camps_anywhere_is_infinitely_far(self):
        self.assertEqual(expansion.distanceFromCamps(self.game, self.campCenter, []), float("inf"))


class DefensiveTests(NeutralFactionTest):
    """Neutral squads leave you alone, stay home and only fight near their camp."""

    def squadTargetOf(self, squad, leader, leaderSpot):
        return expansion.squadTarget(self.game, squad, expansion.beginTurn(self.game), leader, leaderSpot)

    def test_a_neutral_goblin_beside_you_does_not_attack(self):
        goblinSpot = self.campCenter + 2
        goblin = addGoblin(self.game, self.neutralFaction, goblinSpot)
        support.placePlayer(self.game, goblinSpot + 1)
        self.assertIsNone(expansion.adjacentFoe(self.game, goblinSpot, goblin))

    def test_a_hostile_goblin_beside_you_attacks(self):
        hostileFaction = expansion.newFaction(self.game, "warpaint", neutral=False)
        goblinSpot = self.campCenter + 2
        goblin = addGoblin(self.game, hostileFaction, goblinSpot)
        support.placePlayer(self.game, goblinSpot + 1)
        self.assertEqual(expansion.adjacentFoe(self.game, goblinSpot, goblin), ("player", goblinSpot + 1))

    def test_a_neutral_squad_ignores_you_in_plain_sight(self):
        squad, chief = addSquad(self.game, self.neutralFaction, self.campCenter + 2)
        support.placePlayer(self.game, self.campCenter + 5)
        self.assertIsNone(self.squadTargetOf(squad, chief, self.campCenter + 2))

    def test_a_neutral_squad_fights_another_faction_near_its_camp(self):
        squad, chief = addSquad(self.game, self.neutralFaction, self.campCenter + 2)
        raider = addGoblin(self.game, expansion.newFaction(self.game, "warpaint", neutral=False), self.campCenter + 5)
        self.assertEqual(self.squadTargetOf(squad, chief, self.campCenter + 2), (raider, self.campCenter + 5))

    def test_a_neutral_squad_leaves_alone_what_is_far_from_its_camp(self):
        farFromCamp = self.campCenter + 30
        squad, chief = addSquad(self.game, self.neutralFaction, farFromCamp)
        addGoblin(self.game, expansion.newFaction(self.game, "warpaint", neutral=False), farFromCamp + 3)
        self.assertGreater(expansion.dist(self.game, farFromCamp, self.campCenter), expansion.GUARD_REACH)
        self.assertIsNone(self.squadTargetOf(squad, chief, farFromCamp))

    def test_a_neutral_squad_never_raids(self):
        otherFaction = expansion.newFaction(self.game, "warpaint", neutral=False)
        addCampChest(self.game, otherFaction, self.campCenter + 20)
        squad, chief = addSquad(self.game, self.neutralFaction, self.campCenter + 2, marching=True)
        expansion.soldierTurn(self.game, self.campCenter + 2, chief, expansion.beginTurn(self.game))
        self.assertIsNone(squad.raid)

    def test_a_hostile_squad_raids_a_chest_in_reach(self):
        self.neutralFaction.neutral = False
        otherFaction = expansion.newFaction(self.game, "warpaint", neutral=False)
        chestSpot = self.campCenter + 20
        addCampChest(self.game, otherFaction, chestSpot)
        squad, chief = addSquad(self.game, self.neutralFaction, self.campCenter + 2, marching=True)
        expansion.soldierTurn(self.game, self.campCenter + 2, chief, expansion.beginTurn(self.game))
        self.assertEqual(squad.raid, chestSpot)

    def test_a_neutral_squad_never_goes_on_gathering_missions(self):
        squad, chief = addSquad(self.game, self.neutralFaction, self.campCenter + 2, marching=True)
        chiefSpot = self.campCenter + 2
        for _ in range(10):
            chiefSpot = expansion.soldierTurn(self.game, chiefSpot, chief, expansion.beginTurn(self.game))
        self.assertIsNone(getattr(squad, "mission", None))

    def test_a_hostile_squad_goes_on_gathering_missions(self):
        self.neutralFaction.neutral = False
        squad, chief = addSquad(self.game, self.neutralFaction, self.campCenter + 2, marching=True)
        expansion.soldierTurn(self.game, self.campCenter + 2, chief, expansion.beginTurn(self.game))
        self.assertIsNotNone(squad.mission)


class ProvokingTests(NeutralFactionTest):
    """What turns a neutral faction on you, and what doesn't."""

    def assertProvoked(self, provoked=True):
        expectedGrudge = expansion.GRUDGE_TURNS if provoked else 0
        self.assertEqual(self.neutralFaction.grudge, expectedGrudge)

    def test_hitting_one_of_its_goblins_turns_it_on_you(self):
        goblinSpot = self.campCenter + 3
        goblin = addGoblin(self.game, self.neutralFaction, goblinSpot)
        standFacing(self.game, goblinSpot)
        self.game.enemyDodge = lambda target, damage, position: damage  # the swing always lands
        self.game.player.DealDamage = lambda: 3  # (and always does some damage)
        self.game.onInteract()
        self.assertProvoked()
        self.assertIn("The goblins turn on you!", popupTexts(self.game))
        self.assertTrue(expansion.huntsPlayer(self.game, goblin))
        self.assertEqual(expansion.adjacentFoe(self.game, goblinSpot, goblin), ("player", goblinSpot + 1))

    def test_a_bomb_or_a_fire_potion_on_its_goblins_turns_it_on_you(self):
        goblinSpot = self.campCenter + 10
        addGoblin(self.game, self.neutralFaction, goblinSpot)
        for potion in ("Explosive", "Fire"):
            self.neutralFaction.grudge = 0
            with mock.patch("cruel.core.gamemanager.FLOOR_BREAK_CHANCE", 0):
                self.game.land({"landing": goblinSpot, "effect": potion, "power": 3})
            self.assertProvoked()

    def test_breaking_one_of_its_hut_walls_turns_it_on_you(self):
        hut = expansion.layOutHut(self.game, self.campCenter + 8 * self.game.rowLength, set())
        self.neutralFaction.huts.append(hut)
        hutWallSpot = hut["walls"][0]
        self.game.grid[hutWallSpot] = [WALL, 1, wall.StoneWall()]
        self.game.breakWall(hutWallSpot)
        self.assertProvoked()

    def test_breaking_a_plain_wall_does_not(self):
        plainWallSpot = self.campCenter + 4
        self.game.grid[plainWallSpot] = [WALL, 1, wall.StoneWall()]
        self.game.breakWall(plainWallSpot)
        self.assertProvoked(False)

    def test_breaking_its_spawner_turns_it_on_you_but_a_cracked_one_does_not(self):
        spawnerSpot = self.campCenter + 6
        spawner = expansion.Structure("spawner", self.neutralFaction.id)
        expansion.place(self.game, spawnerSpot, spawner)
        spawner.hp = self.game.player.getWallDamage() + 1
        expansion.hitStructure(self.game, spawnerSpot)
        self.assertProvoked(False)
        expansion.hitStructure(self.game, spawnerSpot)
        self.assertNotEqual(self.game.grid[spawnerSpot][0], expansion.CAMP, "the spawner is broken")
        self.assertProvoked()

    def test_putting_out_its_bonfire_does_not(self):
        for _ in range(expansion.BONFIRE_HITS):
            expansion.hitStructure(self.game, self.campCenter)
        self.assertNotEqual(self.game.grid[self.campCenter][0], expansion.CAMP)
        self.assertProvoked(False)

    def test_taking_from_its_chest_turns_it_on_you(self):
        chestSpot = self.campCenter + 4
        addCampChest(self.game, self.neutralFaction, chestSpot, [resources.MaterialStack("stone", 3)])
        standFacing(self.game, chestSpot)
        self.game.roomItems = self.game.getItemsFromGrid()
        self.game.windowSel["items"] = 0
        self.game.pickUpItem()
        self.assertEqual(self.game.player.materials.get("stone"), 3)
        self.assertProvoked()

    def test_taking_from_an_ordinary_chest_does_not(self):
        chestSpot = self.campCenter + 4
        self.game.grid[chestSpot] = [CHEST, 1, [resources.MaterialStack("stone", 3)]]
        standFacing(self.game, chestSpot)
        self.game.roomItems = self.game.getItemsFromGrid()
        self.game.windowSel["items"] = 0
        self.game.pickUpItem()
        self.assertProvoked(False)

    def test_hurting_a_hostile_factions_goblin_changes_nothing(self):
        hostileFaction = expansion.newFaction(self.game, "warpaint", neutral=False)
        goblin = addGoblin(self.game, hostileFaction, self.campCenter + 3)
        expansion.playerHurt(self.game, goblin, self.campCenter + 3)
        self.assertEqual(hostileFaction.grudge, 0)
        self.assertNotIn("The goblins turn on you!", popupTexts(self.game))


class GrudgeTests(NeutralFactionTest):
    """A provoked neutral faction calms down after a while."""

    def test_the_grudge_wears_off_after_grudge_turns(self):
        squad, chief = addSquad(self.game, self.neutralFaction, self.campCenter + 2)
        expansion.provoke(self.game, self.neutralFaction, self.campCenter)
        squad.target = "player"
        for _ in range(expansion.GRUDGE_TURNS - 1):
            expansion.calmDown(self.game)
        self.assertTrue(expansion.huntsPlayer(self.game, chief), "still angry one turn before the end")
        expansion.calmDown(self.game)
        self.assertFalse(expansion.huntsPlayer(self.game, chief))
        self.assertIsNone(squad.target, "the squad stops chasing you")
        self.assertIn("The goblins calm down", popupTexts(self.game))

    def test_provoking_it_again_starts_the_count_over(self):
        expansion.provoke(self.game, self.neutralFaction, self.campCenter)
        for _ in range(100):
            expansion.calmDown(self.game)
        expansion.provoke(self.game, self.neutralFaction, self.campCenter)
        self.assertEqual(self.neutralFaction.grudge, expansion.GRUDGE_TURNS)

    def test_the_camp_turn_wears_the_grudge_down(self):
        expansion.provoke(self.game, self.neutralFaction, self.campCenter)
        expansion.stepCamp(self.game)
        self.assertEqual(self.neutralFaction.grudge, expansion.GRUDGE_TURNS - 1)


class LookingAtGoblinsTests(NeutralFactionTest):
    """What the name of a goblin you look at says about its faction."""

    def test_a_neutral_goblin_says_neutral_then_hostile_when_provoked(self):
        goblinSpot = self.campCenter + 3
        addGoblin(self.game, self.neutralFaction, goblinSpot)
        standFacing(self.game, goblinSpot)
        self.assertEqual(self.game.lookingAt(), "Goblin (neutral)")
        expansion.provoke(self.game, self.neutralFaction, goblinSpot)
        self.assertEqual(self.game.lookingAt(), "Goblin (hostile)")

    def test_a_hostile_factions_goblin_has_no_label(self):
        goblinSpot = self.campCenter + 3
        addGoblin(self.game, expansion.newFaction(self.game, "warpaint", neutral=False), goblinSpot)
        standFacing(self.game, goblinSpot)
        self.assertEqual(self.game.lookingAt(), "Goblin")


if __name__ == "__main__":
    unittest.main()
