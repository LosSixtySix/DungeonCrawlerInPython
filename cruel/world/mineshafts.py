import copy
import math
import random

from cruel.entities import enemies
from cruel.inventory import items
from cruel.world import events
from cruel.world import metropolis
from cruel.world import wall

"""
The Metropolis's works: its mine and its farm (metropolis.WORKS). Each is a building in the city with a mineshaft in
the middle (a metropolis.MINESHAFT tile). Stand on it and press Enter to climb down to the floor it works; climb the
shaft you arrive on to go back up.

  Mine   a Motherlode ore floor (a random ore floor for this depth, wall.ORE_FLOORS, with most of its walls ore).
  Farm   a Mixed cave floor.

Both have, round the shaft: a clearing (CLEARING_RADIUS), tunnels out of it to the caves, and STOREHOUSES
storehouses, each with STOREHOUSE_CHESTS chests (items.StorageChest, empty at first) where the workers put what
they bring in. Wall lamps light the clearing and the storehouses. WORKERS Dweller citizens work the floor and
GUARDS guards stand watch; no other monsters live there (though an Expansion war band can still come). A floor
event can happen there like on any other floor. The city's rules hold there too (dwellers.onDwellerFloor): stealing
from its chests, breaking its buildings' walls or hurting a Dweller turns whoever sees it hostile.

Side floors. A works floor is at the city's depth but off the way down: it has no door down or up, only its shaft.
While you're on one (gameManager.sideFloor), the city's floor is put aside (gameManager.cityAside: its saved grid and
everything kept for its floor number, see putAside) and the works floor takes the city's place at that number, so
everything that's kept per floor works there as it does anywhere. Going back up puts the works floor aside
(gameManager.floorsAside, by (floor, shaft position)) and the city back. You arrive where the shaft is: a works
floor's shaft up is right under the city's shaft down.
"""

CLEARING_RADIUS = 4         # the open ground round the shaft
TUNNELS = 4                 # tunnels dug out of the clearing (up, down, left, right) until they reach the caves
TUNNEL_REACH = 14           # how far a tunnel goes looking for open cave
STOREHOUSES = 2
STOREHOUSE_SIZE = 5         # a storehouse is a square this many tiles across (its walls round a 3x3 inside)
STOREHOUSE_CHESTS = 2
WORKERS = {"mine": (6, 9), "farm": (5, 8)}
GUARDS = (2, 4)
LAMP_RADIUS = 5
FLOOR, WALL, CHEST, ENEMY = 0, 2, 3, 5

# What's kept per floor number besides the saved grid (gameManager attributes): dicts of floor -> value, and sets of
# floors. putAside takes a floor's entries out of all of them; putBack puts them back.
PER_FLOOR_DICTS = ("floorEvents", "camps", "fallen", "memoryFade", "scorchedDoors", "wallLamps")
PER_FLOOR_SETS = ("motherlodes", "trackStarts")


# ---------------------------------------------------------------- side floors

def onSideFloor(game):
    return getattr(game, "sideFloor", None) is not None


def floorKey(game):
    """Which floor you're on: its number, or (its number, the shaft's position) on a works floor."""
    side = getattr(game, "sideFloor", None)
    return game.level if side is None else (game.level, side[1])


def floorNumber(key):
    """The floor number of a floorKey."""
    return key[0] if isinstance(key, tuple) else key


def floorLabel(key, works=None):
    """"4", or "4 (Dweller Mine)" for a works floor."""
    if not isinstance(key, tuple):
        return str(key)
    return f"{key[0]} ({metropolis.WORKS[works]})" if works else f"{key[0]} (a works floor)"


def putAside(game):
    """Takes the floor at game.level off the game: its saved grid and everything kept for its number. Returns it
    (for putBack). The floor must have been saved first (gameManager.saveLevel)."""
    level = game.level
    aside = {"levelGrid": game.levelGrids[level], "dicts": {}, "sets": {}}
    for name in PER_FLOOR_DICTS:
        store = getattr(game, name)
        if level in store:
            aside["dicts"][name] = store.pop(level)
    for name in PER_FLOOR_SETS:
        store = getattr(game, name)
        aside["sets"][name] = level in store
        store.discard(level)
    return aside


def putBack(game, aside):
    """Puts a floor taken off by putAside back at game.level and loads it."""
    level = game.level
    game.levelGrids[level] = aside["levelGrid"]
    for name, value in aside["dicts"].items():
        getattr(game, name)[level] = value
    for name, member in aside["sets"].items():
        if member:
            getattr(game, name).add(level)
    game.LoadLevel(level)


def climbDown(game, shaft):
    """Down the city's shaft to its works floor (made the first time)."""
    shaftSpot = game.playerPositionFlat
    game.saveLevel()
    game.cityAside = putAside(game)
    game.sideFloor = (shaft.kind, shaftSpot)
    aside = game.floorsAside.pop((game.level, shaftSpot), None)
    if aside is not None:
        putBack(game, aside)
    else:
        newWorksFloor(game, shaft.kind)
    game.currentLocation = copy.copy(game.grid[shaftSpot])
    game.afterLevelChange()


