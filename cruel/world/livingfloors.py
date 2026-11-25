import copy
from contextlib import contextmanager

from cruel.world import metropolis
from cruel.world import mineshafts
from cruel.world import occupancy

"""
Floors near you keep going while you're not on them. Every turn (gameManager.enemyTurn) the floors in reach take
their own turn as well, at the same pace as yours (awayTurn: their units, goblin camps, burning, Demise, blood,
floor events and plants; nothing that's only round you, and nothing ever touches you there):

  floorsInReach  the floor you're on counts as floor N (on a city's mine or farm, its city is N); floors N-ABOVE
                 to N+BELOW that exist and that you can still get back to run, and every city among them (N's too)
                 brings its mine and farm floors along, made the first time if you've never been down
                 (ensureWorksFloors).
  awayFloor      puts a floor you're not on in place of yours for its turn (its tiles, units, what's kept for its
                 number), with you nowhere on it (peaceful: nothing there sees or hits you), and then puts yours back.
                 Nothing on it is drawn or heard while it does (gameManager.onScreen): a hit there leaves its blood
                 but makes no spurt or flecks, and nothing there plays a sound, pops up a message or redraws your
                 screen. That keeps it from showing on yours, and keeps its turn cheap.

Walking between floors: a Dweller beside a mineshaft can climb it (climb). It leaves its floor, and comes out by
the shaft's other end at the start of that floor's next turn (arrive: on the free tile nearest the shaft), whether
that's the floor you're on or one of those that keep going. Until then it waits in game.shaftArrivals ({floor key:
[(unit, shaft position)]}, saved with the game).

A new track: once you're on a floor with no door back up (gameManager.trackStarts), the floors above the latest
such floor at or above you can never be reached again. dropUnreachable empties them (from memory and the save),
and nothing simulates them.
"""

ABOVE = 2   # floors above yours that keep going
BELOW = 2   # and below
FLOOR_FIELDS = ("grid", "rooms", "proportion", "EnemyPositions", "enemyOccupiedItemSpaces", "theme", "blood", "bloodDry")
LIVE_FIELDS = FLOOR_FIELDS + ("level", "sideFloor", "peaceful", "simulatingAway", "smoke", "fires", "freshFires",
                              "movedEnemies", "nodes", "sharedTiles", "sharedTilesGrid", "playerPositionFlat",
                              "change")  # (a floor you're not on changing doesn't redraw yours)


# ---------------------------------------------------------------- which floors

def firstReachable(game):
    """The highest floor you can still get to: the latest floor with no door back up at or above yours (0 if
    there's none)."""
    here = mineshafts.floorNumber(mineshafts.floorKey(game))
    starts = [start for start in getattr(game, "trackStarts", ()) if start <= here]
    return max(starts) if starts else 0


def floorData(game, key):
    """The saved data list of a floor you're not on (or None if there isn't one)."""
    here = mineshafts.floorKey(game)
    if isinstance(key, tuple):
        record = game.floorsAside.get(key)
        return record["levelGrid"] if record else None
    if key == mineshafts.floorNumber(here) and isinstance(here, tuple):  # your city, while you're on its works floor
        return game.cityAside["levelGrid"] if game.cityAside else None
    return game.levelGrids[key] if 0 <= key < len(game.levelGrids) else None


def floorsInReach(game):
    """The keys (a floor number, or (number, shaft) for a works floor) of the floors that take a turn while you're
    not on them, nearest first."""
    here = mineshafts.floorKey(game)
    number = mineshafts.floorNumber(here)
    onWorksFloor = isinstance(here, tuple)
    keys = []
    for level in sorted(range(max(firstReachable(game), number - ABOVE), number + BELOW + 1), key=lambda level: abs(level - number)):
        if level == number and not onWorksFloor:  # the floor you're on
            isCity = game.proportion == metropolis.METROPOLIS
        else:
            data = floorData(game, level)
            if data is None:
                continue
            keys.append(level)
            isCity = data[2] == metropolis.METROPOLIS
        if isCity:
            keys += ensureWorksFloors(game, level)
    return [key for key in keys if key != here]


def cityGridOf(game, level):
    """The tiles of the city at level (the floor you're on, your city while you're below it, or a saved one)."""
    here = mineshafts.floorKey(game)
    if here == level:
        return game.grid
    if isinstance(here, tuple) and here[0] == level:
        return game.cityAside["levelGrid"][0]
    return game.levelGrids[level][0]


