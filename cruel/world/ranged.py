"""
Ranged enemies: the Goblin Archer (enemies.GoblinArcher). Plan: https://claude.ai/artifact/1EPWa2TCeVpc232fogBAx5

  Shooting      it shoots a foe within its range when the straight line to it (gameManager.linePoints, the line
                potions fly on) crosses no wall, station or sight-blocking plant (gameManager.blocksThrow).
  Each arrow    one roll out of 100. Below strayChance it strays onto a random one of the target's 8 neighbors and
                hits whatever stands there (even behind a wall), or nothing. Then each unit on the line, friend or
                foe and nearest first, takes lineShare. Whatever is left hits the target. When nothing is left for
                the target (4 units on the line, with the Goblin Archer's numbers) it won't take the shot.
  The hit       arrowDamage, dodged and Warded like a melee hit. A unit on its own side that it hits doesn't turn
                on it; anyone else fights back. The arrow flies on screen (gameManager.startArrow).
  Keeping away  a wild archer that sees you within keepAway tiles steps to an open tile farther from you, one it
                can still shoot from if it can. With nowhere to go it shoots, or fights you hand to hand.
"""
import math
import random as rand

from cruel.world import expansion
from cruel.world import occupancy

PLAYER_TILE, UNIT_TILE, FLOOR_TILE = 1, 5, 0
ENEMY_SIGHT_KIND = 5  # what enemies see through when they look (gameManager.rayCircleVision's selfNum)


def isRanged(unit):
    return getattr(unit, "ranged", False)


