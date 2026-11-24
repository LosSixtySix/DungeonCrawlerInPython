import random

from cruel.entities import enemies
from cruel.inventory import items
from cruel.inventory import recipes
from cruel.inventory import resources
from cruel.world import wall

"""
The Metropolis: a floor that is one whole city of insectoid Dwellers (design sheet:
https://claude.ai/artifact/538ySkNBUTYEUnSTVLSHii).

  The city   a ring of City Wall round the floor, then a grid of streets STREET_WIDTH wide with blocks between them.
             One block near the middle is the plaza, NOBLE_BLOCKS are the noble quarter (one or two mansions each),
             SHOP_COUNT blocks are shops (one big room each) and every other block is two rows of houses. Every
             building has exactly one door, onto a street. A house has a CHEST_CHANCE of a chest (a CityChest).
  Dwellers   citizens walk the streets, nobles stay in their quarter, guards stand at posts on street corners,
             merchants keep a shop each (dwellers.py runs their turns).
  Rooms      the floor's tiles are in the Street, House, Shop and Noble rooms (themes.CITY_ROOMS), each drawn in
             its own theme colors.

You always arrive on a street: the grid is laid out so a street runs through where you stand.
"""

METROPOLIS = "Metropolis"   # the floor type (gameManager.proportion)
APPEAR_CHANCE = 0.04        # chance a new floor is a city...
FIRST_FLOOR = 4             # ...from this floor down

# The layout
STREET_WIDTH = 2
BLOCK_SIZE = (13, 18)       # tiles between two streets (a block's width or height), random in this range
HOUSE_WIDTH = (5, 8)
SMALLEST_BLOCK = 6          # a gap between streets narrower than this stays street
SHOP_COUNT = (3, 5)         # never more than 5 shops, each a different kind
NOBLE_BLOCKS = 2
CHEST_CHANCE = 0.30         # a house has a chest this often
NOBLE_CHEST_CHANCE = 0.6
CHEST_THINGS = (1, 3)       # things in a house chest

# The Dwellers on a floor
CITIZENS = (20, 30)
NOBLES = (3, 6)
GUARD_POSTS = (6, 10)
NOBLES_ON_THE_PLAZA = 2

STREET, HOUSE, SHOP, NOBLE = "Street", "House", "Shop", "Noble"
FLOOR, WALL, CHEST, ENEMY = 0, 2, 3, 5


class CityChest(list):
    """A chest that belongs to the city (a house chest, or a dead merchant's stock): the items in it, like any chest.
    Taking from it is stealing (dwellers.hostileAct)."""


class City:
    """A city laid out on a grid: what the floor generator returns, plus where everything is."""

    def __init__(self, grid, rowLength):
        self.grid = grid
        self.rowLength = rowLength
        self.rooms = {room: set() for room in ("Stone", "Wood", "Sand", "Gold", "Molten", STREET, HOUSE, SHOP, NOBLE)}
        self.houses = []            # [(inside tiles, door)]
        self.mansions = []          # [(inside tiles, door)]
        self.shops = []             # [{"inside", "door", "counter", "kind"}]
        self.plaza = set()
        self.posts = []             # guard posts: street corners
        self.dwellers = {}          # tile: Dweller
        self.streetLines = ([], [])  # (columns, rows) where streets start

    def spot(self, column, row):
        return column + row * self.rowLength


# ---------------------------------------------------------------- laying the city out

def streetLines(size, mustCover):
    """Where streets start along one side of the map (each STREET_WIDTH wide), BLOCK_SIZE apart, the first just
    inside the city wall and the last against the far one. One of them covers mustCover (where you arrive)."""
    lines, at = [1], 1
    while True:
        at += STREET_WIDTH + random.randint(*BLOCK_SIZE)
        if at + STREET_WIDTH >= size - 1:
            break
        lines.append(at)
    lines.append(size - 1 - STREET_WIDTH)
    covering = min(max(1, mustCover if mustCover + 1 < size - 1 else mustCover - 1), size - 1 - STREET_WIDTH)
    if not any(line <= mustCover < line + STREET_WIDTH for line in lines):
        lines = [line for line in lines if abs(line - covering) >= SMALLEST_BLOCK + STREET_WIDTH or line in (1, size - 1 - STREET_WIDTH)]
        lines.append(covering)
    return sorted(set(lines))


