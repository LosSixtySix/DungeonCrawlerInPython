import copy
import math
import random

from cruel.entities import enemies
from cruel.inventory import items
from cruel.inventory import resources
from cruel.world import events
from cruel.world import farmhouses
from cruel.world import metropolis
from cruel.world import plants
from cruel.world import wall

"""
The Metropolis's works: its mine and its farm (metropolis.WORKS). Each is a building in the city with a mineshaft in
the middle (a metropolis.MINESHAFT tile). Stand on it and press Enter to climb down to the floor it works; climb the
shaft you arrive on to go back up.

  Mine   a Motherlode ore floor (a random ore floor for this depth, wall.ORE_FLOORS, with most of its walls ore).
  Farm   a Mixed cave floor with PENS pens of Dew Grubs (fenced, with a gate toward the shaft and another on the far side) and FARMHOUSES farmhouses (farmhouses.py: round, with plots of
         the city's crops (plants.Plant with cityCrop: picking one is stealing), which its farmers tend.

Both have, round the shaft: a clearing (CLEARING_RADIUS), tunnels out of it to the caves, and STOREHOUSES
storehouses, each with two doors (one toward the shaft, one in the far wall) and STOREHOUSE_CHESTS chests
(items.StorageChest) where the workers put what they bring in. Wall lamps light the clearing and the storehouses. WORKERS Dweller citizens work the floor and
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
PENS = (2, 3)
PEN_WIDTH, PEN_HEIGHT = 7, 6   # a pen's size, fence and all
PEN_REACH = (9, 16)         # how far from the shaft a pen's middle is
GRUBS_PER_PEN = (2, 3)
FARMER_START_FOOD = 3       # herbs of each crop a keeper starts with (so the grubs don't starve before the first harvest)
FARMER_START_SEEDS = 2      # seeds of its crop a grower starts with
CHEST_START_FOOD = 8        # herbs of each crop in a farm's storehouse chests to begin with
FARMHOUSES = 2
CLEARANCE = 2               # every building has this much open ground round it: no other building this close, and
#                             the rock this close dug out (clearAround), so nothing blocks its doors
FARMHOUSE_REACH = (10, 17)  # how far from the shaft a farmhouse's middle is
FLOOR, WALL, CHEST, ENEMY, PLANT = 0, 2, 3, 5, 8

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


def fallOff(game):
    """You're falling through a hole in a works floor: the works floor is put aside and the city is put back (with
    you where you fell), so the fall goes on from the city's floor to the one below it."""
    shaftSpot = game.sideFloor[1]
    game.saveLevel()
    game.floorsAside[(game.level, shaftSpot)] = putAside(game)
    putBack(game, game.cityAside)
    game.cityAside = None
    game.sideFloor = None
    game.currentLocation = copy.copy(game.grid[game.playerPositionFlat])  # (saving the city leaves its tile as it was)


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
        oreFloors = [name for name, oreFloor in wall.ORE_FLOORS.items() if oreFloor["first"] <= level]
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
    works = layOutWorks(game.grid, game.rowLength, shaftSpot, kind, game.rooms)
    game.wallLamps[level] = works.lamps
    for spot, dweller in works.dwellers.items():
        game.grid[spot] = [ENEMY, 0, dweller]
        game.EnemyPositions.add(spot)
    event = events.roll(level)
    if event:
        game.floorEvents[level] = event
    game.levelGrids[level] = None  # (saveLevel fills it in when you leave)


class Works:
    """What layOutWorks built: the clearing, its tunnels, the storehouses (each {"walls", "inside", "door",
    "backDoor", "chests"}), a farm's pens (each {"fence", "inside", "gate", "backGate"}) and fields ({tile: plant kind}, shared by its
    farmers), the wall lamps ({tile: metropolis.WallLamp}) and the Dwellers ({tile: Dweller})."""

    def __init__(self):
        self.clearing = set()
        self.tunnels = set()
        self.storehouses = []
        self.pens = []
        self.farmhouses = []  # each {"walls", "inside", "door", "backDoor", "beds", "chest", "crop"}
        self.fields = {}
        self.lamps = {}
        self.ways = set()   # the ways dug from the buildings' doors out to open ground (kept clear)
        self.dwellers = {}
        self.plans = []     # buildings the workers are putting up (dwellerbuilding.py), shared by them

    def builtOn(self):
        """Every tile the works use (nothing else goes there)."""
        tiles = self.clearing | self.tunnels | self.ways
        for storehouse in self.storehouses:
            tiles |= storehouse["walls"] | storehouse["inside"]
        for pen in self.pens:
            tiles |= pen["fence"] | pen["inside"]
        for farmhouse in self.farmhouses:
            tiles |= farmhouse["box"]
        return tiles


