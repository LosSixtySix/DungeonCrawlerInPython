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

  The city   a ring of City Wall round the floor. Inside it, winding roads: two ring roads round a round plaza in
             the middle, and roads curving out from the plaza like spokes. Buildings are packed into the land
             between the roads, each in the shape its theme builds (STYLES: hexagons, round towers, oblong domes,
             soft rounded cells or sharp squares). The mansions of the noble quarter take the biggest open ground
             nearest the middle, then come SHOP_COUNT shops (each a different kind), then houses everywhere else. Every building has exactly
             one door facing the roads, and you can walk to every door from where you arrive. A shop's sign sits in
             its wall beside the door. A house has a CHEST_CHANCE of a chest (a CityChest).
  Lights     wall lamps hang on the outside walls along the roads and on the walls inside every building (WallLamp:
             they light round them, and anyone can stand under one without putting it out). Lamp posts stand
             round the plaza.
  Dwellers   citizens walk the roads, nobles stay near their mansions, guards stand at posts spread over the roads,
             merchants keep a shop each (dwellers.py runs their turns, cityshops.py stocks their shops).
  Rooms      the floor's tiles are in the Street (roads and plaza), Yard (open ground between buildings), House,
             Shop and Noble rooms (themes.CITY_ROOMS), each drawn in its own theme colors.

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
RING_ROADS = (0.38, 0.72)   # ring roads, as a share of the way from the middle to the city wall
RING_WOBBLE = 0.07          # how much a ring road bends in and out
SPOKE_ROADS = (5, 7)        # roads curving out from the plaza
SPOKE_BEND = 0.5            # how far (in radians) a spoke curves on its way out
PLAZA_RADIUS = 6

# The buildings (sizes: the box a building's shape fills, in tiles)
HOUSE_SIZE = (5, 8)
SHOP_SIZE = (9, 11)
MANSION_SIZE = (10, 13)
MANSIONS = (2, 4)
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

STREET, YARD, HOUSE, SHOP, NOBLE = "Street", "Yard", "House", "Shop", "Noble"  # Street: the roads and the plaza.
# Yard: the rest of the open ground, between the buildings.
SHOP_SIGN = 14              # grid tile type of a shop's sign (its object: the shop kind, cityshops.SHOP_KINDS)
STREET_LIGHT = 15           # grid tile type of a lamp post: it lights round it and blocks the way
FLOOR, WALL, CHEST, ENEMY = 0, 2, 3, 5
SIDES = {"up": (0, -1), "down": (0, 1), "left": (-1, 0), "right": (1, 0)}


CityChest = items.CityChest  # a chest that belongs to the city: taking from it is stealing


class Building:
    """A building of the city: its kind ("house", "shop" or "mansion"), the tiles of its walls and inside, and its door."""

    def __init__(self, kind, walls, inside, door):
        self.kind = kind
        self.walls = walls
        self.inside = inside
        self.door = door
        self.center = None      # the inside tile nearest its middle (a shop's counter)
        self.shopKind = None    # a shop: cityshops.SHOP_KINDS
        self.sign = None        # a shop: where its sign is (in its wall beside the door)


class City:
    """A city laid out on a grid: what the floor generator returns, plus where everything is."""

    def __init__(self, grid, rowLength, style):
        self.grid = grid
        self.rowLength = rowLength
        self.rowCount = len(grid) // rowLength
        self.style = style
        self.rooms = {room: set() for room in ("Stone", "Wood", "Sand", "Gold", "Molten", STREET, YARD, HOUSE, SHOP, NOBLE)}
        self.roads = set()
        self.plaza = set()
        self.buildings = []
        self.posts = []             # guard posts, spread over the roads
        self.wallLamps = {}         # tile: WallLamp
        self.dwellers = {}          # tile: Dweller

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