def blocksBetween(columns, rows):
    """The blocks between the streets: (left, top, right, bottom), inclusive, at least SMALLEST_BLOCK across."""
    blocks = []
    for top, nextRow in zip(rows, rows[1:]):
        for left, nextColumn in zip(columns, columns[1:]):
            block = (left + STREET_WIDTH, top + STREET_WIDTH, nextColumn - 1, nextRow - 1)
            if block[2] - block[0] + 1 >= SMALLEST_BLOCK and block[3] - block[1] + 1 >= SMALLEST_BLOCK:
                blocks.append(block)
    return blocks


def building(city, left, top, right, bottom, room, wallKind, doorSide):
    """A building: a ring of wallKind walls round room floor, with one door in the middle of doorSide.
    Returns (inside tiles, door)."""
    inside = []
    for row in range(top, bottom + 1):
        for column in range(left, right + 1):
            spot = city.spot(column, row)
            if row in (top, bottom) or column in (left, right):
                city.grid[spot] = [WALL, 0, wallKind()]
            else:
                city.grid[spot] = [FLOOR, 0]
                inside.append(spot)
            city.rooms[room].add(spot)
    middleColumn, middleRow = (left + right) // 2, (top + bottom) // 2
    doorColumn, doorRow = {"top": (middleColumn, top), "bottom": (middleColumn, bottom),
                           "left": (left, middleRow), "right": (right, middleRow)}[doorSide]
    door = city.spot(doorColumn, doorRow)
    city.grid[door] = [FLOOR, 0]
    return inside, door


def buildHouses(city, block):
    """Two rows of houses across a block: the top row's doors open onto the street above, the bottom row's onto
    the street below. (A block too short for two rows gets one, opening upward.)"""
    left, top, right, bottom = block
    middle = (top + bottom) // 2
    rowsOfHouses = [(top, middle, "top"), (middle + 1, bottom, "bottom")] if bottom - top + 1 >= 8 else [(top, bottom, "top")]
    for rowTop, rowBottom, doorSide in rowsOfHouses:
        column = left
        while column <= right:
            width = random.randint(*HOUSE_WIDTH)
            if right - (column + width - 1) < HOUSE_WIDTH[0]:  # don't leave a sliver too narrow for a house
                width = right - column + 1
            city.houses.append(building(city, column, rowTop, column + width - 1, rowBottom, HOUSE, wall.HouseWall, doorSide))
            column += width


def houseChest():
    """What's in a house chest: a few things (gear, potions or materials) and maybe some gold. Never a relic."""
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


def chestSpotIn(city, inside, door):
    """A tile inside a building for a chest: not the one just inside its door, so the way in stays open."""
    doorway = set(neighborsOf(city, door))
    choices = [spot for spot in inside if spot not in doorway]
    return random.choice(choices) if choices else None