def climbUp(game):
    """Up a works floor's shaft, back to the city."""
    shaftSpot = game.sideFloor[1]
    game.saveLevel()
    game.floorsAside[(game.level, shaftSpot)] = putAside(game)
    putBack(game, game.cityAside)
    game.cityAside = None
    game.sideFloor = None
    game.currentLocation = copy.copy(game.grid[shaftSpot])
    game.afterLevelChange()


def climb(game):
    """You pressed Enter on a mineshaft: down it from the city, or up it back to the city."""
    shaft = game.currentLocation[2]
    if shaft.down:
        climbDown(game, shaft)
    else:
        climbUp(game)


def dropAsideBelow(game, last):
    """Works floors put aside below floor last are gone with their floors (gameManager.dropFloorsBelow)."""
    for key in [key for key in game.floorsAside if key[0] > last]:
        del game.floorsAside[key]


# ---------------------------------------------------------------- making a works floor

def newWorksFloor(game, kind):
    """Makes the works floor of this kind at game.level (with you on its shaft) and puts it in place."""
    level, shaftSpot = game.level, game.playerPositionFlat
    if kind == "mine":
        oreFloors = [name for name, info in wall.ORE_FLOORS.items() if info["first"] <= level]
        game.forcedOreFloor = (random.choice(oreFloors), True)
    else:
        game.forcedOreFloor = ("Mixed", False)
    game.grid, game.EnemyPositions, game.rooms, game.proportion, game.nodes = game.generateNewLevel(depth=level, allowCity=False)
    game.setTheme(game.newFloorTheme())
    game.enemyOccupiedItemSpaces = {}
    game.blood, game.bloodDry = {}, {}
    if game.newFloorMotherlode:
        game.motherlodes.add(level)
    for spot in list(game.EnemyPositions):  # nothing lives here but the city's own
        game.grid[spot] = [FLOOR, game.grid[spot][1]]
    game.EnemyPositions = set()
    works = layOutWorks(game.grid, game.rowLength, shaftSpot, kind)
    game.wallLamps[level] = works.lamps
    for spot, dweller in works.dwellers.items():
        game.grid[spot] = [ENEMY, 0, dweller]
        game.EnemyPositions.add(spot)
    event = events.roll(level)
    if event:
        game.floorEvents[level] = event
    game.levelGrids[level] = None  # (saveLevel fills it in when you leave)


class Works:
    """What layOutWorks built: the clearing, the storehouses (each {"walls", "inside", "door", "chests"}), the wall
    lamps ({tile: metropolis.WallLamp}) and the Dwellers ({tile: Dweller})."""

    def __init__(self):
        self.clearing = set()
        self.storehouses = []
        self.lamps = {}
        self.dwellers = {}


def inBounds(rowLength, rowCount, column, row, margin=1):
    return margin <= column < rowLength - margin and margin <= row < rowCount - margin


def openUp(grid, spot):
    """Makes spot open floor (whatever was there goes)."""
    grid[spot] = [FLOOR, grid[spot][1] if spot in grid else 0]


def layOutWorks(grid, rowLength, shaftSpot, kind):
    """Builds the works round the shaft on a new floor: the shaft up, the clearing, its tunnels, the storehouses,
    the lamps and the Dwellers. Returns a Works."""
    rowCount = len(grid) // rowLength
    works = Works()
    shaftColumn, shaftRow = shaftSpot % rowLength, shaftSpot // rowLength
    for rowOffset in range(-CLEARING_RADIUS, CLEARING_RADIUS + 1):
        for columnOffset in range(-CLEARING_RADIUS, CLEARING_RADIUS + 1):
            column, row = shaftColumn + columnOffset, shaftRow + rowOffset
            if math.hypot(columnOffset, rowOffset) <= CLEARING_RADIUS + 0.4 and inBounds(rowLength, rowCount, column, row):
                spot = column + row * rowLength
                openUp(grid, spot)
                works.clearing.add(spot)
    digTunnels(grid, rowLength, rowCount, shaftColumn, shaftRow)
    buildStorehouses(grid, rowLength, rowCount, shaftColumn, shaftRow, works)
    grid[shaftSpot] = [metropolis.MINESHAFT, 1, metropolis.Mineshaft(kind, down=False)]
    hangLamps(grid, rowLength, works)
    placeDwellers(grid, rowLength, shaftSpot, kind, works)
    return works


def digTunnels(grid, rowLength, rowCount, shaftColumn, shaftRow):
    """Tunnels straight out of the clearing (up, down, left and right), three tiles wide, until each reaches open
    cave (or TUNNEL_REACH, or the edge of the map)."""
    for stepColumn, stepRow in ((0, -1), (0, 1), (-1, 0), (1, 0))[:TUNNELS]:
        for distance in range(CLEARING_RADIUS + 1, CLEARING_RADIUS + 1 + TUNNEL_REACH):
            column, row = shaftColumn + stepColumn * distance, shaftRow + stepRow * distance
            if not inBounds(rowLength, rowCount, column, row):
                break
            spot = column + row * rowLength
            reachedCave = grid[spot][0] == FLOOR and distance > CLEARING_RADIUS + 2
            for width in (-1, 0, 1):
                sideColumn, sideRow = column + stepRow * width, row + stepColumn * width
                if inBounds(rowLength, rowCount, sideColumn, sideRow) and grid[sideColumn + sideRow * rowLength][0] != FLOOR:
                    openUp(grid, sideColumn + sideRow * rowLength)
            if reachedCave:
                break


