import random

from cruel.entities import enemies
from cruel.world import dwellers
from cruel.world import dwellerfarming
from cruel.world import dwellerwork
from cruel.world import expansion
from cruel.world import livingfloors
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
  Dew carriers    metropolis.CARRIERS of a city's citizens are set aside (work "dew") to feed the Queen Dew from the
                  farm (carrierTurn). Empty-handed in the city, one walks to the farm's shaft and climbs down
                  (livingfloors.climb), but only AT_ONCE are down on the farm at a time (Queen.carriersAway: so
                  they don't crowd the farmers at the storehouse); on the farm it takes up to CARRY Dew from the storehouse chests, climbs back
                  up, walks to the Queen and feeds it all to her (queen.dew). Finding no Dew there, it climbs back up
                  and goes about the city for REST_TURNS before trying again (so they don't crowd the farm). On any
                  other floor it climbs back up. It deals with the city's enemies like any citizen first.
"""

PUPATE_CHANCE = 0.02
PUPA_TURNS = 40
CARRY = 10                  # Dew a carrier takes from the farm each trip
REST_TURNS = 50             # a carrier that found no Dew on the farm waits this long in the city before going again
AT_ONCE = 2                 # carriers down on the farm at a time...
AWAY_LIMIT = 300            # ...not counting one that went down this long ago and hasn't come back (it may have died there)


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


# ---------------------------------------------------------------- the Dew carriers

def shaftsHere(game, kind=None):
    """Where this floor's mineshafts are (of kind, if given: the works kind each goes to)."""
    return [spot for spot, tile in game.grid.items() if tile[0] == metropolis.MINESHAFT and len(tile) > 2
            and (kind is None or getattr(tile[2], "kind", None) == kind)]


def climbOrWalk(game, position, carrier, shaftSpot):
    """Beside the shaft, the carrier climbs it; otherwise it takes a step toward it."""
    if shaftSpot in game.neighbors(position):
        livingfloors.climb(game, position, carrier, shaftSpot)
        return position
    return dwellerwork.walkTo(game, position, carrier, shaftSpot, reach=dwellers.FAR_PATH_REACH)


def carriersAway(game, dwellerQueen):
    """{carrier: the turn it went down}: the Queen's carriers down on the farm now (forgetting any gone longer than
    AWAY_LIMIT)."""
    away = getattr(dwellerQueen, "carriersAway", None)
    if away is None:
        away = dwellerQueen.carriersAway = {}
    for carrier in [carrier for carrier, went in away.items() if game.turnCount - went > AWAY_LIMIT]:
        del away[carrier]
    return away


def feed(dwellerQueen, carrier):
    """The carrier feeds the Queen all the Dew it carries. Returns how much."""
    dew = carrier.materials.pop("dew", 0)
    dwellerQueen.dew = getattr(dwellerQueen, "dew", 0) + dew
    return dew


def carrierTurn(game, position, carrier):
    """A Dew carrier's turn (see the top of this file). Returns where it ends up, or None with nothing to do (no
    Queen, or no farm shaft: it wanders like any citizen)."""
    dew = carrier.materials.get("dew", 0)
    side = getattr(game, "sideFloor", None)
    if side is None:  # the city
        court = courtOf(game)
        if court is None:
            return None
        anchor, dwellerQueen = court
        away = carriersAway(game, dwellerQueen)
        away.pop(carrier, None)  # (it's back)
        if dew:
            if game.reachOf(dwellerQueen, anchor, position) <= 1:
                feed(dwellerQueen, carrier)
                game.change = True
                return position
            return dwellerwork.walkTo(game, position, carrier, anchor, reach=dwellers.FAR_PATH_REACH)
        farmShafts = shaftsHere(game, "farm")
        if not farmShafts or game.turnCount < getattr(carrier, "restUntil", 0) or len(away) >= AT_ONCE:
            return None
        moved = climbOrWalk(game, position, carrier, dwellerwork.nearest(game, position, farmShafts))
        if livingfloors.leaving(carrier):
            away[carrier] = game.turnCount
        return moved
    kind, shaftSpot = side
    if kind == "farm" and dew < CARRY:
        fetched = dwellerfarming.fetch(game, position, carrier, {"dew"}, CARRY - dew)
        if fetched is not None:
            return fetched
        if not dew:  # (none in the chests: back up, and it rests a while before trying again)
            carrier.restUntil = game.turnCount + REST_TURNS
    return climbOrWalk(game, position, carrier, shaftSpot)
