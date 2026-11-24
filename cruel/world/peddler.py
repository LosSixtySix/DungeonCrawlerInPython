import random

from cruel.inventory import recipes
from cruel.inventory import relics
from cruel.inventory import resources
from cruel.world import wall

"""
The Gray Peddler: a trader who turns up on a new floor by chance (APPEAR_CHANCE), with no message. A signpost beside
where you arrive is the only clue. He waits in a small room of Peddler's Stone with one entrance, somewhere away
from you.

  Shop      face him and press interact to open his shop (the "shop" window, built from the Inventory window).
            Buy tab: his stock. Sell tab: your pack, then your pouch. He sells finished things only (gear, potions,
            meals, stations and the Leather Pouch, never parts like Handles or Ingots), and now and then a relic.
            He buys any item for BUY_BACK_SHARE of what he'd sell it for, and any material at MATERIALS_PER_GOLD
            for 1 gold. His stock never refills, and what you sell him isn't resold.
  Prices    worked out from each recipe's materials (recipePrice), so they follow the game's own costs.
  Fighting  any damage from you turns him hostile for good (provoke): the shop closes and he fights like any
            enemy. Killed, he pays his gold and drops everything still in his stock (enemies.GrayPeddler.loot).

The game manager calls placeRoom and placeSignpost when a new floor is made (gameManager.maybeAddPeddler).
"""

# When he turns up
APPEAR_CHANCE = 0.08        # rolled once for each brand-new floor...
FIRST_FLOOR = 1             # ...from this floor down (never on the Scorched Depths)

# His stock
STOCK_SIZE = (6, 9)         # how many things he has
QUALITY_ODDS = [("Common", 75), ("Fine", 20), ("Masterwork", 5)]  # gear quality, in percent
RELIC_CHANCE = 0.05         # chance one of his things is a relic
NEVER_SOLD_RELICS = {"molten_blade"}  # relics you only get by a path (the Scorched Depths), never from him
NEVER_SOLD_STATIONS = {"shrine", "forge"}  # found in vaults, never made, so never sold

# Prices
PRICE_MULTIPLIER = 1.5      # his price is this many times what the recipe's materials (and gold) are worth...
QUALITY_PRICE = {"Crude": 0.75, "Common": 1.0, "Fine": 1.25, "Masterwork": 1.5}  # ...times this for gear...
LEAST_PRICE = 2             # ...and never less than this
RELIC_PRICE = 200
MATERIALS_PER_GOLD = 11     # he buys any material at this many for 1 gold
BUY_BACK_SHARE = 0.25       # and any item for this share of what he'd sell it for
# What one of a material is worth, by its group in resources.MATERIALS (anything else: DEFAULT_WORTH). A material a
# recipe makes (Ingots, Glass, Handles, cut gems, Iron Ore from Scrap) is worth what goes into making it instead.
GROUP_WORTH = {"Raw": 1, "Ore": 2, "Plants": 2}
DEFAULT_WORTH = 2

# His room: a ring of Peddler's Stone around ROOM_INSIDE floor, with one gap for the entrance
ROOM_INSIDE = (7, 5)        # columns, rows
ROOM_DISTANCE = 15          # at least this many tiles from where you arrive
ROOM_TRIES = 400
BLOCKING_TILES = (1, 3, 4, 5, 6, 7)  # the player, chests, doors, enemies and stations: never built over

SIGNPOST = 13               # grid tile type of the signpost by the arrival spot
FLOOR, WALL = 0, 2


# ---------------------------------------------------------------- his stock

class Ware:
    """One thing in his stock. kind: "gear", "potion", "relic" (each holds the item you'd get), "station" (unlocks a
    Crafting tab) or "pouch" (the Leather Pouch upgrade). recipeId: the recipe it comes from (none for a relic)."""

    def __init__(self, kind, price, item=None, recipeId=None, stationId=None):
        self.kind = kind
        self.price = price
        self.item = item
        self.recipeId = recipeId
        self.stationId = stationId

    @property
    def name(self):
        if self.item is not None:
            return self.item.name
        return recipes.RECIPES_BY_ID[self.recipeId].name

    @property
    def recipe(self):
        return recipes.RECIPES_BY_ID.get(self.recipeId)


def materialWorth(materialId, depth=0):
    """What one of a material is worth to him: by its group, or for a made material, what went into it."""
    madeBy = next((recipe for recipe in recipes.RECIPES if recipe.kind == "material" and recipe.makes == materialId), None)
    if madeBy is not None and depth < 4:
        return sum(materialWorth(needed, depth + 1) * count for needed, count in madeBy.needs.items()
                   if needed != "gold") / madeBy.amount
    group = resources.MATERIALS[materialId][1]
    return GROUP_WORTH.get(group, DEFAULT_WORTH)


def recipePrice(recipe, quality="Common"):
    """His price for one thing made by recipe: PRICE_MULTIPLIER times what its materials and gold are worth (times
    QUALITY_PRICE for gear), and at least LEAST_PRICE."""
    worth = sum(count if materialId == "gold" else materialWorth(materialId) * count for materialId, count in recipe.needs.items())
    price = round(PRICE_MULTIPLIER * worth * QUALITY_PRICE.get(quality, 1.0) / recipe.amount)
    return max(LEAST_PRICE, price)