def buildStorehouses(grid, rowLength, rowCount, shaftColumn, shaftRow, works):
    """STOREHOUSES storehouses just off the clearing (on the diagonals, clear of the tunnels), each with its door
    toward the shaft and its chests inside."""
    half = STOREHOUSE_SIZE // 2
    reach = CLEARING_RADIUS + half - 1
    corners = [(1, 1), (-1, 1), (1, -1), (-1, -1)]
    random.shuffle(corners)
    for stepColumn, stepRow in corners:
        if len(works.storehouses) >= STOREHOUSES:
            break
        middleColumn, middleRow = shaftColumn + stepColumn * reach, shaftRow + stepRow * reach
        if not inBounds(rowLength, rowCount, middleColumn - half, middleRow - half) or \
                not inBounds(rowLength, rowCount, middleColumn + half, middleRow + half):
            continue
        walls, inside = set(), set()
        for rowOffset in range(-half, half + 1):
            for columnOffset in range(-half, half + 1):
                spot = middleColumn + columnOffset + (middleRow + rowOffset) * rowLength
                (walls if max(abs(columnOffset), abs(rowOffset)) == half else inside).add(spot)
        # the door: in the side toward the shaft (the one the clearing is on)
        door = middleColumn + (middleRow - stepRow * half) * rowLength
        for spot in walls:
            grid[spot] = [WALL, 0, wall.ShopWall()]
        for spot in inside | {door}:
            openUp(grid, spot)
        outside = door - stepRow * rowLength
        while outside not in works.clearing and grid.get(outside, [FLOOR])[0] != FLOOR:  # a step out to the clearing
            openUp(grid, outside)
            outside -= stepRow * rowLength
        backRow = [middleColumn + columnOffset + (middleRow + stepRow * (half - 1)) * rowLength for columnOffset in (-1, 1)]
        chests = backRow[:STOREHOUSE_CHESTS]
        for spot in chests:
            grid[spot] = [CHEST, 0, items.StorageChest()]
        works.storehouses.append({"walls": walls, "inside": inside, "door": door, "chests": chests})
        works.clearing -= walls | inside


def sideOfWall(grid, rowLength, spot):
    """Which side of floor tile spot has a wall, or None."""
    for side, (stepColumn, stepRow) in metropolis.SIDES.items():
        near = spot + stepColumn + stepRow * rowLength
        if near in grid and grid[near][0] == WALL and (near // rowLength == spot // rowLength or stepRow):
            return side
    return None


def hangLamps(grid, rowLength, works):
    """A lamp in each storehouse (on its back wall) and lamps round the edge of the clearing."""
    for storehouse in works.storehouses:
        for spot in sorted(storehouse["inside"]):
            side = sideOfWall(grid, rowLength, spot)
            if grid[spot][0] == FLOOR and side is not None and spot not in tilesBeside(rowLength, storehouse["door"]):
                works.lamps[spot] = metropolis.WallLamp(side, metropolis.ROOM_LAMP_RADIUS)
                break
    placed = []
    for spot in sorted(works.clearing):
        side = sideOfWall(grid, rowLength, spot)
        if side is None or grid[spot][0] != FLOOR:
            continue
        if all(abs(spot % rowLength - other % rowLength) + abs(spot // rowLength - other // rowLength) >= metropolis.WALL_LAMP_SPACING
               for other in placed):
            works.lamps[spot] = metropolis.WallLamp(side, LAMP_RADIUS)
            placed.append(spot)


def tilesBeside(rowLength, spot):
    """The four tiles beside spot (up, down, left, right)."""
    return {spot - 1, spot + 1, spot - rowLength, spot + rowLength}


def placeDwellers(grid, rowLength, shaftSpot, kind, works):
    """The workers (citizens, at work on this floor) and the guards, on the clearing. Everyone's home is the
    clearing; a guard's post is a spot on its edge."""
    free = [spot for spot in sorted(works.clearing) if grid[spot][0] == FLOOR and spot != shaftSpot
            and spot not in tilesBeside(rowLength, shaftSpot)]
    random.shuffle(free)
    for _ in range(random.randint(*GUARDS)):
        if not free:
            break
        guard = enemies.DwellerGuard()
        guard.home = free.pop()
        works.dwellers[guard.home] = guard
    for _ in range(random.randint(*WORKERS[kind])):
        if not free:
            break
        worker = enemies.DwellerCitizen()
        spot = free.pop()
        worker.home = spot
        worker.work = kind
        works.dwellers[spot] = worker
