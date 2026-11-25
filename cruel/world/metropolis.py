import functools
import math
import random

from cruel.entities import enemies
from cruel.inventory import items
from cruel.inventory import recipes
from cruel.inventory import resources
from cruel.world import cityshops
from cruel.world import wall

"""
The Metropolis: a floor that is one whole city of insectoid Dwellers (design sheet:
https://claude.ai/artifact/538ySkNBUTYEUnSTVLSHii).

  The city   a ring of City Wall round the floor. Inside it, solid rock (Stone Wall, like any other floor's) with
             the roads carved out of it and the buildings set into it. The roads are a network of random paths: a small round plaza
             somewhere near the middle, a path from where you arrive to it, and paths out to targets spread over the
             floor, each starting from the nearest road so they branch off one another. Each path is either
             "rounded" (it curves smoothly as it goes) or "square" (straight runs with right-angle corners), picked
             at random. Buildings are built along the paths, BUILDING_CLEARANCE apart, with the ground that close
             round each cleared, each in the shape its theme builds (STYLES: hexagons,
             round towers, oblong domes, soft rounded cells or sharp squares), every one with its door facing a road:
             the noble quarter's mansions nearest the plaza first, then the city's works (a mine and a farm, WORKS),
             then SHOP_COUNT shops (each a different kind), then houses. Every building has two doors (its door, facing a
             road, and its back door, as far from it as can be: so a crowd at one door can go round to the other), each
             with a doorstep carved from it to the road, and you can walk to every door from where you arrive. The
             rock left over lines the roads; away from them it's walled at random, like any other floor
             (fillWithRock). A shop's sign sits in
             its wall beside the door. A house has a CHEST_CHANCE of a chest (a CityChest).
  Works      a mine and a farm: buildings with a mineshaft (MINESHAFT) in the middle and a sign by the door. The
             shaft goes down to the floor the city works (mineshafts.py): stand on it and press Enter.
  Lights     wall lamps hang on the walls along the roads (the rock's or a building's) and on the walls inside every building (WallLamp:
             they light round them, and anyone can stand under one without putting it out). Lamp posts stand
             round the plaza.
  Dwellers   citizens walk the roads, nobles stay near their mansions, guards stand at posts spread over the roads,
             merchants keep a shop each (dwellers.py runs their turns, cityshops.py stocks their shops).
  Rooms      the floor's tiles are in the Street (roads, plaza and doorsteps), Yard (the rock between them: dig it
             out and it's Yard ground), House, Shop and Noble rooms (themes.CITY_ROOMS), each drawn in its own theme
             colors. Each is its own floor type for plants (plants.CITY_FLOORS), so they grow in a city too.

You always arrive on a road: one runs from where you stand to the rest of the city.
"""

METROPOLIS = "Metropolis"   # the floor type (gameManager.proportion)
APPEAR_CHANCE = 0.04        # chance a new floor is a city...
FIRST_FLOOR = 4             # ...from this floor down

# Each theme's buildings (by theme name, themes.THEMES["Metropolis"]); a theme not listed builds DEFAULT_STYLE
STYLES = {"Amber Hive": "hexagon", "Chitin Spires": "round", "Verdigris Bazaar": "oblong",
          "Pale Wax Warrens": "rounded", "Obsidian Court": "square"}
DEFAULT_STYLE = "square"
BUILDING_STYLES = ("hexagon", "round", "oblong", "rounded", "square")

# The roads
PATH_TARGETS = (10, 14)     # paths out to this many targets spread over the floor (plus the one from where you arrive)
PATH_STYLES = ("rounded", "square")  # each path is one or the other, at random
ROUNDED_TURN = (0.025, 0.05) # a rounded path turns toward its target at most this much (radians) each half tile...
ROUNDED_SWERVE = 1.3        # ...and sets off this far (radians, at least half of it) off the straight line, so it arcs
SQUARE_JOGS = (1, 3)        # a square path runs in this many straight legs (with right-angle corners between)
PLAZA_RADIUS = 5
PLAZA_AREA = 0.25           # the plaza is within this share of the floor's size of its middle

# The buildings (sizes: the box a building's shape fills, in tiles)
HOUSE_SIZE = (5, 8)
SHOP_SIZE = (9, 11)
MANSION_SIZE = (10, 13)
MANSIONS = (2, 4)
BUILDING_CLEARANCE = 2      # buildings stand this far apart, the ground this close round each cleared of rock
ROCK_DENSITIES = [round(0.15 + 0.05 * step, 2) for step in range(13)]  # (gameManager.WALL_DENSITIES: any floor's)
HOUSE_PASSES = 3            # times the land is gone over for room for another house
SHOP_COUNT = (3, 5)         # never more than 5 shops, each a different kind
ROUNDED_CORNER = 0.8        # how much a "rounded" building's corners are cut (smaller: rounder)
OBLONG_STRETCH = 1.6        # an oblong building is this many times longer one way than the other
CHEST_CHANCE = 0.30         # a house has a chest this often
NOBLE_CHEST_CHANCE = 0.6
CHEST_THINGS = (1, 3)       # things in a house chest