def itemPrice(item):
    """What he'd sell this item for (used for what he pays for yours). None if he doesn't know it."""
    if relics.isRelic(item):
        return RELIC_PRICE
    recipe = recipes.recipeFor(item)
    if recipe is None or recipe.id.startswith("found_"):
        return None
    return recipePrice(recipe, getattr(item, "quality", "Common"))


def offerFor(item):
    """What he pays for one of your items: BUY_BACK_SHARE of his price, at least 1 gold."""
    price = itemPrice(item)
    return max(1, int((price or 0) * BUY_BACK_SHARE))


def offerForMaterial(amount):
    """(gold he pays, how many he takes) for a pile of one material: only whole lots of MATERIALS_PER_GOLD."""
    lots = amount // MATERIALS_PER_GOLD
    return lots, lots * MATERIALS_PER_GOLD


def stockRecipes(player):
    """(stations you don't have, everything else) he could stock, as recipes. Parts (kind "material"), planting,
    setting up, relic stations, found-gear stand-ins and double batches are never sold. The Leather Pouch is only
    sold until you have it."""
    stations, others = [], []
    for recipe in recipes.RECIPES:
        if recipe.id.startswith("found_") or recipe.amount != 1:
            continue
        if recipe.kind == "station":
            if recipe.makes not in player.stations and recipe.makes not in NEVER_SOLD_STATIONS:
                stations.append(recipe)
        elif recipe.kind in ("item", "potion"):
            others.append(recipe)
        elif recipe.kind == "upgrade" and player.pouchLimit < resources.BIG_POUCH_LIMIT:
            others.append(recipe)
    return stations, others


def rollQuality():
    names, weights = zip(*QUALITY_ODDS)
    return random.choices(names, weights=weights)[0]


def wareFrom(recipe):
    """A Ware for one thing made by recipe (gear gets its quality rolled now)."""
    if recipe.kind == "station":
        return Ware("station", recipePrice(recipe), recipeId=recipe.id, stationId=recipe.makes)
    if recipe.kind == "upgrade":
        return Ware("pouch", recipePrice(recipe), recipeId=recipe.id)
    if recipe.kind == "item":
        quality = rollQuality()
        return Ware("gear", recipePrice(recipe, quality), item=recipe.build(quality), recipeId=recipe.id)
    potion = recipe.makeItem(0, 0)
    potion.recipeId = recipe.id
    return Ware("potion", recipePrice(recipe), item=potion, recipeId=recipe.id)


def relicWare():
    choices = [relicId for relicId in relics.RELICS if relicId not in NEVER_SOLD_RELICS]
    return Ware("relic", RELIC_PRICE, item=relics.make(random.choice(choices)))


def rollStock(player):
    """His stock: STOCK_SIZE things, always one station you don't have yet (when there's one left), maybe a relic."""
    size = random.randint(*STOCK_SIZE)
    stations, others = stockRecipes(player)
    picked = []
    if stations:
        first = random.choice(stations)
        picked.append(first)
        stations.remove(first)
    pool = stations + others
    picked += random.sample(pool, min(len(pool), size - len(picked)))
    stock = [wareFrom(recipe) for recipe in picked]
    if random.random() < RELIC_CHANCE:
        relic = relicWare()
        if len(stock) >= size:
            stock[-1] = relic
        else:
            stock.append(relic)
    return stock


# ---------------------------------------------------------------- buying and selling

def buy(player, peddler, index):
    """You buy the ware at index of his stock. Returns (bought?, message)."""
    ware = peddler.wares[index]
    if ware.kind == "station" and ware.stationId in player.stations:
        return False, "You already have one"
    if ware.kind == "pouch" and player.pouchLimit >= resources.BIG_POUCH_LIMIT:
        return False, "Your pouch is already big"
    if player.gold < ware.price:
        return False, f"You need {ware.price - player.gold} more gold"
    if ware.item is not None and player.roomFor(ware.item) < 1:
        return False, "No room in your pack"
    player.gold -= ware.price
    peddler.wares.pop(index)
    if ware.kind == "station":
        player.stations.add(ware.stationId)
        return True, f"Bought the {ware.name}: its Crafting tab is open"
    if ware.kind == "pouch":
        player.pouchLimit = resources.BIG_POUCH_LIMIT
        return True, f"Bought the {ware.name}: your pouch holds {player.pouchLimit} of each"
    player.addItemToInventory(ware.item)
    return True, f"Bought {ware.name} for {ware.price} gold"


def sellItem(player, index):
    """You sell him one of the item in pack slot index (one potion off a stack). Returns the message."""
    item = player.takeOne(index)
    gold = offerFor(item)
    player.gold += gold
    return f"Sold {item.name} for {gold} gold"


