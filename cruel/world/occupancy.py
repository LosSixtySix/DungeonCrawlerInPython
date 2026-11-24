"""
Unit sizes, and two units on one space.

Every unit has a size (sizeOf):
  small   half a space: Dire Rats, Young Dew Grubs, goblins (but chieftains), every Dweller citizen, noble, merchant
          and guard.
  medium  a whole space: you, and everything not small or large.
  large   a Fire Giant: it covers 4 spaces (its footprint), at half a space on each.
So a space holds one medium unit; or one or two small units; or a part of a giant and one small unit.

The first unit on a space is where it always was: the grid tile [5, visibility, unit]. A second (always small)
unit on it is kept in the floor's shared table (sharedTiles: {space: unit}), saved with the floor. A small unit can
step onto a space with one unit on it when canJoin says so: that unit is small or a giant, the space has no second
unit yet, and the two are on the same side (sameSide: not fighting each other).

Moving and placing go through leave and settle: a unit leaving a space that still holds another unit leaves it as
it is, and when the first unit leaves, the second takes its place on the grid (promote). settle puts a unit down on
a space, as the second unit if one is already there. allUnits lists every unit on the floor, second ones too.

Fighting: an enemy hitting a space with two units on it hits the one with the lowest HP (victimAt; a tie goes either
way, at random). Area damage (fire, magic, a bomb) reaches every unit in the area (unitsInArea). You choose which to
hit (gameManager's "attack" window).
"""

import random

SMALL, MEDIUM, LARGE = "small", "medium", "large"
ENEMY, FLOOR = 5, 0


def sizeOf(unit):
    """A unit's size (its unitSize: a class's, or a property of it). Medium if it doesn't say."""
    return getattr(unit, "unitSize", MEDIUM)


# ---------------------------------------------------------------- the shared table

def sharedTiles(game):
    """{space: second unit} for the floor you're on (a fresh table for a floor that hasn't got one)."""
    if getattr(game, "sharedTilesGrid", None) is not game.grid:
        game.sharedTiles = {}
        game.sharedTilesGrid = game.grid
    return game.sharedTiles


def useShared(game, table):
    """The floor just loaded keeps this shared table (from its saved data)."""
    game.sharedTiles = table if table is not None else {}
    game.sharedTilesGrid = game.grid


def primaryAt(game, spot):
    tile = game.grid.get(spot)
    return tile[2] if tile is not None and tile[0] == ENEMY and len(tile) > 2 else None


def unitsAt(game, spot):
    """The units on a space: the first, then the second if there is one."""
    first = primaryAt(game, spot)
    second = sharedTiles(game).get(spot)
    return [unit for unit in (first, second) if unit is not None]


def allUnits(game):
    """(space, unit) for every unit on the floor, second ones too (during the enemies' turn, also the ones that
    have already moved: gameManager.movedEnemies). A giant is listed once, at its anchor."""
    found, seen = [], set()
    for spot in set(game.EnemyPositions) | getattr(game, "movedEnemies", set()):
        unit = primaryAt(game, spot)
        if unit is not None and id(unit) not in seen:
            seen.add(id(unit))
            found.append((spot, unit))
    for spot, unit in sharedTiles(game).items():
        if id(unit) not in seen:
            seen.add(id(unit))
            found.append((spot, unit))
    return found


def victimAt(game, spot, target):
    """Who a hit aimed at target on spot lands on: with two units there, the one with the lowest HP (a tie: either,
    at random)."""
    units = unitsAt(game, spot)
    if len(units) < 2 or target not in units:
        return target
    lowest = min(unit.hp for unit in units)
    return random.choice([unit for unit in units if unit.hp == lowest])


def unitsInArea(game, area):
    """(space, unit) for every unit on the spaces of area, each once (a giant covering several of them included)."""
    found, seen = [], set()
    for spot in area:
        for unit in unitsAt(game, spot):
            if id(unit) not in seen:
                seen.add(id(unit))
                found.append((spot, unit))
    return found


def positionOf(game, unit):
    """Where a unit is (its space), or None."""
    return next((spot for spot, other in allUnits(game) if other is unit), None)


# ---------------------------------------------------------------- who can share

def sameSide(unit, other):
    """Are these two not fighting each other? Dwellers with Dwellers (unless one has turned on you and the other
    hasn't: they still don't fight); goblins of one faction; wild monsters with wild monsters."""
    unitDweller, otherDweller = getattr(unit, "dweller", False), getattr(other, "dweller", False)
    if unitDweller or otherDweller:
        return unitDweller and otherDweller
    return getattr(unit, "faction", None) == getattr(other, "faction", None)


def canJoin(game, spot, unit):
    """Can unit (small) step onto spot as its second unit?"""
    if sizeOf(unit) != SMALL or spot in sharedTiles(game) or spot == game.playerPositionFlat:
        return False
    first = primaryAt(game, spot)
    return first is not None and first is not unit and sizeOf(first) in (SMALL, LARGE) and sameSide(unit, first)


# ---------------------------------------------------------------- moving

def lift(game, spot, unit):
    """Takes unit off spot for its turn (first or second unit there). True if it was there."""
    tile = game.grid.get(spot)
    if tile is not None and tile[0] == ENEMY and len(tile) > 2 and tile[2] is unit:
        tile.pop()
        return True
    if sharedTiles(game).get(spot) is unit:
        del sharedTiles(game)[spot]
        return True
    return False


def settle(game, spot, unit):
    """Puts unit down on spot (its tile already marked as an enemy's): as the second unit if one is there."""
    tile = game.grid[spot]
    if len(tile) > 2 and tile[2] is not unit:
        sharedTiles(game)[spot] = unit
    elif len(tile) <= 2:
        tile.append(unit)


def promote(game, spot):
    """The first unit has gone from spot: the second, if there is one, takes its place on the grid (on top of
    whatever lies there). True if one did."""
    second = sharedTiles(game).pop(spot, None)
    if second is None:
        return False
    tile = game.grid[spot]
    if tile[0] != FLOOR and tile[0] != ENEMY:
        game.enemyOccupiedItemSpaces[spot] = tile
    game.grid[spot] = [ENEMY, tile[1], second]
    for positions in (game.EnemyPositions, getattr(game, "movedEnemies", set())):
        positions.add(spot)
    return True


def leave(game, spot):
    """A unit (already lifted) leaves spot: if another unit is still there, the space stays as it is; if not, what
    it stood on comes back, and the second unit there (if any) takes its place."""
    if stillOccupied(game, spot):
        return
    if spot in game.enemyOccupiedItemSpaces:
        game.grid[spot] = game.enemyOccupiedItemSpaces.pop(spot)
    else:
        game.grid[spot][0] = FLOOR
    promote(game, spot)


def stillOccupied(game, spot):
    """Is another unit still on spot (the one leaving was its second unit)?"""
    tile = game.grid[spot]
    return tile[0] == ENEMY and len(tile) > 2
