from cruel.world import dwellerfarming
from cruel.world import dwellers
from cruel.world import dwellerwork
from cruel.world import mineshafts
from cruel.world import plants
from cruel.world import wall

"""
The Dwellers keeping Overgrowth (events.py) off their buildings. While the event is on, any calm Dweller on the floor
(a city or its works floors) with nothing more pressing comes out to clear what's growing near the buildings: within
QUELL_REACH of any building's wall (not the city's own outer wall), it pulls up wild plants (keeping what a ripe one
gives, like a farmer picking a crop: dwellerfarming.pickCrop) and deals with walls the plants have corrupted: a
building's wall has the vines scraped off it; a rock wall is broken (dwellerwork.MINE_SWING a swing, like a miner).
Planted crops are left alone.

Each Dweller takes the nearest such spot (within QUELL_SEARCH) that no other Dweller has claimed in the last
CLAIM_TURNS turns, so they spread out over the work. Merchants stay at their counters, a farm's keepers keep
feeding the grubs, and a Dweller on an errand (carrying Dew or an egg, or on its way to work on a works floor)
finishes it first (quells).
"""

QUELL_REACH = 4         # tiles round a building that the Dwellers keep clear during Overgrowth
QUELL_SEARCH = 20       # how far a Dweller looks for something to clear
CLAIM_TURNS = 10        # a spot one Dweller is clearing isn't taken by another for this long
PLANT = 8
ZONE_TURNS = 25         # the ground round the buildings is worked out again this often (walls get built or broken)


def overgrowthOn(game):
    return dwellers.onDwellerFloor(game) and game.activeEvent() == "overgrowth"


def isWild(tile):
    """A plant growing wild (not a planted crop)."""
    return tile[0] == PLANT and len(tile) > 2 and not tile[2].planted


def isCorrupted(tile):
    return plants.corruptedBy(tile) is not None


def isBuildingWall(tile):
    return tile[0] == dwellerwork.WALL and len(tile) > 2 and isinstance(tile[2], wall.CityBuildingWall) \
        and not isinstance(tile[2], wall.CityWall)


def nearBuildings(game):
    """Every tile within QUELL_REACH of a building's wall on this floor (worked out every ZONE_TURNS turns)."""
    key = (mineshafts.floorKey(game), game.turnCount // ZONE_TURNS, id(game.grid))
    cache = game.__dict__.setdefault("quellZone", {})
    if key not in cache:
        cache.clear()
        rowLength, zone = game.rowLength, set()
        for spot, tile in game.grid.items():
            if not isBuildingWall(tile):
                continue
            column, row = spot % rowLength, spot // rowLength
            for stepRow in range(-QUELL_REACH, QUELL_REACH + 1):
                for stepColumn in range(-QUELL_REACH, QUELL_REACH + 1):
                    if 0 <= column + stepColumn < rowLength:
                        zone.add(spot + stepColumn + stepRow * rowLength)
        cache[key] = zone
    return cache[key]


def targets(game):
    """The spots to clear this turn: wild plants and corrupted walls near the buildings (worked out once a turn)."""
    key = (mineshafts.floorKey(game), game.turnCount, id(game.grid))
    cache = game.__dict__.setdefault("quellTargets", {})
    if key not in cache:
        cache.clear()
        grid = game.grid
        cache[key] = [spot for spot in nearBuildings(game)
                      if spot in grid and (isWild(grid[spot]) or isCorrupted(grid[spot]))]
    return cache[key]


def stillToClear(game, spot):
    tile = game.grid.get(spot)
    return tile is not None and (isWild(tile) or isCorrupted(tile))


def quells(dweller):
    """Does this Dweller come out to clear? Not a merchant (it minds its shop), a farm's keeper (it feeds the
    grubs), or one on an errand that can't wait: a Dew carrier, one carrying or fetching an egg, one on its way to
    a works floor to work there (queen.py)."""
    if dweller.role not in ("citizen", "noble", "guard") or dwellerfarming.roleOf(dweller) == "keeper":
        return False
    return dweller.work != "dew" and not getattr(dweller, "joining", None) and getattr(dweller, "heldEgg", None) is None \
        and getattr(dweller, "eggTarget", None) is None


def quellTurn(game, position, dweller):
    """A calm Dweller's turn at clearing (see the top of this file). Returns where it ends up, or None with nothing
    to clear."""
    if not overgrowthOn(game) or not quells(dweller):
        return None
    claims = game.__dict__.setdefault("quellClaims", {})
    target = getattr(dweller, "quellTarget", None)
    if target is None or not stillToClear(game, target):
        claimedByOthers = {spot for spot, (who, when) in claims.items()
                           if who != id(dweller) and game.turnCount - when < CLAIM_TURNS}
        choices = [spot for spot in targets(game) if spot not in claimedByOthers and stillToClear(game, spot)
                   and dwellers.distance(game, position, spot) <= QUELL_SEARCH]
        if not choices:
            dweller.quellTarget = None
            return None
        target = dweller.quellTarget = dwellerwork.nearest(game, position, choices)
    claims[target] = (id(dweller), game.turnCount)
    if target in game.neighbors(position):
        clear(game, position, target, dweller)
        return position
    return dwellerwork.walkTo(game, position, dweller, target)


def clear(game, position, spot, dweller):
    """The Dweller beside spot clears it: pulls up the wild plant, scrapes the vines off a building's wall, or
    takes a swing at a corrupted rock wall."""
    tile = game.grid[spot]
    if isWild(tile):
        if not hasattr(dweller, "materials") or dweller.materials is None:
            dweller.materials = {}
        dwellerfarming.pickCrop(game, spot, dweller)
    elif isBuildingWall(tile):
        tile[2].corruptedBy = None
    else:
        game.chip(spot, position)
        tile[2].takeDamage(dwellerwork.MINE_SWING, game.tileSize)
        if tile[2].hp <= 0:
            game.grid[spot] = [dwellerwork.FLOOR, tile[1]]
    if not stillToClear(game, spot):
        dweller.quellTarget = None
        game.__dict__.setdefault("quellClaims", {}).pop(spot, None)
    game.change = True