def neighborsOf(city, spot):
    rowLength = city.rowLength
    out = []
    for other in (spot - 1, spot + 1, spot - rowLength, spot + rowLength):
        if other in city.grid and (abs(other - spot) != 1 or other // rowLength == spot // rowLength):
            out.append(other)
    return out


def buildCity(rowLength, rowCount, playerSpot):
    """A whole city on a rowLength x rowCount floor, with a street through playerSpot. Returns a City."""
    grid = {spot: [FLOOR, 0] for spot in range(rowLength * rowCount)}
    city = City(grid, rowLength)
    playerColumn, playerRow = playerSpot % rowLength, playerSpot // rowLength
    for spot in grid:
        column, row = spot % rowLength, spot // rowLength
        if column in (0, rowLength - 1) or row in (0, rowCount - 1):
            grid[spot] = [WALL, 0, wall.CityWall()]
        else:
            city.rooms[STREET].add(spot)
    columns, rows = streetLines(rowLength, playerColumn), streetLines(rowCount, playerRow)
    city.streetLines = (columns, rows)
    blocks = blocksBetween(columns, rows)

    middleColumn, middleRow = rowLength / 2, rowCount / 2
    plaza = min(blocks, key=lambda block: abs((block[0] + block[2]) / 2 - middleColumn) + abs((block[1] + block[3]) / 2 - middleRow))
    others = [block for block in blocks if block != plaza]
    random.shuffle(others)
    nobleBlocks, others = others[:NOBLE_BLOCKS], others[NOBLE_BLOCKS:]
    shopCount = min(random.randint(*SHOP_COUNT), len(others))
    shopBlocks, houseBlocks = others[:shopCount], others[shopCount:]

    left, top, right, bottom = plaza
    city.plaza = {city.spot(column, row) for row in range(top, bottom + 1) for column in range(left, right + 1)}

    for left, top, right, bottom in nobleBlocks:
        halves = [(left, (left + right) // 2), ((left + right) // 2 + 1, right)] if right - left + 1 >= 12 else [(left, right)]
        for mansionLeft, mansionRight in halves:
            city.mansions.append(building(city, mansionLeft, top, mansionRight, bottom, NOBLE, wall.NobleWall, "bottom"))

    shopKinds = random.sample(SHOP_KIND_IDS, shopCount)
    for (left, top, right, bottom), kind in zip(shopBlocks, shopKinds):
        inside, door = building(city, left, top, right, bottom, SHOP, wall.ShopWall, random.choice(["top", "bottom"]))
        counter = city.spot((left + right) // 2, (top + bottom) // 2)
        city.shops.append({"inside": inside, "door": door, "counter": counter, "kind": kind})

    for block in houseBlocks:
        buildHouses(city, block)
    for spot in city.rooms[HOUSE] | city.rooms[SHOP] | city.rooms[NOBLE]:
        city.rooms[STREET].discard(spot)

    for inside, door in city.houses:
        if random.random() < CHEST_CHANCE:
            chestSpot = chestSpotIn(city, inside, door)
            if chestSpot is not None:
                grid[chestSpot] = [CHEST, 0, houseChest()]
    for inside, door in city.mansions:
        if random.random() < NOBLE_CHEST_CHANCE:
            chestSpot = chestSpotIn(city, inside, door)
            if chestSpot is not None:
                grid[chestSpot] = [CHEST, 0, houseChest()]

    grid[playerSpot] = [FLOOR, 0]
    placeDwellers(city, playerSpot)
    return city


# ---------------------------------------------------------------- the Dwellers

def openStreet(city, spot, taken):
    return city.grid[spot][0] == FLOOR and spot in city.rooms[STREET] and spot not in taken


def placeDwellers(city, playerSpot):
    """Guards at posts on street corners, a merchant at each shop's counter, nobles in their mansions and on the
    plaza, citizens on the streets (each with a house to go home to)."""
    taken = {playerSpot} | set(neighborsOf(city, playerSpot))
    columns, rows = city.streetLines
    corners = [city.spot(column, row) for column in columns[1:-1] for row in rows[1:-1]]
    random.shuffle(corners)
    corners = [spot for spot in corners if openStreet(city, spot, taken)]
    posts = corners[:random.randint(*GUARD_POSTS)]
    for post in posts:
        guard = enemies.DwellerGuard()
        guard.home = post
        city.dwellers[post] = guard
        taken.add(post)
    city.posts = posts

    for shop in city.shops:
        merchant = enemies.DwellerMerchant()
        merchant.home = shop["counter"]
        merchant.shopKind = shop["kind"]
        city.dwellers[shop["counter"]] = merchant
        taken.add(shop["counter"])

    nobleSpots = [spot for inside, _ in city.mansions for spot in inside]
    plazaSpots = [spot for spot in city.plaza if openStreet(city, spot, taken)]
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

    streets = [spot for spot in city.rooms[STREET] if openStreet(city, spot, taken)]
    houseInsides = [inside for inside, _ in city.houses if inside]
    for spot in random.sample(streets, min(len(streets), random.randint(*CITIZENS))):
        citizen = enemies.DwellerCitizen()
        citizen.home = random.choice(random.choice(houseInsides)) if houseInsides else spot
        city.dwellers[spot] = citizen
    for spot, dweller in city.dwellers.items():
        city.grid[spot] = [ENEMY, 0, dweller]


# ---------------------------------------------------------------- the shops (what each kind sells: see cityshops.py)

SHOP_KIND_IDS = ["ore", "gems", "food", "weapons", "tools", "armor", "potions", "builder"]