# The Dwellers on a floor
CITIZENS = (20, 30)
NOBLES = (3, 6)
GUARD_POSTS = (6, 10)
NOBLES_ON_THE_PLAZA = 2

# The lights
WALL_LAMP_SPACING = 6       # outside wall lamps along the roads, at least this far apart
WALL_LAMP_RADIUS = 5        # how far an outside wall lamp lights
ROOM_LAMP_RADIUS = 3        # how far a lamp inside a building lights
PLAZA_LAMPS = 6             # lamp posts round the plaza
STREET_LIGHT_RADIUS = 5     # how far a lamp post lights

STREET, YARD, HOUSE, SHOP, NOBLE = "Street", "Yard", "House", "Shop", "Noble"  # Street: the roads, the plaza and
# the doorsteps. Yard: the rock between the roads and the buildings (and the ground left where it's dug out).
SHOP_SIGN = 14              # grid tile type of a shop's sign (its object: the shop kind, cityshops.SHOP_KINDS, or a works kind)
STREET_LIGHT = 15           # grid tile type of a lamp post: it lights round it and blocks the way
MINESHAFT = 16              # grid tile type of a mineshaft (its object: a Mineshaft): you can stand on it and climb it
WORKS = {"mine": "Dweller Mine", "farm": "Dew Farm"}  # the works every city has: kind -> its sign's name
FLOOR, WALL, CHEST, ENEMY = 0, 2, 3, 5
SIDES = {"up": (0, -1), "down": (0, 1), "left": (-1, 0), "right": (1, 0)}


CityChest = items.CityChest  # a chest that belongs to the city: taking from it is stealing


class Mineshaft:
    """A mineshaft: kind is "mine" or "farm" (the floor it goes to). down: the city's end, going down to it; the
    other end (on that floor) goes back up."""

    def __init__(self, kind, down=True):
        self.kind = kind
        self.down = down

    @property
    def name(self):
        return f"Mineshaft {'down to the' if self.down else 'up from the'} {WORKS[self.kind]}"


def signName(kind):
    """What a sign by a door says: a works' name, or a shop's."""
    return WORKS[kind] if kind in WORKS else cityshops.shopName(kind)


class Building:
    """A building of the city: its kind ("house", "shop", "mansion", or a works kind: "mine" or "farm"), the tiles
    of its walls and inside, its door and its back door."""

    def __init__(self, kind, walls, inside, door, backDoor=None):
        self.kind = kind
        self.walls = walls
        self.inside = inside
        self.door = door
        self.backDoor = backDoor

    @property
    def doors(self):
        return [self.door] + ([self.backDoor] if self.backDoor is not None else [])

    @property
    def tiles(self):
        """Every tile of the building: its walls, its inside and its doors."""
        return self.walls | self.inside | set(self.doors)
        self.center = None      # the inside tile nearest its middle (a shop's counter)
        self.shopKind = None    # a shop: cityshops.SHOP_KINDS
        self.sign = None        # a shop or works: where its sign is (in its wall beside the door)
        self.shaft = None       # a works: where its mineshaft is (in its middle)


class City:
    """A city laid out on a grid: what the floor generator returns, plus where everything is."""

    def __init__(self, grid, rowLength, style):
        self.grid = grid
        self.rowLength = rowLength
        self.rowCount = len(grid) // rowLength
        self.style = style
        self.rooms = {room: set() for room in ("Stone", "Wood", "Sand", "Gold", "Molten", STREET, YARD, HOUSE, SHOP, NOBLE)}
        self.roads = set()
        self.paths = []             # (style, tiles) for each path laid: "rounded" or "square"
        self.plaza = set()
        self.plazaCenter = None
        self.buildings = []
        self.posts = []             # guard posts, spread over the roads
        self.wallLamps = {}         # tile: WallLamp
        self.dwellers = {}          # tile: Dweller
        self.builtCells = set()     # every tile a building stands on (placeBuilding: the next keeps its distance)

    def spot(self, column, row):
        return column + row * self.rowLength

    def inside(self, column, row):
        """Is (column, row) within the city wall?"""
        return 1 <= column < self.rowLength - 1 and 1 <= row < self.rowCount - 1

    @property
    def houses(self):
        return [(building.inside, building.door) for building in self.buildings if building.kind == "house"]

    @property
    def mansions(self):
        return [(building.inside, building.door) for building in self.buildings if building.kind == "mansion"]

    @property
    def works(self):
        """{kind: Building} for the city's mine and farm."""
        return {building.kind: building for building in self.buildings if building.kind in WORKS}

    @property
    def shops(self):
        return [{"inside": building.inside, "door": building.door, "counter": building.center, "kind": building.shopKind,
                 "sign": building.sign} for building in self.buildings if building.kind == "shop"]