def shaftsOf(game, level):
    """{shaft spot: works kind} for the city at level's mineshafts down (the one you stand on included)."""
    grid = cityGridOf(game, level)
    shafts = {spot: tile[2].kind for spot, tile in grid.items()
              if tile[0] == metropolis.MINESHAFT and len(tile) > 2 and getattr(tile[2], "down", False)}
    standingOn = game.currentLocation if mineshafts.floorKey(game) == level else None
    if standingOn is not None and standingOn[0] == metropolis.MINESHAFT and getattr(standingOn[2], "down", False):
        shafts[game.playerPositionFlat] = standingOn[2].kind
    return shafts


def ensureWorksFloors(game, level):
    """The keys of the city at level's mine and farm floors, making any that's never been made (as if you'd gone
    down its shaft, but without you)."""
    here = mineshafts.floorKey(game)
    keys = []
    for shaft, kind in sorted(shaftsOf(game, level).items()):
        key = (level, shaft)
        if key != here and key not in game.floorsAside:
            makeWorksFloor(game, level, shaft, kind)
        keys.append(key)
    return keys


# ---------------------------------------------------------------- putting a floor in place of yours

def stashLive(game):
    return {field: getattr(game, field, None) for field in LIVE_FIELDS}


def restoreLive(game, live):
    for field, value in live.items():
        setattr(game, field, value)


def takeNumbered(game, level):
    """Takes everything kept for floor number level out of the game's stores ({"dicts", "sets"})."""
    kept = {"dicts": {}, "sets": {}}
    for name in mineshafts.PER_FLOOR_DICTS:
        store = getattr(game, name)
        if level in store:
            kept["dicts"][name] = store.pop(level)
    for name in mineshafts.PER_FLOOR_SETS:
        store = getattr(game, name)
        kept["sets"][name] = level in store
        store.discard(level)
    return kept


def putNumbered(game, level, kept):
    for name, value in kept["dicts"].items():
        getattr(game, name)[level] = value
    for name, member in kept["sets"].items():
        if member:
            getattr(game, name).add(level)


def recordOf(game, key):
    """The record holding a floor's own kept things (a works floor's, or your city's while you're below it), or None
    for a floor that keeps them in the game's stores under its number."""
    here = mineshafts.floorKey(game)
    if isinstance(key, tuple):
        return game.floorsAside.get(key)
    if isinstance(here, tuple) and key == here[0]:
        return game.cityAside
    return None


@contextmanager
def awayFloor(game, key):
    """While it lasts, the floor key is in place of yours: its tiles and units, and what's kept for its number, with
    you nowhere on it. Then yours is put back."""
    live = stashLive(game)
    level = mineshafts.floorNumber(key)
    record = recordOf(game, key)
    data = floorData(game, key)
    yours = takeNumbered(game, level) if record is not None else None
    if record is not None:
        putNumbered(game, level, record)
    try:
        for field, value in zip(FLOOR_FIELDS, data):
            setattr(game, field, value)
        occupancy.useShared(game, data[8] if len(data) > 8 else {})
        game.level = level
        game.sideFloor = (worksKind(data[0], key[1]), key[1]) if isinstance(key, tuple) else None
        game.peaceful = True          # nothing on it can see or hit you (you're not there)
        game.simulatingAway = True    # nothing on it is shown or heard (gameManager.onScreen)
        game.smoke, game.fires, game.freshFires = {}, {}, set()
        yield
    finally:
        data[:] = [getattr(game, field) for field in FLOOR_FIELDS] + [occupancy.sharedTiles(game)]
        if record is not None:
            kept = takeNumbered(game, level)
            record["dicts"], record["sets"] = kept["dicts"], kept["sets"]
            putNumbered(game, level, yours)
        restoreLive(game, live)


def worksKind(grid, shaft):
    tile = grid.get(shaft)
    return tile[2].kind if tile is not None and tile[0] == metropolis.MINESHAFT and len(tile) > 2 else "mine"


def makeWorksFloor(game, level, shaft, kind):
    """Makes the works floor down the city at level's shaft (of kind), as going down it would, and keeps it aside
    (game.floorsAside) for when you do, all without you or the floor you're on changing."""
    live = stashLive(game)
    theme = game.theme
    yours = takeNumbered(game, level)
    floorsBefore = len(game.levelGrids)
    game.levelGrids.extend([None] * (level + 1 - floorsBefore))  # (a city not saved yet has no place in the list)
    savedGrid = game.levelGrids[level]
    try:
        game.level, game.sideFloor, game.playerPositionFlat = level, (kind, shaft), shaft
        mineshafts.newWorksFloor(game, kind)
        data = [getattr(game, field) for field in FLOOR_FIELDS] + [{}]
        kept = takeNumbered(game, level)
        game.floorsAside[(level, shaft)] = {"levelGrid": data, "dicts": kept["dicts"], "sets": kept["sets"]}
    finally:
        game.levelGrids[level] = savedGrid
        del game.levelGrids[max(floorsBefore, level + 1):]
        if floorsBefore <= level:
            del game.levelGrids[floorsBefore:]
        putNumbered(game, level, yours)
        restoreLive(game, live)
        game.setTheme(theme)  # (making it set the theme to its own colors)