def clearAround(grid, rowLength, box, works):
    """Digs out the rock (cave walls and veins) within CLEARANCE of a building's box, leaving everything the works
    use (other buildings, ways) as it is."""
    rowCount = len(grid) // rowLength
    keep = works.builtOn() | set(box)
    columns = [spot % rowLength for spot in box]
    rows = [spot // rowLength for spot in box]
    for row in range(min(rows) - CLEARANCE, max(rows) + CLEARANCE + 1):
        for column in range(min(columns) - CLEARANCE, max(columns) + CLEARANCE + 1):
            spot = column + row * rowLength
            if not inBounds(rowLength, rowCount, column, row) or spot in keep:
                continue
            tile = grid[spot]
            if tile[0] == WALL and not (len(tile) > 2 and isinstance(tile[2], wall.CityBuildingWall)):
                openUp(grid, spot)


def withClearance(rowLength, left, top, width, height):
    """A box's tiles and every tile within CLEARANCE of it."""
    return {column + row * rowLength for row in range(top - CLEARANCE, top + height + CLEARANCE)
            for column in range(left - CLEARANCE, left + width + CLEARANCE)}


def inBounds(rowLength, rowCount, column, row, margin=1):
    return margin <= column < rowLength - margin and margin <= row < rowCount - margin


def openUp(grid, spot):
    """Makes spot open floor (whatever was there goes)."""
    grid[spot] = [FLOOR, grid[spot][1] if spot in grid else 0]


def layOutWorks(grid, rowLength, shaftSpot, kind, rooms=None):
    """Builds the works round the shaft on a new floor: the shaft up, the clearing, its tunnels, the storehouses, a
    farm's pens and fields, the lamps and the Dwellers. rooms: the floor's rooms (what grows where). Returns a
    Works."""
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
    works.tunnels = digTunnels(grid, rowLength, rowCount, shaftColumn, shaftRow)
    buildStorehouses(grid, rowLength, rowCount, shaftColumn, shaftRow, works)
    grid[shaftSpot] = [metropolis.MINESHAFT, 1, metropolis.Mineshaft(kind, down=False)]
    if kind == "farm":
        buildPens(grid, rowLength, rowCount, shaftSpot, works)
        buildFarmhouses(grid, rowLength, rowCount, shaftSpot, works, rooms if rooms is not None else {})
        for storehouse in works.storehouses:  # some food put by
            for materialId, amount in startingStock(works, CHEST_START_FOOD, 0).items():
                if amount:
                    grid[storehouse["chests"][0]][2].append(resources.MaterialStack(materialId, amount))
    hangLamps(grid, rowLength, works)
    placeDwellers(grid, rowLength, shaftSpot, kind, works)
    return works


def digTunnels(grid, rowLength, rowCount, shaftColumn, shaftRow):
    """Tunnels straight out of the clearing (up, down, left and right), three tiles wide, until each reaches open
    cave (or TUNNEL_REACH, or the edge of the map). Returns their tiles."""
    tunnels = set()
    for stepColumn, stepRow in ((0, -1), (0, 1), (-1, 0), (1, 0))[:TUNNELS]:
        for distance in range(CLEARING_RADIUS + 1, CLEARING_RADIUS + 1 + TUNNEL_REACH):
            column, row = shaftColumn + stepColumn * distance, shaftRow + stepRow * distance
            if not inBounds(rowLength, rowCount, column, row):
                break
            spot = column + row * rowLength
            reachedCave = grid[spot][0] == FLOOR and distance > CLEARING_RADIUS + 2
            for width in (-1, 0, 1):
                sideColumn, sideRow = column + stepRow * width, row + stepColumn * width
                if inBounds(rowLength, rowCount, sideColumn, sideRow):
                    tunnels.add(sideColumn + sideRow * rowLength)
                    if grid[sideColumn + sideRow * rowLength][0] != FLOOR:
                        openUp(grid, sideColumn + sideRow * rowLength)
            if reachedCave:
                break
    return tunnels


def buildStorehouses(grid, rowLength, rowCount, shaftColumn, shaftRow, works):
    """STOREHOUSES storehouses just off the clearing (on the diagonals, clear of the tunnels), each with its door
    toward the shaft, a back door in the far wall (with a way dug from it to ground you can walk to from the shaft)
    and its chests inside."""
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
        backDoor = middleColumn + (middleRow + stepRow * half) * rowLength
        openUp(grid, backDoor)
        walls.discard(backDoor)
        storehouse = {"walls": walls, "inside": inside, "door": door, "backDoor": backDoor, "chests": chests}
        works.storehouses.append(storehouse)
        works.clearing -= walls | inside
        clearAround(grid, rowLength, walls | inside | {door, backDoor}, works)
        works.ways |= digWayOut(grid, rowLength, backDoor + stepRow * rowLength, shaftColumn + shaftRow * rowLength,
                                works.builtOn(), walls | inside | {door, backDoor})


def digWayOut(grid, rowLength, start, shaftSpot, keepOff, building):
    """Opens start (the step outside a door) and the shortest way from it to ground you can walk to from the shaft
    without going through building (its tiles), round keepOff. Returns the tiles of the way."""
    openUp(grid, start)
    connected = walkable(grid, rowLength, shaftSpot, avoid=building) | {shaftSpot}
    way = {start} | set(pathOut(grid, rowLength, start, connected, keepOff | building))
    for spot in way:
        openUp(grid, spot)
    return way


def walkable(grid, rowLength, start, avoid=()):
    """Every open floor tile you can walk to from start (over open floor, not through avoid)."""
    reached, frontier = {start}, [start]
    while frontier:
        spot = frontier.pop()
        for near in tilesBeside(rowLength, spot):
            if near in grid and near not in reached and near not in avoid and grid[near][0] == FLOOR and \
                    (near // rowLength == spot // rowLength or near % rowLength == spot % rowLength):
                reached.add(near)
                frontier.append(near)
    return reached


def pathOut(grid, rowLength, start, connected, keepOff):
    """The shortest way (through rock or not, but round keepOff) from start to ground in connected: the tiles to
    open up. Empty if start is already there."""
    cameFrom, frontier = {start: None}, [start]
    while frontier:
        nextFrontier = []
        for spot in frontier:
            if spot in connected:
                path, step = [], cameFrom[spot]
                while step is not None:
                    path.append(step)
                    step = cameFrom[step]
                return path
            for near in tilesBeside(rowLength, spot):
                if near in grid and near not in cameFrom and (near not in keepOff or near in connected) and \
                        (near // rowLength == spot // rowLength or near % rowLength == spot % rowLength):
                    cameFrom[near] = spot
                    nextFrontier.append(near)
        frontier = nextFrontier
    return []


def buildPens(grid, rowLength, rowCount, shaftSpot, works):
    """PENS fenced pens round the clearing, clear of everything else, each with a gate in the side toward the
    shaft and a back gate in the far side (each with a path from it to ground you can walk to from the shaft), and
    GRUBS_PER_PEN Dew Grubs inside."""
    shaftColumn, shaftRow = shaftSpot % rowLength, shaftSpot // rowLength
    wanted = random.randint(*PENS)
    angles = [math.tau * index / 12 for index in range(12)]
    random.shuffle(angles)
    for angle in angles:
        if len(works.pens) >= wanted:
            break
        reach = random.randint(*PEN_REACH)
        left = round(shaftColumn + reach * math.cos(angle)) - PEN_WIDTH // 2
        top = round(shaftRow + reach * math.sin(angle)) - PEN_HEIGHT // 2
        if not (inBounds(rowLength, rowCount, left - CLEARANCE, top - CLEARANCE, margin=1) and
                inBounds(rowLength, rowCount, left + PEN_WIDTH - 1 + CLEARANCE, top + PEN_HEIGHT - 1 + CLEARANCE, margin=1)):
            continue
        box = {column + row * rowLength for row in range(top, top + PEN_HEIGHT) for column in range(left, left + PEN_WIDTH)}
        if withClearance(rowLength, left, top, PEN_WIDTH, PEN_HEIGHT) & works.builtOn():
            continue
        fence = {spot for spot in box if spot % rowLength in (left, left + PEN_WIDTH - 1) or spot // rowLength in (top, top + PEN_HEIGHT - 1)}
        inside = box - fence
        middleColumn, middleRow = left + PEN_WIDTH // 2, top + PEN_HEIGHT // 2
        # the gate: the middle of the side that faces the shaft most
        if abs(shaftColumn - middleColumn) > abs(shaftRow - middleRow):
            gateColumn = left if shaftColumn < middleColumn else left + PEN_WIDTH - 1
            gate, step = gateColumn + middleRow * rowLength, (-1 if shaftColumn < middleColumn else 1)
            backGate = (left + PEN_WIDTH - 1 if gateColumn == left else left) + middleRow * rowLength
        else:
            gateRow = top if shaftRow < middleRow else top + PEN_HEIGHT - 1
            gate, step = middleColumn + gateRow * rowLength, (-rowLength if shaftRow < middleRow else rowLength)
            backGate = middleColumn + (top + PEN_HEIGHT - 1 if gateRow == top else top) * rowLength
        for spot in fence - {gate, backGate}:
            grid[spot] = [WALL, 0, wall.PenFence()]
        for spot in inside | {gate, backGate}:
            openUp(grid, spot)
        for doorway, outward in ((gate, step), (backGate, -step)):
            works.ways |= digWayOut(grid, rowLength, doorway + outward, shaftSpot, works.builtOn(), box)
        inside = frozenset(inside)
        pen = {"fence": fence, "inside": inside, "gate": gate, "backGate": backGate}
        works.pens.append(pen)
        clearAround(grid, rowLength, box, works)
        spots = sorted(inside - {gate + step * -1})
        random.shuffle(spots)
        for spot in spots[:random.randint(*GRUBS_PER_PEN)]:
            grub = enemies.DewGrub()
            grub.pen = frozenset(inside)
            grub.home = spot
            works.dwellers[spot] = grub


def buildFarmhouses(grid, rowLength, rowCount, shaftSpot, works, rooms):
    """FARMHOUSES farmhouses (farmhouses.py) round the clearing, clear of everything else, each with its two doors
    (each with a way from it to ground you can walk to from the shaft), a storage chest in the middle, its floor laid
    for its crop and its plots already growing (wild patches' stages)."""
    shaftColumn, shaftRow = shaftSpot % rowLength, shaftSpot // rowLength
    tries = [(math.tau * index / 16, reach) for index in range(16) for reach in range(FARMHOUSE_REACH[0], FARMHOUSE_REACH[1] + 1)]
    random.shuffle(tries)
    for angle, reach in tries:
        if len(works.farmhouses) >= FARMHOUSES:
            break
        middleColumn, middleRow = round(shaftColumn + reach * math.cos(angle)), round(shaftRow + reach * math.sin(angle))
        half = farmhouses.HALF
        if not (inBounds(rowLength, rowCount, middleColumn - half - CLEARANCE, middleRow - half - CLEARANCE) and
                inBounds(rowLength, rowCount, middleColumn + half + CLEARANCE, middleRow + half + CLEARANCE)):
            continue
        farmhouse = farmhouses.shape(rowLength, middleColumn, middleRow, (shaftColumn, shaftRow))
        if withClearance(rowLength, middleColumn - half, middleRow - half, 2 * half + 1, 2 * half + 1) & works.builtOn():
            continue
        crop = farmhouses.pickCrop(works.fields)
        for spot in farmhouse["walls"]:
            grid[spot] = [WALL, 0, wall.FarmhouseWall()]
        for spot in farmhouse["inside"] | {farmhouse["door"], farmhouse["backDoor"]}:
            openUp(grid, spot)
        grid[farmhouse["chest"]] = [CHEST, 0, items.StorageChest()]
        farmhouses.layFloor(rooms, farmhouse["inside"], crop)
        for bed in farmhouse["beds"]:
            sprout = plants.Plant.grown(crop)
            sprout.planted = sprout.cityCrop = True
            grid[bed] = [PLANT, 0, sprout]
            works.fields[bed] = crop
        farmhouse["crop"] = crop
        works.farmhouses.append(farmhouse)
        clearAround(grid, rowLength, farmhouse["box"], works)
        for outside in (farmhouse["outside"], farmhouse["backOutside"]):
            works.ways |= digWayOut(grid, rowLength, outside, shaftSpot, works.builtOn(), farmhouse["box"])


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


def startingStock(works, food, seeds):
    """{id: amount}: food herbs and seeds of each of the farm's crops (a farmer's pockets, or a chest)."""
    stock = {}
    for cropKind in sorted(set(works.fields.values())):
        stock[plants.PLANTS[cropKind]["herb"]] = food
        stock[plants.PLANTS[cropKind]["seed"]] = seeds
    return stock


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
        worker.plans = works.plans  # (one list, shared by every worker)
        if kind == "farm":
            worker.fields = works.fields  # (one dict, shared by every farmer)
            worker.pens = works.pens      # (and the pens, the same way)
            worker.farmhouses = works.farmhouses
            farmers = sum(1 for dweller in works.dwellers.values() if getattr(dweller, "work", None) == "farm")
            crops = sorted(set(works.fields.values()))
            if farmers % 2 == 0 or not crops:  # every other farmer keeps the grubs; the others grow a crop each
                worker.farmRole = "keeper"
                worker.materials = startingStock(works, FARMER_START_FOOD, 0)
            else:  # (seeds of every crop: which it tends depends on how many growers there are, growerCrops)
                worker.farmRole = "grower"
                worker.materials = startingStock(works, 0, FARMER_START_SEEDS)
        works.dwellers[spot] = worker
