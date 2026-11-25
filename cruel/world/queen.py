import random

from cruel.entities import enemies
from cruel.world import dwellers
from cruel.world import expansion
from cruel.world import metropolis
from cruel.world import occupancy

"""
The Dweller Queen and her court (design sheet: https://claude.ai/artifact/8crUvVgcwiWWNoooJmPKyY).

  The Queen       one to a city, in the middle of the Queen's Chamber (metropolis.placeCourt). A large unit (2 x 2,
                  enemies.DwellerQueen) that never moves. Each turn she hits one thing within her reach of her body
                  that she can see: you, once she's hostile (she saw you do something hostile, or you hurt her), or
                  else the nearest enemy of the city (dwellers.isCityEnemy). Hurting her is hostile, like hurting
                  any Dweller.
  Royal Guards    stronger guards in royal colors (enemies.RoyalGuard) at posts round her. They take a guard's turn
                  but never go more than their leash from their post (dwellers.withinLeash).
  Pupating        Royal Guards are never hatched. While there are fewer than metropolis.ROYAL_GUARDS (pupae count),
                  each turn there's a PUPATE_CHANCE that the city guard nearest the Queen pupates where it stands
                  (one at a time): it becomes a Royal Pupa (enemies.RoyalPupa) that can't move or fight, and
                  PUPA_TURNS turns on comes out a Royal Guard (takeTurn), which goes to a free post beside the Queen.
"""

PUPATE_CHANCE = 0.02
PUPA_TURNS = 40


def isQueen(unit):
    return getattr(unit, "role", None) == "queen"


def isRoyal(unit):
    return getattr(unit, "royal", False)


def isPupa(unit):
    return getattr(unit, "role", None) == "pupa"


def courtOf(game):
    """(her anchor, the Queen) on this floor, or None."""
    return next(((spot, unit) for spot, unit in dwellers.cityDwellers(game) if isQueen(unit)), None)


# ---------------------------------------------------------------- the Queen's turn

def sees(game, anchor, queen, spot):
    """Can the Queen see spot from her body: right beside it, or within her vision with a clear line from one of
    her tiles?"""
    if game.reachOf(queen, anchor, spot) <= 1:
        return True
    return any(dwellers.distance(game, tile, spot) <= queen.visionRange and game.lineOfSight(tile, spot)
               for tile in game.footprint(anchor, queen.size))


def youInReach(game, anchor, queen):
    """Are you within her reach and in her sight, with her hostile to you?"""
    player = game.playerPositionFlat
    return not game.peaceful and queen.hostile and game.reachOf(queen, anchor, player) <= queen.reach \
        and sees(game, anchor, queen, player)


def enemyInReach(game, anchor, queen):
    """(position, enemy) of the nearest enemy of the city within her reach that she can see, or None."""
    found = []
    for spot in set(game.EnemyPositions) | getattr(game, "movedEnemies", set()):
        tile = game.grid.get(spot)
        if not (tile and tile[0] == 5 and len(tile) > 2 and dwellers.isCityEnemy(tile[2])):
            continue
        reach = game.reachOf(queen, anchor, spot)
        if reach <= queen.reach and sees(game, anchor, queen, spot):
            found.append((reach, spot, tile[2]))
    if not found:
        return None
    _, spot, enemy = min(found, key=lambda item: item[0])
    return spot, enemy


def queenTurn(game, anchor, queen):
    """One action for the Queen: she never moves. She hits you if you're within reach and she's hostile, otherwise
    the nearest enemy of the city within reach. Returns her anchor."""
    if youInReach(game, anchor, queen):
        game.hitPlayer(queen, anchor)
        return anchor
    found = enemyInReach(game, anchor, queen)
    if found is not None:
        enemySpot, enemy = found
        expansion.attack(game, anchor, queen, enemy, enemySpot)  # (it fights back)
    return anchor


# ---------------------------------------------------------------- Royal Guards and pupating

def royalCount(game):
    """Royal Guards and pupae on the floor."""
    return sum(1 for _, unit in dwellers.cityDwellers(game) if isRoyal(unit) or isPupa(unit))


def freePost(game, queen):
    """A post round the Queen with no Royal Guard (or pupa) going to it, or her first post."""
    units = dwellers.cityDwellers(game)
    claimed = {unit.home for _, unit in units if isRoyal(unit)} | {unit.post for _, unit in units if isPupa(unit)}
    free = [post for post in queen.royalPosts if post not in claimed]
    return free[0] if free else (queen.royalPosts[0] if queen.royalPosts else queen.anchor)


def stepCourt(game):
    """The court's turn (gameManager.enemyTurn and awayTurn): short of Royal Guards, with no guard already
    pupating, maybe (PUPATE_CHANCE) the city guard nearest the Queen pupates where it stands. Returns the pupa, or
    None."""
    if not dwellers.onDwellerFloor(game):
        return None
    court = courtOf(game)
    if court is None:
        return None
    anchor, queen = court
    units = dwellers.cityDwellers(game)
    if any(isPupa(unit) for _, unit in units) or royalCount(game) >= metropolis.ROYAL_GUARDS:
        return None
    if random.random() >= PUPATE_CHANCE:
        return None
    guards = [(spot, unit) for spot, unit in units if unit.role == "guard" and not isRoyal(unit)]
    if not guards:
        return None
    spot, guard = min(guards, key=lambda found: game.reachOf(queen, anchor, found[0]))
    pupa = enemies.RoyalPupa(PUPA_TURNS, freePost(game, queen))
    pupa.hostile = guard.hostile
    if occupancy.sharedTiles(game).get(spot) is guard:
        occupancy.sharedTiles(game)[spot] = pupa
    else:
        game.grid[spot][2] = pupa
    game.change = True
    return pupa


def takesTurn(unit):
    """Does this unit take its turn here (takeTurn) rather than as a Dweller?"""
    return isPupa(unit)


def takeTurn(game, position, unit):
    """One action for a Royal Pupa: it waits, and when its time is up it comes out a Royal Guard headed for its
    post. Returns (where it is, the unit there now)."""
    unit.turnsLeft -= 1
    if unit.turnsLeft > 0:
        return position, unit
    royal = enemies.RoyalGuard()
    royal.home = royal.goal = unit.post if unit.post is not None else position
    royal.hostile = unit.hostile
    game.change = True
    return position, royal