class WallLamp:
    """A lamp hung on a wall, lighting the floor tile in front of it and round it. side: which side of that tile the
    wall is on ("up", "down", "left" or "right"). It's not a tile of its own, so anyone can stand under it."""

    def __init__(self, side, radius):
        self.side = side
        self.radius = radius


def neighborsOf(city, spot):
    rowLength = city.rowLength
    out = []
    for other in (spot - 1, spot + 1, spot - rowLength, spot + rowLength):
        if other in city.grid and (abs(other - spot) != 1 or other // rowLength == spot // rowLength):
            out.append(other)
    return out


# ---------------------------------------------------------------- building shapes

@functools.lru_cache(maxsize=None)
def shapeCells(style, width, height):
    """The cells a building of this style covers in a width x height box, as (column, row) offsets from its top-left.
    hexagon: pointed at its left and right ends. round and oblong: an ellipse (oblong boxes are stretched one way).
    rounded: a box with well-rounded corners. square: the whole box."""
    cells = set()
    for row in range(height):
        for column in range(width):
            across = (column + 0.5 - width / 2) / (width / 2)  # -1 at the left edge, 1 at the right
            down = (row + 0.5 - height / 2) / (height / 2)
            if style == "hexagon":
                fits = abs(across) + abs(down) / 2 <= 1.0
            elif style in ("round", "oblong"):
                fits = across ** 2 + down ** 2 <= 1.0
            elif style == "rounded":
                fits = across ** 4 + down ** 4 <= ROUNDED_CORNER  # (below 1, so even a small house loses its corners)
            else:
                fits = True
            if fits:
                cells.add((column, row))
    return frozenset(cells)  # (frozen: it's shared, worked out once per style and size)


def buildingSize(style, sizeRange):
    """(width, height) for a building of this style: round ones are as wide as they're tall, oblong ones are
    stretched one way, the others a little uneven."""
    size = random.randint(*sizeRange)
    if style == "round":
        return size, size
    if style == "oblong":
        long = max(size, round(size * OBLONG_STRETCH))
        return (long, size) if random.random() < 0.5 else (size, long)
    if style == "hexagon":
        return size + size // 3, size  # a little wider than it's tall, so its points show
    return size, max(HOUSE_SIZE[0], size + random.randint(-2, 2))


@functools.lru_cache(maxsize=None)
def outlineOf(cells):
    """The cells of a shape with a neighbor outside it: its walls. The rest is its inside."""
    return frozenset((column, row) for column, row in cells
                     if any((column + stepColumn, row + stepRow) not in cells for stepColumn, stepRow in SIDES.values()))


# ---------------------------------------------------------------- roads

def stampRoad(city, column, row):
    """Paves a road three tiles wide (a plus shape) round (column, row)."""
    column, row = round(column), round(row)
    for stepColumn, stepRow in ((0, 0), (1, 0), (-1, 0), (0, 1), (0, -1)):
        if city.inside(column + stepColumn, row + stepRow):
            city.roads.add(city.spot(column + stepColumn, row + stepRow))


def roundedPath(city, start, end):
    """A path that curves from start to end ((column, row) points): it sets off at an angle to the straight line
    and keeps turning toward end, a little each half tile (more as it gets close), so it sweeps round in an arc.
    Returns its points."""
    column, row = start
    heading = math.atan2(end[1] - row, end[0] - column) + random.choice((-1, 1)) * random.uniform(ROUNDED_SWERVE / 2, ROUNDED_SWERVE)
    turnRate = random.uniform(*ROUNDED_TURN)
    points = [(column, row)]
    for _ in range(4 * (city.rowLength + city.rowCount)):  # (a guard: it always gets there long before this)
        if math.hypot(end[0] - column, end[1] - row) <= 1:
            break
        wanted = math.atan2(end[1] - row, end[0] - column)
        turn = (wanted - heading + math.pi) % math.tau - math.pi
        # it turns gently while it's far off and harder as it closes in, so it arrives instead of circling its end
        mostTurn = max(turnRate, 1.0 / math.hypot(end[0] - column, end[1] - row))
        heading += max(-mostTurn, min(mostTurn, turn))
        column = min(city.rowLength - 2, max(1, column + 0.5 * math.cos(heading)))
        row = min(city.rowCount - 2, max(1, row + 0.5 * math.sin(heading)))
        points.append((column, row))
    points.append(end)
    return points


def squarePath(city, start, end):
    """A path of straight runs with right-angle corners from start to end: a few legs, turning at random points
    along the way. Returns its points."""
    corners = [start]
    column, row = start
    legs = random.randint(*SQUARE_JOGS)
    for leg in range(legs):
        if leg == legs - 1:
            target = end
        else:  # partway there, at a random point
            share = (leg + 1) / legs
            target = (round(start[0] + (end[0] - start[0]) * share + random.randint(-4, 4)),
                      round(start[1] + (end[1] - start[1]) * share + random.randint(-4, 4)))
        if random.random() < 0.5:
            corners += [(target[0], row), target]
        else:
            corners += [(column, target[1]), target]
        column, row = target
    points = []
    for (fromColumn, fromRow), (toColumn, toRow) in zip(corners, corners[1:]):
        steps = max(abs(toColumn - fromColumn), abs(toRow - fromRow), 1)
        points += [(fromColumn + (toColumn - fromColumn) * step / steps, fromRow + (toRow - fromRow) * step / steps)
                   for step in range(steps + 1)]
    return points


def nearestRoad(city, column, row):
    """The (column, row) of the road tile nearest a point."""
    nearest = min(city.roads, key=lambda spot: (spot % city.rowLength - column) ** 2 + (spot // city.rowLength - row) ** 2)
    return nearest % city.rowLength, nearest // city.rowLength


def layPath(city, start, end):
    """Paves one path from start to end, rounded or square at random. Remembers it (city.paths) as its style and
    the tiles it paved."""
    style = random.choice(PATH_STYLES)
    points = roundedPath(city, start, end) if style == "rounded" else squarePath(city, start, end)
    before = set(city.roads)
    for column, row in points:
        stampRoad(city, column, row)
    city.paths.append((style, city.roads - before))


def layRoads(city, playerSpot):
    """A small round plaza somewhere near the middle; a path from where you arrive to it; then paths out to targets
    spread over the floor, each from the nearest road there is (so they branch off one another)."""
    rowLength, rowCount = city.rowLength, city.rowCount
    plazaColumn = round(rowLength / 2 + random.uniform(-PLAZA_AREA, PLAZA_AREA) * rowLength)
    plazaRow = round(rowCount / 2 + random.uniform(-PLAZA_AREA, PLAZA_AREA) * rowCount)
    city.plazaCenter = city.spot(plazaColumn, plazaRow)
    for spot in city.grid:
        if math.hypot(spot % rowLength - plazaColumn, spot // rowLength - plazaRow) <= PLAZA_RADIUS and city.inside(spot % rowLength, spot // rowLength):
            city.plaza.add(spot)
            city.roads.add(spot)
    layPath(city, (playerSpot % rowLength, playerSpot // rowLength), (plazaColumn, plazaRow))
    margin = 6
    spread = [city.spot(column, row) for row in range(margin, rowCount - margin, 3) for column in range(margin, rowLength - margin, 3)]
    for target in spreadOutOnMap(spread, random.randint(*PATH_TARGETS), rowLength):
        targetColumn, targetRow = target % rowLength, target // rowLength
        if target in city.roads:
            continue
        layPath(city, nearestRoad(city, targetColumn, targetRow), (targetColumn, targetRow))


# ---------------------------------------------------------------- buildings

@functools.lru_cache(maxsize=None)
def withMargin(cells, rowLength, reach=1):
    """The tiles a building with these cells needs free (itself and reach tiles all round it), as offsets from its
    top-left tile on a map rowLength wide. (Worked out once per shape.)"""
    steps = range(-reach, reach + 1)
    needed = {(column + stepColumn, row + stepRow) for column, row in cells for stepColumn in steps for stepRow in steps}
    return tuple(column + row * rowLength for column, row in needed)


def fits(city, cells, left, top, taken):
    """Can a building with these cells stand at (left, top), inside the city wall, with a tile of open ground all
    round it (taken: roads and buildings) and no other building within BUILDING_CLEARANCE?"""
    width = max(column for column, _ in cells) + 1
    height = max(row for _, row in cells) + 1
    reach = BUILDING_CLEARANCE
    if not (city.inside(left - reach, top - reach) and city.inside(left + width - 1 + reach, top + height - 1 + reach)):
        return False
    corner = city.spot(left, top)
    if not taken.isdisjoint(corner + offset for offset in withMargin(cells, city.rowLength)):
        return False
    return city.builtCells.isdisjoint(corner + offset for offset in withMargin(cells, city.rowLength, reach))


def doorCells(city, cells, walls, left, top):
    """[(how well it faces a road: 0 onto one, 1 a step from one, 2 not, (column, row))] for every wall cell that
    can be a door: its outside is outside the building and its inside faces the building's inside."""
    found = {}
    for column, row in walls:
        for stepColumn, stepRow in SIDES.values():
            outsideCell = (column + stepColumn, row + stepRow)
            insideCell = (column - stepColumn, row - stepRow)
            if outsideCell in cells or insideCell not in cells or insideCell in walls:
                continue
            outside = city.spot(left + outsideCell[0], top + outsideCell[1])
            facesRoad = 0 if outside in city.roads else 1 if any(near in city.roads for near in neighborsOf(city, outside)) else 2
            found[(column, row)] = min(facesRoad, found.get((column, row), 2))
    return [(facesRoad, cell) for cell, facesRoad in found.items()]


def doorFor(city, cells, walls, left, top):
    """The wall cell that makes the best door: its outside faces a road (or failing that, open ground near one)
    and its inside faces the building's inside. None if no wall cell can be a door."""
    best = None
    for facesRoad, cell in doorCells(city, cells, walls, left, top):
        if best is None or facesRoad < best[0]:
            best = (facesRoad, cell)
    return best[1] if best else None


def backDoorFor(city, cells, walls, left, top, doorCell):
    """The wall cell for a building's back door: one that can be a door, not beside its door, as far from it as can
    be (and, between those, the one facing a road best). None if there's none."""
    best = None
    for facesRoad, cell in doorCells(city, cells, walls, left, top):
        if max(abs(cell[0] - doorCell[0]), abs(cell[1] - doorCell[1])) <= 1:
            continue
        score = (-(abs(cell[0] - doorCell[0]) + abs(cell[1] - doorCell[1])), facesRoad)
        if best is None or score < best[0]:
            best = (score, cell)
    return best[1] if best else None


def placeBuilding(city, kind, sizeRange, candidates, taken, nearRoad=True):
    """Puts one building of kind on the first candidate (left, top) where it fits (and, with nearRoad, its door
    faces a road). Returns the Building, or None."""
    for left, top in candidates:
        width, height = buildingSize(city.style, sizeRange)
        if city.spot(left + width // 2, top + height // 2) in taken:  # (a quick no before the full check)
            continue
        cells = shapeCells(city.style, width, height)
        if not fits(city, cells, left, top, taken):
            continue
        walls = outlineOf(cells)
        if len(cells) - len(walls) < 4:
            continue
        doorCell = doorFor(city, cells, walls, left, top)
        if doorCell is None:
            continue
        backDoorCell = backDoorFor(city, cells, walls, left, top, doorCell)
        if backDoorCell is None:  # (every building has two doors)
            continue
        door = city.spot(left + doorCell[0], top + doorCell[1])
        outsideDoor = [near for near in neighborsOf(city, door) if near not in {city.spot(left + column, top + row) for column, row in cells}]
        if nearRoad and not any(near in city.roads or any(far in city.roads for far in neighborsOf(city, near)) for near in outsideDoor):
            continue
        building = Building(kind, {city.spot(left + column, top + row) for column, row in walls - {doorCell, backDoorCell}},
                            {city.spot(left + column, top + row) for column, row in cells - walls}, door,
                            city.spot(left + backDoorCell[0], top + backDoorCell[1]))
        for column, row in cells:  # (the next building keeps BUILDING_CLEARANCE from it: fits)
            taken.add(city.spot(left + column, top + row))
            city.builtCells.add(city.spot(left + column, top + row))
        middle = (left + width / 2, top + height / 2)
        building.center = min(building.inside, key=lambda spot: math.hypot(spot % city.rowLength + 0.5 - middle[0],
                                                                          spot // city.rowLength + 0.5 - middle[1]))
        city.buildings.append(building)
        return building
    return None


def raiseBuilding(city, building):
    """Puts a placed building on the grid: its walls, its inside floor, its doors, its room."""
    room, wallKind = {"house": (HOUSE, wall.HouseWall), "shop": (SHOP, wall.ShopWall), "mansion": (NOBLE, wall.NobleWall),
                      "mine": (SHOP, wall.ShopWall), "farm": (SHOP, wall.ShopWall)}[building.kind]
    for spot in building.walls:
        city.grid[spot] = [WALL, 0, wallKind()]
    for spot in building.inside | set(building.doors):
        city.grid[spot] = [FLOOR, 0]
    for spot in building.tiles:
        city.rooms[room].add(spot)


def carveDoorstep(city, door, builtOn):
    """Carves the way from a building's door out to the nearest road through the rock (the shortest way round the
    other buildings, builtOn), and makes it part of the roads. (A door always faces a road a step or two away; a
    back door may be further.)"""
    cameFrom, frontier = {door: None}, [door]
    while frontier:
        nextFrontier = []
        for spot in frontier:
            for near in neighborsOf(city, spot):
                if near in cameFrom or near in builtOn or not city.inside(near % city.rowLength, near // city.rowLength):
                    continue
                cameFrom[near] = spot
                if near in city.roads:
                    step = spot
                    while step != door:
                        city.roads.add(step)
                        step = cameFrom[step]
                    return
                nextFrontier.append(near)
        frontier = nextFrontier


def clearedRound(city):
    """The ground within BUILDING_CLEARANCE of every building (not a building itself): kept open."""
    builtOn = set()
    for building in city.buildings:
        builtOn |= building.tiles
    cleared = set()
    reach = BUILDING_CLEARANCE
    for spot in builtOn:
        column, row = spot % city.rowLength, spot // city.rowLength
        for stepRow in range(-reach, reach + 1):
            for stepColumn in range(-reach, reach + 1):
                if city.inside(column + stepColumn, row + stepRow):
                    cleared.add(city.spot(column + stepColumn, row + stepRow))
    return cleared - builtOn


def fillWithRock(city):
    """Every tile inside the city wall that isn't a road, part of a building or the ground cleared round one
    (clearedRound) is rock: rock beside a road (one of the 8 tiles round it) is a Stone Wall, so the roads are
    carved out of it; the rest is walled at random, like any other floor (a density from ROCK_DENSITIES), the
    tiles left open being Yard ground."""
    builtOn = set()
    for building in city.buildings:
        builtOn |= building.tiles
    cleared = clearedRound(city)
    density = random.choice(ROCK_DENSITIES)
    for spot in city.grid:
        column, row = spot % city.rowLength, spot // city.rowLength
        if not city.inside(column, row) or spot in city.roads or spot in builtOn or spot in cleared:
            continue
        besideRoad = any(city.spot(column + stepColumn, row + stepRow) in city.roads
                         for stepColumn in (-1, 0, 1) for stepRow in (-1, 0, 1))
        if besideRoad or random.random() < density:
            city.grid[spot] = [WALL, 0, wall.StoneWall()]
        else:
            city.grid[spot] = [FLOOR, 0]


def removeUnreachable(city, playerSpot):
    """Takes down any building with a door you couldn't walk to from where you arrive (a pocket the packing closed
    in), until every door is reachable. Where it stood turns back to rock."""
    while True:
        reached, frontier = {playerSpot}, [playerSpot]
        while frontier:
            spot = frontier.pop()
            for near in neighborsOf(city, spot):
                if near not in reached and city.grid[near][0] == FLOOR:
                    reached.add(near)
                    frontier.append(near)
        cutOff = [building for building in city.buildings if any(door not in reached for door in building.doors)]
        if not cutOff:
            return
        for building in cutOff:
            city.buildings.remove(building)
            for spot in building.tiles:
                city.grid[spot] = [WALL, 0, wall.StoneWall()]
                for room in (HOUSE, SHOP, NOBLE):
                    city.rooms[room].discard(spot)


def placeBuildings(city, playerSpot):
    """Mansions on the open ground nearest the plaza that's big enough, then the shops, then houses wherever there's
    room along the paths. Every building's door faces a road, with a doorstep carved to it; everything else inside
    the city wall is rock."""
    taken = set(city.roads)
    for near in [playerSpot] + neighborsOf(city, playerSpot):
        taken.add(near)
    middleColumn, middleRow = city.plazaCenter % city.rowLength, city.plazaCenter // city.rowLength
    lattice = [(left, top) for top in range(1, city.rowCount - 2, 2) for left in range(1, city.rowLength - 2, 2)]
    nearestThePlaza = sorted(lattice, key=lambda corner: math.hypot(corner[0] - middleColumn, corner[1] - middleRow))
    for _ in range(random.randint(*MANSIONS)):
        placeBuilding(city, "mansion", MANSION_SIZE, nearestThePlaza, taken)
    shuffled = lattice[:]
    random.shuffle(shuffled)
    for kind in WORKS:  # the works: as big as a shop
        placeBuilding(city, kind, SHOP_SIZE, shuffled, taken)
    shopKinds = random.sample(list(cityshops.SHOP_KINDS), random.randint(*SHOP_COUNT))
    for kind in shopKinds:
        shop = placeBuilding(city, "shop", SHOP_SIZE, shuffled, taken)
        if shop is not None:
            shop.shopKind = kind
    shuffled = [(left, top) for top in range(1, city.rowCount - 2) for left in range(1, city.rowLength - 2)]  # houses: try every spot
    for _ in range(HOUSE_PASSES):  # a few passes, each size tried in turn, so the gaps between buildings fill up
        random.shuffle(shuffled)
        for corner in shuffled:  # (every door faces a road: the city is built along its paths)
            placeBuilding(city, "house", HOUSE_SIZE, [corner], taken)
    builtOn = set()
    for building in city.buildings:
        raiseBuilding(city, building)
        builtOn |= building.tiles
    for building in city.buildings:
        for door in building.doors:
            carveDoorstep(city, door, builtOn)
    fillWithRock(city)
    removeUnreachable(city, playerSpot)
    for building in city.buildings:  # a shop's or works' sign: in its wall beside the door
        if building.kind == "shop" or building.kind in WORKS:
            besideDoor = [near for near in neighborsOf(city, building.door) if near in building.walls]
            if besideDoor:
                building.sign = besideDoor[0]
                city.grid[building.sign] = [SHOP_SIGN, 0, building.shopKind if building.kind == "shop" else building.kind]
        if building.kind in WORKS:  # a works' mineshaft: in its middle
            building.shaft = building.center
            city.grid[building.shaft] = [MINESHAFT, 0, Mineshaft(building.kind)]


# ---------------------------------------------------------------- chests

def houseChest():
    """What's in a house chest: a few things (gear, potions or materials). Never a relic."""
    things = []
    for _ in range(random.randint(*CHEST_THINGS)):
        roll = random.random()
        if roll < 0.35:
            things += items.createRandomStatItems(1)
        elif roll < 0.6:
            potionRecipes = [recipe for recipe in recipes.RECIPES if recipe.kind == "potion" and recipe.amount == 1]
            things.append(random.choice(potionRecipes).makeItem(0, 0))
        else:
            materialId = random.choice(["wood", "stone", "coal", "copper_ore", "iron_ore", "hide", "bone", "meat"])
            things.append(resources.MaterialStack(materialId, random.randint(2, 6)))
    return CityChest(things)


def chestSpotIn(city, building):
    """A tile inside a building for a chest: not just inside a door (the ways in stay open) and not its middle."""
    doorway = {near for door in building.doors for near in neighborsOf(city, door)}
    choices = [spot for spot in building.inside if spot not in doorway and spot != building.center and city.grid[spot][0] == FLOOR]
    return random.choice(choices) if choices else None


def placeChests(city):
    for building in city.buildings:
        chance = {"house": CHEST_CHANCE, "mansion": NOBLE_CHEST_CHANCE}.get(building.kind, 0)
        if random.random() < chance:
            chestSpot = chestSpotIn(city, building)
            if chestSpot is not None:
                city.grid[chestSpot] = [CHEST, 0, houseChest()]


# ---------------------------------------------------------------- lights

def sideOfWall(city, spot, walls):
    """Which side of floor tile spot has a wall of walls (for a lamp hung there), or None."""
    for side, (stepColumn, stepRow) in SIDES.items():
        column, row = spot % city.rowLength + stepColumn, spot // city.rowLength + stepRow
        if city.inside(column, row) and city.spot(column, row) in walls:
            return side
    return None


def inOpenGround(city, spot):
    """Is spot open road with open road all round it (all 8 tiles)? A lamp post only stands on one of those, so it
    never blocks the way anywhere (a doorstep, or a narrow bit of road)."""
    column, row = spot % city.rowLength, spot // city.rowLength
    return all(city.spot(column + stepColumn, row + stepRow) in city.roads
               and city.grid[city.spot(column + stepColumn, row + stepRow)][0] == FLOOR
               for stepColumn in (-1, 0, 1) for stepRow in (-1, 0, 1))


def placeLights(city, playerSpot):
    """Wall lamps along the roads, on the walls that line them (the rock's or a building's), at least
    WALL_LAMP_SPACING apart; wall lamps inside every building (one in a house, two in a shop or mansion); and lamp
    posts round the plaza."""
    doorways = set()
    for building in city.buildings:
        for door in building.doors:
            doorways |= {door, *neighborsOf(city, door)}
    walls = {spot for spot, tile in city.grid.items() if tile[0] == WALL}
    outsideLamps = []
    for spot in sorted(city.roads):
        if spot in doorways or spot == playerSpot or city.grid[spot][0] != FLOOR:
            continue
        side = sideOfWall(city, spot, walls)
        spacedOut = all(abs(spot % city.rowLength - lamp % city.rowLength) + abs(spot // city.rowLength - lamp // city.rowLength)
                        >= WALL_LAMP_SPACING for lamp in outsideLamps)
        if side is not None and spacedOut:
            city.wallLamps[spot] = WallLamp(side, WALL_LAMP_RADIUS)
            outsideLamps.append(spot)
    for building in city.buildings:
        wanted = 1 if building.kind == "house" else 2
        choices = [spot for spot in building.inside if spot not in doorways and spot != building.center
                   and city.grid[spot][0] == FLOOR and sideOfWall(city, spot, building.walls) is not None]
        random.shuffle(choices)
        for spot in choices[:wanted]:
            city.wallLamps[spot] = WallLamp(sideOfWall(city, spot, building.walls), ROOM_LAMP_RADIUS)
    middleColumn, middleRow = city.plazaCenter % city.rowLength, city.plazaCenter // city.rowLength
    for index in range(PLAZA_LAMPS):
        angle = math.tau * index / PLAZA_LAMPS
        spot = city.spot(round(middleColumn + (PLAZA_RADIUS - 1) * math.cos(angle)), round(middleRow + (PLAZA_RADIUS - 1) * math.sin(angle)))
        if spot != playerSpot and spot not in neighborsOf(city, playerSpot) and inOpenGround(city, spot):
            city.grid[spot] = [STREET_LIGHT, 0]


def streetLights(game):
    """Where the lamp posts stand on this floor (worked out once per floor: they never move)."""
    cache = game.__dict__.setdefault("streetLightCache", {})
    key = id(game.grid)
    if key not in cache:
        cache.clear()
        cache[key] = [spot for spot, tile in game.grid.items() if tile[0] == STREET_LIGHT] \
            if game.proportion == METROPOLIS else []
    return cache[key]


def wallLampsHere(game):
    """{tile: WallLamp} for this floor's wall lamps (only a city and its works floors have them)."""
    if game.proportion != METROPOLIS and getattr(game, "sideFloor", None) is None:
        return {}
    return getattr(game, "wallLamps", {}).get(game.level, {})


# ---------------------------------------------------------------- the whole city

def buildCity(rowLength, rowCount, playerSpot, style=DEFAULT_STYLE):
    """A whole city on a rowLength x rowCount floor, its buildings in style (STYLES), with a road where you arrive.
    Returns a City."""
    grid = {spot: [FLOOR, 0] for spot in range(rowLength * rowCount)}
    city = City(grid, rowLength, style)
    for spot in grid:
        column, row = spot % rowLength, spot // rowLength
        if not city.inside(column, row):
            grid[spot] = [WALL, 0, wall.CityWall()]
    layRoads(city, playerSpot)
    placeBuildings(city, playerSpot)
    for spot in grid:  # the roads are Street; the rock round them is Yard
        if city.inside(spot % rowLength, spot // rowLength) and not any(spot in city.rooms[room] for room in (HOUSE, SHOP, NOBLE)):
            city.rooms[STREET if spot in city.roads else YARD].add(spot)
    placeChests(city)
    grid[playerSpot] = [FLOOR, 0]
    placeLights(city, playerSpot)
    placeDwellers(city, playerSpot)
    return city


# ---------------------------------------------------------------- the Dwellers

def openRoad(city, spot, taken):
    return city.grid[spot][0] == FLOOR and spot in city.roads and spot not in taken


def placeDwellers(city, playerSpot):
    """Guards at posts spread over the roads, a merchant at each shop's counter, nobles in their mansions and on the
    plaza, citizens on the roads (each with a house to go home to)."""
    taken = {playerSpot} | set(neighborsOf(city, playerSpot))
    roadSpots = [spot for spot in city.roads if openRoad(city, spot, taken) and spot not in city.plaza]
    rowLength = city.rowLength
    posts = []
    for post in spreadOutOnMap(roadSpots, random.randint(*GUARD_POSTS), rowLength):  # (a few, far apart)
        guard = enemies.DwellerGuard()
        guard.home = post
        city.dwellers[post] = guard
        taken.add(post)
        posts.append(post)
    city.posts = posts

    for building in city.buildings:
        if building.kind == "shop":
            merchant = enemies.DwellerMerchant()
            merchant.home = building.center
            merchant.shopKind = building.shopKind
            merchant.wares = cityshops.rollStock(building.shopKind)
            city.dwellers[building.center] = merchant
            taken.add(building.center)

    nobleSpots = [spot for inside, _ in city.mansions for spot in inside]
    plazaSpots = [spot for spot in city.plaza if city.grid[spot][0] == FLOOR and spot not in taken]
    for index in range(random.randint(*NOBLES)):
        pool = plazaSpots if index < NOBLES_ON_THE_PLAZA and plazaSpots else nobleSpots
        free = [spot for spot in pool if city.grid[spot][0] == FLOOR and spot not in taken]
        if not free:
            continue
        spot = random.choice(free)
        noble = enemies.DwellerNoble()
        noble.home = random.choice(nobleSpots) if nobleSpots else spot
        city.dwellers[spot] = noble
        taken.add(spot)

    roads = [spot for spot in city.roads if openRoad(city, spot, taken)]
    houseInsides = [list(inside) for inside, _ in city.houses if inside]
    for spot in random.sample(roads, min(len(roads), random.randint(*CITIZENS))):
        citizen = enemies.DwellerCitizen()
        citizen.home = random.choice(random.choice(houseInsides)) if houseInsides else spot
        city.dwellers[spot] = citizen
    for spot, dweller in city.dwellers.items():
        city.grid[spot] = [ENEMY, 0, dweller]


def spreadOutOnMap(spots, count, rowLength):
    """count of spots spread as far apart on the map as they can be (each next one the furthest from those already
    picked)."""
    if not spots:
        return []
    distance = lambda spot, other: math.hypot(spot % rowLength - other % rowLength, spot // rowLength - other // rowLength)
    picked = [random.choice(spots)]
    while len(picked) < min(count, len(spots)):
        picked.append(max(spots, key=lambda spot: min(distance(spot, other) for other in picked)))
    return picked