def sellMaterial(player, materialId, everything=False):
    """You sell him one lot of MATERIALS_PER_GOLD of a material, or with everything, every whole lot.
    Returns (sold?, message)."""
    have = player.materials.get(materialId, 0)
    lots, taken = offerForMaterial(have)
    if not lots:
        return False, f"He only takes {MATERIALS_PER_GOLD} at a time"
    if not everything:
        lots, taken = 1, MATERIALS_PER_GOLD
    player.materials[materialId] = have - taken
    if player.materials[materialId] == 0:
        del player.materials[materialId]
    player.gold += lots
    return True, f"Sold {taken} {resources.materialName(materialId)} for {lots} gold"


def sellableMaterials(player):
    """The material ids in your pouch, in the pouch's order, that you have any of."""
    return [materialId for materialId in resources.MATERIALS if player.materials.get(materialId, 0) > 0]


# ---------------------------------------------------------------- fighting him

def isPeddler(enemy):
    return getattr(enemy, "merchant", False)


def isCalm(enemy):
    """Is this the Peddler, still willing to trade (you haven't hurt him)?"""
    return isPeddler(enemy) and not enemy.hostile


def attitudeLabel(enemy):
    """For his name when you look at him: "trader" while he'll trade, "hostile" once you've hurt him. None for
    every other enemy."""
    if not isPeddler(enemy):
        return None
    return "hostile" if enemy.hostile else "trader"


def provoke(gameManager, enemy, position):
    """You hurt enemy: if it's the Peddler, he turns on you for good and his shop closes."""
    if not isCalm(enemy):
        return
    enemy.hostile = True
    enemy.lastPlayerPosition = gameManager.playerPositionFlat
    gameManager.closeWindow("shop")
    gameManager.addPopup("The Peddler turns on you!", position)


# ---------------------------------------------------------------- his room and the signpost

def placeRoom(grid, rowLength, playerSpot, peddler):
    """Builds his room on a new floor's grid: a ring of Peddler's Stone with one gap (on the side facing the most
    open floor), ROOM_INSIDE floor inside, and him in the middle. At least ROOM_DISTANCE from playerSpot, never over
    the player, chests, doors, enemies or stations. Returns his position, or None if there's no room for it."""
    rowCount = len(grid) // rowLength
    insideColumns, insideRows = ROOM_INSIDE
    width, height = insideColumns + 2, insideRows + 2
    playerColumn, playerRow = playerSpot % rowLength, playerSpot // rowLength
    for _ in range(ROOM_TRIES):
        left = random.randint(1, rowLength - width - 1)
        top = random.randint(1, rowCount - height - 1)
        middleColumn, middleRow = left + width // 2, top + height // 2
        if abs(middleColumn - playerColumn) + abs(middleRow - playerRow) < ROOM_DISTANCE:
            continue
        block = [(left + column) + (top + row) * rowLength for row in range(height) for column in range(width)]
        if any(grid[spot][0] in BLOCKING_TILES for spot in block):
            continue
        for row in range(height):
            for column in range(width):
                spot = (left + column) + (top + row) * rowLength
                onRing = row in (0, height - 1) or column in (0, width - 1)
                grid[spot] = [WALL, 0, wall.PeddlerWall()] if onRing else [FLOOR, 0]
        entrance, outside = entranceFor(grid, rowLength, left, top, width, height)
        grid[entrance] = [FLOOR, 0]
        if grid[outside][0] == WALL:  # the doorway opens onto floor, so it reads as a way in
            grid[outside] = [FLOOR, 0]
        center = middleColumn + middleRow * rowLength
        grid[center] = [5, 0, peddler]
        return center
    return None


def entranceFor(grid, rowLength, left, top, width, height):
    """(the gap in the ring, the tile just outside it): the middle of the side whose outside has the most open floor
    within a few tiles."""
    rowCount = len(grid) // rowLength
    middleColumn, middleRow = left + width // 2, top + height // 2
    sides = {  # side: (gap column, gap row, step outward)
        "top": (middleColumn, top, (0, -1)), "bottom": (middleColumn, top + height - 1, (0, 1)),
        "left": (left, middleRow, (-1, 0)), "right": (left + width - 1, middleRow, (1, 0)),
    }

    def openness(side):
        column, row, (stepColumn, stepRow) = sides[side]
        count = 0
        for distance in range(1, 5):
            outsideColumn, outsideRow = column + stepColumn * distance, row + stepRow * distance
            if 0 <= outsideColumn < rowLength and 0 <= outsideRow < rowCount:
                count += grid[outsideColumn + outsideRow * rowLength][0] == FLOOR
        return count

    best = max(sides, key=openness)
    column, row, (stepColumn, stepRow) = sides[best]
    return column + row * rowLength, (column + stepColumn) + (row + stepRow) * rowLength


def placeSignpost(grid, besideSpots):
    """Puts the signpost on a free floor tile among besideSpots (the tiles next to where you arrive), or on a wall
    beside you if they're all walls. Returns where it went, or None."""
    for spot in besideSpots:
        if grid[spot][0] == FLOOR:
            grid[spot] = [SIGNPOST, grid[spot][1]]
            return spot
    for spot in besideSpots:
        if grid[spot][0] == WALL:
            grid[spot] = [SIGNPOST, grid[spot][1]]
            return spot
    return None