# ---------------------------------------------------------------- taking turns

def simulate(game):
    """The floors in reach (floorsInReach) take their turn."""
    for key in floorsInReach(game):
        if floorData(game, key) is None:
            continue
        with awayFloor(game, key):
            game.awayTurn()


# ---------------------------------------------------------------- a new track

def dropUnreachable(game):
    """Empties every floor above the first you can still reach (firstReachable): its saved tiles, its works floors
    and what's kept for its number go, and a crafting station set up on it is packed. Returns how many floors
    went."""
    first = firstReachable(game)
    dropped = 0
    for level in range(min(first, len(game.levelGrids))):
        if game.levelGrids[level] is not None:
            game.levelGrids[level] = None
            dropped += 1
        takeNumbered(game, level)
    for key in [key for key in game.floorsAside if key[0] < first]:
        del game.floorsAside[key]
    for key in [key for key in arrivals(game) if mineshafts.floorNumber(key) < first]:
        del arrivals(game)[key]
    for station, (floor, _) in list(game.player.stationPlaced.items()):
        if mineshafts.floorNumber(floor) < first:
            del game.player.stationPlaced[station]
    return dropped


# ---------------------------------------------------------------- walking between floors

def arrivals(game):
    """{floor key: [(unit, shaft position)]}: who has climbed a shaft and will come out on that floor."""
    if getattr(game, "shaftArrivals", None) is None:
        game.shaftArrivals = {}
    return game.shaftArrivals


def otherEnd(game, shaftSpot):
    """The floor key at the other end of the shaft at shaftSpot on the floor taking its turn: down a city's shaft,
    its works floor; up a works floor's, the city."""
    shaft = game.grid[shaftSpot][2]
    return (game.level, shaftSpot) if getattr(shaft, "down", True) and getattr(game, "sideFloor", None) is None else game.level


def climb(game, position, unit, shaftSpot):
    """unit (lifted off position for its turn, beside the shaft at shaftSpot) climbs it: it leaves this floor
    (position is left as if it had walked off it; leaving(unit) is true until it's put down) and comes out on the
    other end's floor at its next turn."""
    occupancy.leave(game, position)
    unit.climbing = True
    arrivals(game).setdefault(otherEnd(game, shaftSpot), []).append((unit, shaftSpot))
    game.change = True


def leaving(unit):
    """Did this unit just climb a shaft (so it isn't put back on this floor)?"""
    return getattr(unit, "climbing", False)


def nearestFree(game, spot, reach=6):
    """The open floor tile nearest spot (spot itself counts), within reach rings, or None."""
    rowLength = game.rowLength
    column, row = spot % rowLength, spot // rowLength
    for ring in range(reach + 1):
        ringTiles = [(column + stepColumn) + (row + stepRow) * rowLength for stepRow in range(-ring, ring + 1)
                     for stepColumn in range(-ring, ring + 1) if max(abs(stepColumn), abs(stepRow)) == ring
                     and 0 <= column + stepColumn < rowLength]
        free = [tile for tile in ringTiles if tile in game.grid and game.grid[tile][0] == 0 and tile != game.playerPositionFlat]
        if free:
            return min(free, key=lambda tile: abs(tile % rowLength - column) + abs(tile // rowLength - row))
    return None


def arrive(game):
    """The start of a floor's turn: everyone who climbed a shaft to it comes out on the free tile nearest the
    shaft (one with nowhere to stand waits another turn). Returns how many came out."""
    key = mineshafts.floorKey(game)
    waiting = arrivals(game).pop(key, [])
    stillWaiting, came = [], 0
    for unit, shaftSpot in waiting:
        spot = nearestFree(game, shaftSpot)
        if spot is None:
            stillWaiting.append((unit, shaftSpot))
            continue
        unit.climbing = False
        game.grid[spot] = [5, game.grid[spot][1], unit]
        game.EnemyPositions.add(spot)
        came += 1
    if stillWaiting:
        arrivals(game)[key] = stillWaiting
    if came:
        game.change = True
    return came