def layRoads(city, playerSpot):
    """The plaza in the middle, the ring roads round it, the spokes curving out from it, and a road from where you
    arrive to the nearest of them."""
    middleColumn, middleRow = (city.rowLength - 1) / 2, (city.rowCount - 1) / 2
    reachAcross, reachDown = city.rowLength / 2 - 2, city.rowCount / 2 - 2
    for spot in city.grid:
        column, row = spot % city.rowLength, spot // city.rowLength
        if math.hypot(column - middleColumn, row - middleRow) <= PLAZA_RADIUS:
            city.plaza.add(spot)
            city.roads.add(spot)
    for share in RING_ROADS:
        bend = random.uniform(0, math.tau)
        steps = int(math.tau * share * (reachAcross + reachDown))
        for step in range(steps):
            angle = math.tau * step / steps
            wobble = 1 + RING_WOBBLE * math.sin(3 * angle + bend)
            stampRoad(city, middleColumn + share * wobble * reachAcross * math.cos(angle),
                      middleRow + share * wobble * reachDown * math.sin(angle))
    spokeCount = random.randint(*SPOKE_ROADS)
    start = random.uniform(0, math.tau)
    for index in range(spokeCount):
        angle = start + math.tau * index / spokeCount + random.uniform(-0.2, 0.2)
        bend = random.uniform(-SPOKE_BEND, SPOKE_BEND)
        distance = PLAZA_RADIUS / max(reachAcross, reachDown)
        while distance <= 1.0:
            turning = angle + bend * distance  # the spoke curves more the further out it gets
            stampRoad(city, middleColumn + distance * reachAcross * math.cos(turning),
                      middleRow + distance * reachDown * math.sin(turning))
            distance += 0.5 / max(reachAcross, reachDown)
    # from where you arrive, straight toward the middle until it meets a road
    column, row = playerSpot % city.rowLength, playerSpot // city.rowLength
    length = max(1.0, math.hypot(middleColumn - column, middleRow - row))
    for step in range(int(length * 2) + 1):
        stampColumn = column + (middleColumn - column) * step / (length * 2)
        stampRow = row + (middleRow - row) * step / (length * 2)
        before = len(city.roads)
        here = city.spot(round(stampColumn), round(stampRow))
        if step > 2 and here in city.roads and before == len(city.roads):
            break
        stampRoad(city, stampColumn, stampRow)


# ---------------------------------------------------------------- buildings

def fits(city, cells, left, top, taken):
    """Can a building with these cells stand at (left, top), with a tile of open ground all round it?"""
    for column, row in cells:
        for stepColumn in (-1, 0, 1):
            for stepRow in (-1, 0, 1):
                atColumn, atRow = left + column + stepColumn, top + row + stepRow
                if not city.inside(atColumn, atRow) or city.spot(atColumn, atRow) in taken:
                    return False
    return True


def doorFor(city, cells, walls, left, top):
    """The wall cell that makes the best door: its outside faces a road (or failing that, open ground near one)
    and its inside faces the building's inside. None if no wall cell can be a door."""
    best = None
    for column, row in walls:
        for stepColumn, stepRow in SIDES.values():
            outsideCell = (column + stepColumn, row + stepRow)
            insideCell = (column - stepColumn, row - stepRow)
            if outsideCell in cells or insideCell not in cells or insideCell in walls:
                continue
            outside = city.spot(left + outsideCell[0], top + outsideCell[1])
            facesRoad = 0 if outside in city.roads else 1 if any(near in city.roads for near in neighborsOf(city, outside)) else 2
            if best is None or facesRoad < best[0]:
                best = (facesRoad, (column, row))
    return best[1] if best else None