def distance(gameManager, fromSpot, toSpot):
    rowLength = gameManager.rowLength
    return math.hypot(fromSpot % rowLength - toSpot % rowLength, fromSpot // rowLength - toSpot // rowLength)


def shotLine(gameManager, fromSpot, toSpot):
    """The spots an arrow passes between fromSpot and toSpot (neither end), in order, or None when a wall, a station
    or a plant you can't see through is in the way."""
    rowLength = gameManager.rowLength
    between = []
    for column, row in gameManager.linePoints(fromSpot, toSpot)[:-1]:
        spot = column + row * rowLength
        if not 0 <= column < rowLength or gameManager.blocksThrow(spot):
            return None
        between.append(spot)
    return between


def whoIsAt(gameManager, spot):
    """"player", the unit standing on spot, or None."""
    if spot == gameManager.playerPositionFlat:
        return "player"
    tile = gameManager.grid.get(spot)
    if tile and tile[0] == UNIT_TILE and len(tile) > 2:
        return tile[2]
    return None


def unitsOnLine(gameManager, between, shooter):
    """(spot, "player" or unit) for everyone standing on the line, nearest first: each space once, and a big unit
    covering several of them once."""
    found, seen = [], set()
    for spot in between:
        standing = whoIsAt(gameManager, spot)
        if standing is None or standing is shooter or id(standing) in seen:
            continue
        seen.add(id(standing))
        found.append((spot, standing))
    return found


def targetShare(shooter, unitsInLine):
    """The chance out of 100 that an arrow hits its target past unitsInLine units."""
    return 100 - shooter.strayChance - shooter.lineShare * unitsInLine


def canShoot(gameManager, fromSpot, toSpot, shooter):
    """Can shooter, standing on fromSpot, shoot at toSpot: in range, a clear line, and a chance left for the target?"""
    if fromSpot == toSpot or distance(gameManager, fromSpot, toSpot) > shooter.range:
        return False
    between = shotLine(gameManager, fromSpot, toSpot)
    if between is None:
        return False
    return targetShare(shooter, len(unitsOnLine(gameManager, between, shooter))) > 0


def rollShot(gameManager, fromSpot, toSpot, shooter, roll=None):
    """Where one arrow lands: ("stray", a neighbor of the target), ("line", the spot of a unit on the line) or
    ("target", toSpot). roll: 0 to 100 (random when not given)."""
    if roll is None:
        roll = rand.random() * 100
    if roll < shooter.strayChance:
        return "stray", rand.choice(gameManager.eightAround(toSpot))
    left = roll - shooter.strayChance
    for spot, _ in unitsOnLine(gameManager, shotLine(gameManager, fromSpot, toSpot) or [], shooter):
        if left < shooter.lineShare:
            return "line", spot
        left -= shooter.lineShare
    return "target", toSpot


def shoot(gameManager, fromSpot, shooter, toSpot):
    """shooter fires one arrow from fromSpot at toSpot. Returns who it hit ("player", a unit) or None."""
    gameManager.faceToward(shooter, fromSpot, toSpot)
    _, landing = rollShot(gameManager, fromSpot, toSpot, shooter)
    struck = whoIsAt(gameManager, landing)
    gameManager.startArrow(fromSpot, landing, struck is not None, getattr(shooter, "look", None))
    if struck == "player":
        gameManager.hitPlayer(shooter, fromSpot, damage=shooter.arrowDamage, arrow=True)
    elif struck is not None:
        expansion.attack(gameManager, fromSpot, shooter, struck, landing, damage=shooter.arrowDamage,
                         fightsBack=expansion.hostile(shooter, struck))
    gameManager.change = True
    return struck


# ---------------------------------------------------------------- a wild archer's turn

def seesPlayer(gameManager, spot, shooter):
    """Can shooter, on spot, see you (the way gameManager.enemyAct decides it)?"""
    if gameManager.peaceful:
        return False
    player = gameManager.playerPositionFlat
    if not shooter.allSight and player not in gameManager.rayCircleVision(spot, shooter.visionRange, ENEMY_SIGHT_KIND,
                                                                          shooter.tremorSense):
        return False
    return not (gameManager.playerHidden() and player not in gameManager.neighbors(spot))


def stepBack(gameManager, spot, shooter, foeSpot):
    """An open tile beside spot that's farther from foeSpot, best first one it could still shoot from, then the
    farthest; None if there's nowhere to go."""
    here = distance(gameManager, spot, foeSpot)
    choices = [beside for beside in gameManager.neighbors(spot)
               if gameManager.grid[beside][0] == FLOOR_TILE and distance(gameManager, beside, foeSpot) > here]
    if not choices:
        return None
    return max(choices, key=lambda beside: (canShoot(gameManager, beside, foeSpot, shooter),
                                            distance(gameManager, beside, foeSpot)))


def wildTurn(gameManager, spot, shooter):
    """A wild archer's turn when it sees you: step back if you're too close, else shoot if it can. Returns where it
    is now, or None for its usual turn (coming at you, or hitting you when it's right beside you)."""
    player = gameManager.playerPositionFlat
    if not seesPlayer(gameManager, spot, shooter):
        return None
    shooter.lastPlayerPosition = player
    if distance(gameManager, spot, player) <= shooter.keepAway:
        away = stepBack(gameManager, spot, shooter, player)
        if away is not None:
            return away
    if player in gameManager.neighbors(spot):
        return None  # nowhere to go and right beside you: it fights
    if canShoot(gameManager, spot, player, shooter):
        shoot(gameManager, spot, shooter, player)
        return spot
    return None


# ---------------------------------------------------------------- a faction archer's turn

def factionTarget(gameManager, spot, shooter, turnContext):
    """The nearest foe a faction archer on spot can shoot: you (when its faction fights you and it sees you) or a
    unit it's hostile to. Its spot, or None."""
    targets = []
    player = gameManager.playerPositionFlat
    if expansion.huntsPlayer(gameManager, shooter) and distance(gameManager, spot, player) <= shooter.range \
            and seesPlayer(gameManager, spot, shooter):
        targets.append(player)
    for nearSpot, unit in expansion.near(gameManager, turnContext, spot, shooter.range):
        if unit is shooter or unit.hp <= 0 or not expansion.hostile(shooter, unit):
            continue
        at = expansion.find(gameManager, turnContext, unit)
        if at is not None and at not in gameManager.smoke:
            targets.append(at)
    targets = [target for target in targets if canShoot(gameManager, spot, target, shooter)]
    return min(targets, key=lambda target: distance(gameManager, spot, target), default=None)