def placeBuilding(city, kind, sizeRange, candidates, taken, nearRoad=True):
    """Puts one building of kind on the first candidate (left, top) where it fits (and, with nearRoad, its door
    faces a road). Returns the Building, or None."""
    for left, top in candidates:
        width, height = buildingSize(city.style, sizeRange)
        cells = shapeCells(city.style, width, height)
        if not fits(city, cells, left, top, taken):
            continue
        walls = outlineOf(cells)
        if len(cells) - len(walls) < 4:
            continue
        doorCell = doorFor(city, cells, walls, left, top)
        if doorCell is None:
            continue
        door = city.spot(left + doorCell[0], top + doorCell[1])
        outsideDoor = [near for near in neighborsOf(city, door) if near not in {city.spot(left + c, top + r) for c, r in cells}]
        if nearRoad and not any(near in city.roads or any(far in city.roads for far in neighborsOf(city, near)) for near in outsideDoor):
            continue
        building = Building(kind, {city.spot(left + c, top + r) for c, r in walls - {doorCell}},
                            {city.spot(left + c, top + r) for c, r in cells - walls}, door)
        for column, row in cells:  # (the next building's own margin keeps a one-tile alley between them)
            taken.add(city.spot(left + column, top + row))
        middle = (left + width / 2, top + height / 2)
        building.center = min(building.inside, key=lambda spot: math.hypot(spot % city.rowLength + 0.5 - middle[0],
                                                                          spot // city.rowLength + 0.5 - middle[1]))
        city.buildings.append(building)
        return building
    return None


def raiseBuilding(city, building):
    """Puts a placed building on the grid: its walls, its inside floor, its door, its room."""
    room, wallKind = {"house": (HOUSE, wall.HouseWall), "shop": (SHOP, wall.ShopWall), "mansion": (NOBLE, wall.NobleWall)}[building.kind]
    for spot in building.walls:
        city.grid[spot] = [WALL, 0, wallKind()]
    for spot in building.inside | {building.door}:
        city.grid[spot] = [FLOOR, 0]
    for spot in building.walls | building.inside | {building.door}:
        city.rooms[room].add(spot)


def removeUnreachable(city, playerSpot):
    """Takes down any building whose door you couldn't walk to from where you arrive (a pocket the packing closed
    in), until every door is reachable."""
    while True:
        reached, frontier = {playerSpot}, [playerSpot]
        while frontier:
            spot = frontier.pop()
            for near in neighborsOf(city, spot):
                if near not in reached and city.grid[near][0] == FLOOR:
                    reached.add(near)
                    frontier.append(near)
        cutOff = [building for building in city.buildings if building.door not in reached]
        if not cutOff:
            return
        for building in cutOff:
            city.buildings.remove(building)
            for spot in building.walls | building.inside | {building.door}:
                city.grid[spot] = [FLOOR, 0]
                for room in (HOUSE, SHOP, NOBLE):
                    city.rooms[room].discard(spot)


def placeBuildings(city, playerSpot):
    """Mansions on the open ground nearest the middle that's big enough, then the shops, then houses wherever
    there's room."""
    taken = set(city.roads)
    for near in [playerSpot] + neighborsOf(city, playerSpot):
        taken.add(near)
    middleColumn, middleRow = city.rowLength / 2, city.rowCount / 2
    lattice = [(left, top) for top in range(1, city.rowCount - 2, 2) for left in range(1, city.rowLength - 2, 2)]
    nearestThePlaza = sorted(lattice, key=lambda corner: math.hypot(corner[0] - middleColumn, corner[1] - middleRow))
    for _ in range(random.randint(*MANSIONS)):
        placeBuilding(city, "mansion", MANSION_SIZE, nearestThePlaza, taken)
    shopKinds = random.sample(list(cityshops.SHOP_KINDS), random.randint(*SHOP_COUNT))
    shuffled = lattice[:]
    random.shuffle(shuffled)
    for kind in shopKinds:
        shop = placeBuilding(city, "shop", SHOP_SIZE, shuffled, taken)
        if shop is not None:
            shop.shopKind = kind
    for _ in range(HOUSE_PASSES):  # a few passes, each size tried in turn, so the gaps between buildings fill up
        random.shuffle(shuffled)
        for corner in shuffled:  # (a house can face an alley between buildings: removeUnreachable keeps every door reachable)
            placeBuilding(city, "house", HOUSE_SIZE, [corner], taken, nearRoad=False)
    for building in city.buildings:
        raiseBuilding(city, building)
    removeUnreachable(city, playerSpot)
    for building in city.buildings:  # a shop's sign: in its wall beside the door
        if building.kind == "shop":
            besideDoor = [near for near in neighborsOf(city, building.door) if near in building.walls]
            if besideDoor:
                building.sign = besideDoor[0]
                city.grid[building.sign] = [SHOP_SIGN, 0, building.shopKind]


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
    """A tile inside a building for a chest: not just inside its door (the way in stays open) and not its middle."""
    doorway = set(neighborsOf(city, building.door))
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


def placeLights(city, playerSpot):
    """Wall lamps outside along the roads, at least WALL_LAMP_SPACING apart; wall lamps inside every building (one
    in a house, two in a shop or mansion); and lamp posts round the plaza."""
    doorways = set()
    for building in city.buildings:
        doorways |= {building.door, *neighborsOf(city, building.door)}
    outsideLamps = []
    for building in city.buildings:
        for wallSpot in sorted(building.walls):
            for near in neighborsOf(city, wallSpot):
                if near in building.inside or near in doorways or city.grid[near][0] != FLOOR or near not in city.rooms[STREET] | city.rooms[YARD]:
                    continue
                nearRoad = near in city.roads or any(far in city.roads for far in neighborsOf(city, near))
                spacedOut = all(abs(near % city.rowLength - lamp % city.rowLength) + abs(near // city.rowLength - lamp // city.rowLength)
                                >= WALL_LAMP_SPACING for lamp in outsideLamps)
                if nearRoad and spacedOut:
                    city.wallLamps[near] = WallLamp(sideOfWall(city, near, building.walls), WALL_LAMP_RADIUS)
                    outsideLamps.append(near)
    for building in city.buildings:
        wanted = 1 if building.kind == "house" else 2
        choices = [spot for spot in building.inside if spot not in doorways and spot != building.center
                   and city.grid[spot][0] == FLOOR and sideOfWall(city, spot, building.walls) is not None]
        random.shuffle(choices)
        for spot in choices[:wanted]:
            city.wallLamps[spot] = WallLamp(sideOfWall(city, spot, building.walls), ROOM_LAMP_RADIUS)
    middleColumn, middleRow = (city.rowLength - 1) / 2, (city.rowCount - 1) / 2
    for index in range(PLAZA_LAMPS):
        angle = math.tau * index / PLAZA_LAMPS
        spot = city.spot(round(middleColumn + (PLAZA_RADIUS - 1) * math.cos(angle)), round(middleRow + (PLAZA_RADIUS - 1) * math.sin(angle)))
        if spot != playerSpot and spot not in neighborsOf(city, playerSpot) and city.grid[spot][0] == FLOOR:
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
    """{tile: WallLamp} for this floor's wall lamps (only a city has them)."""
    if game.proportion != METROPOLIS:
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
    for spot in grid:
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
