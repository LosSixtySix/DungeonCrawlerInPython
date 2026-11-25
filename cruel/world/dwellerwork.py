import math
import random

from cruel.inventory import items
from cruel.inventory import loot
from cruel.inventory import resources
from cruel.world import dewgrubs
from cruel.world import dwellerbuilding
from cruel.world import dwellerfarming
from cruel.world import dwellers
from cruel.world import expansion
from cruel.world import metropolis
from cruel.world import organizers
from cruel.world import plants
from cruel.world import queen
from cruel.world import wall

"""
The Dwellers at work on their city's works floors (mineshafts.py). A worker is a Dweller citizen whose work is
"mine" or "farm" (enemies.Dweller.work). While it's calm it works instead of wandering (dwellers.calmTurn); seeing
you do something hostile, or an enemy of the city, it stops to deal with that first, like any Dweller.

What a worker brings in it carries in its pockets (its materials, like any enemy that picks things up: kill one and
you get your share). Once it has something, it takes it to the nearest storage chest with room for it
(items.StorageChest, in the storehouses by the shaft) and puts it in, adding to a stack of the same thing if there is
one. A stack holds up to STACK_LIMIT and a chest up to CHEST_STACKS stacks. When every chest is full the workers
build another storehouse (dwellerbuilding.py); if there's nowhere left to build one, what doesn't fit goes up the
shaft to the city (it's gone). (A farmer keeps some food and seeds: dwellerfarming.toStore.)

A worker with a building to put up (dwellerbuilding.py) builds it before its own work, if it's one of the
dwellerbuilding.BUILDERS at it (or it's carrying something with nowhere to put it).

  Miner   picks the nearest seam it can walk to: an ore vein or a Gold Wall beside a tile it can reach (one no
          other miner is working). It hits it for MINE_SWING a turn (no more than the wall's hardness) until it breaks,
          then rolls what the wall gives (loot.rollWall, with MINER_WISDOM) and takes it in. With no seam it can
          reach, it tunnels: it breaks the wall it can reach that's nearest the nearest seam. It never breaks the
          city's own walls (the storehouses) or a wall a lamp hangs on.
  Farmer  farms the farm's fields like a goblin farmer and feeds the Dew Grubs (dwellerfarming.py); a grub with
          Dew ready, it collects it (DEW_PER_GRUB) into its pockets.

The Dew Grub (enemies.DewGrub) stays in its pen, shuffling about it now and then (GRUB_SHUFFLE). Each time a grown
one is fed it counts a feeding; after FEEDINGS_FOR_DEW it has made Dew, and eats no more until a farmer collects it.
A young one's feedings make it grow instead (dewgrubs.py).
"""

MINE_SWING = 4              # damage a miner does to the wall it's working each turn
MINER_WISDOM = 4            # how lucky a miner is with what a wall gives (loot.wallOdds)
SEAM_REACH = 40             # how far a miner looks for a seam (in steps)
GIVE_UP_TURNS = 6           # a worker that can't get any closer for this long gives up on where it's going
STUCK_SWAP_TURNS = 2        # a worker stuck this long swaps past whoever is in its way (a queue at a door)
FEEDINGS_FOR_DEW = 3        # plants a Dew Grub eats to make its Dew
DEW_PER_GRUB = (1, 2)       # Dew a farmer collects from a grub
GRUB_SHUFFLE = 0.3          # a Dew Grub moves about its pen this often
STACK_LIMIT = 30            # a storage chest's stack of one thing holds this much
CHEST_STACKS = 6            # stacks a storage chest holds
FLOOR, WALL, CHEST, ENEMY, PLANT = 0, 2, 3, 5, 8


# ---------------------------------------------------------------- working

def isWorker(dweller):
    return getattr(dweller, "work", None) is not None


def carrying(worker):
    """What a worker has in its pockets ({material id: amount})."""
    if not hasattr(worker, "materials"):
        worker.materials = {}
    return {materialId: amount for materialId, amount in worker.materials.items() if amount > 0}


def workTurn(game, position, worker):
    """A calm worker's turn at its work. Returns where it ends up, or None if there's nothing for it to do (it
    wanders like any calm Dweller). A Dew carrier's work is the Queen's (queen.carrierTurn)."""
    if worker.work == "dew":
        return queen.carrierTurn(game, position, worker)
    loaded = dwellerfarming.needsHauling(worker) if worker.work == "farm" else bool(toStore(worker))
    if loaded:  # (a farmer keeps its food and seeds, and takes the rest in once it's a load)
        moved = haul(game, position, worker)
        if moved is not None:
            return moved
        return storeElsewhere(game, position, worker)
    plan = None if getattr(worker, "movingGrub", None) else dwellerbuilding.planFor(game, worker)
    if plan is not None:  # (a farmer moving a grub finishes that first)
        moved = dwellerbuilding.build(game, position, worker, plan)
        if moved is not None:
            return moved
    if worker.work == "mine":
        return mine(game, position, worker)
    if worker.work == "farm":
        return dwellerfarming.farmTurn(game, position, worker)
    return None


def walkTo(game, position, worker, goal, reach=None):
    """A step toward goal (a tile or the wall or chest beside where it's going). A worker that hasn't got any closer
    for GIVE_UP_TURNS turns forgets its target; one stuck for STUCK_SWAP_TURNS swaps past whoever is in its way. A
    farmer walks through any plant (like a goblin farmer)."""
    stuck = getattr(worker, "stuckTurns", 0) >= STUCK_SWAP_TURNS
    newPosition = dwellers.stepToward(game, position, goal, forceSwap=stuck, throughPlants=worker.work == "farm", unit=worker,
                                      reach=reach or dwellers.PATH_REACH)
    if newPosition == position:
        worker.stuckTurns = getattr(worker, "stuckTurns", 0) + 1
        if worker.stuckTurns >= GIVE_UP_TURNS:
            worker.target = None
            worker.stuckTurns = 0
    else:
        worker.stuckTurns = 0
    return newPosition


# ---------------------------------------------------------------- taking things in

def storageChests(game):
    """Where this floor's storage chests are. Looked for once a turn on each floor (farmers ask many times a turn):
    one destroyed during the turn is left out at once, a storehouse built during it has its chests found next
    turn."""
    key = (game.level, getattr(game, "sideFloor", None), game.turnCount, id(game.grid))
    cache = game.__dict__.setdefault("storageChestsFound", {})
    if key not in cache:
        if len(cache) > 16:
            cache.clear()
        cache[key] = [spot for spot, tile in game.grid.items() if isStorageChest(tile)]
    return [spot for spot in cache[key] if isStorageChest(game.grid[spot])]


def isStorageChest(tile):
    return tile[0] == CHEST and len(tile) > 2 and isinstance(tile[2], items.StorageChest)


def openStack(chest, materialId):
    """A stack of this in the chest that isn't full, or None."""
    return next((thing for thing in chest if isinstance(thing, resources.MaterialStack) and thing.materialId == materialId
                 and thing.amount < STACK_LIMIT), None)


def hasRoomFor(chest, materials):
    """Can the chest take any of materials: a stack of one of them that isn't full, or room for a new stack?"""
    return len(chest) < CHEST_STACKS or any(openStack(chest, materialId) for materialId in materials)


def putInChest(chest, materials):
    """Puts materials ({id: amount}) in a chest, on top of a stack of the same thing that isn't full (up to
    STACK_LIMIT), then in new stacks while the chest has room for them (CHEST_STACKS). Returns what didn't fit
    ({id: amount})."""
    leftOver = {}
    for materialId, amount in materials.items():
        while amount > 0:
            stack = openStack(chest, materialId)
            if stack is None:
                if len(chest) >= CHEST_STACKS:
                    break
                stack = resources.MaterialStack(materialId, 0)
                chest.append(stack)
            taken = min(amount, STACK_LIMIT - stack.amount)
            stack.amount += taken
            amount -= taken
        if amount > 0:
            leftOver[materialId] = amount
    return leftOver


def toStore(worker):
    """What a worker takes in: everything a miner carries; a farmer's Dew and what food and seeds it doesn't keep."""
    return dwellerfarming.toStore(worker) if worker.work == "farm" else carrying(worker)


def drop(worker, materials):
    """Takes materials ({id: amount}) out of the worker's pockets."""
    for materialId, amount in materials.items():
        left = carrying(worker).get(materialId, 0) - amount
        if left > 0:
            worker.materials[materialId] = left
        else:
            worker.materials.pop(materialId, None)


def haul(game, position, worker):
    """Takes what it has to store (toStore) to the nearest storage chest with room for it and puts it in (what
    doesn't fit, it keeps). None if no chest has room."""
    load = toStore(worker)
    chests = [spot for spot in storageChests(game) if hasRoomFor(game.grid[spot][2], load)]
    if not chests:
        return None
    chestSpot = min(chests, key=lambda spot: dwellers.distance(game, position, spot))
    if chestSpot in game.neighbors(position):
        leftOver = putInChest(game.grid[chestSpot][2], load)
        drop(worker, {materialId: amount - leftOver.get(materialId, 0) for materialId, amount in load.items()})
        game.change = True
        return position
    return walkTo(game, position, worker, chestSpot)


def storeElsewhere(game, position, worker):
    """Every chest is full (or there are none): it helps build a new storehouse; with nowhere to build one, what it
    has to store goes up to the city (it's gone)."""
    plan = dwellerbuilding.storehousePlan(game, position, worker)
    if plan is not None:
        worker.job = "build"
        return dwellerbuilding.build(game, position, worker, plan)
    if storageChests(game):
        drop(worker, toStore(worker))
    return None


# ---------------------------------------------------------------- mining

def mineable(tile):
    """A wall a miner may break: anything but the city's own walls."""
    return tile[0] == WALL and len(tile) > 2 and not isinstance(tile[2], wall.CityBuildingWall)


def isSeam(tile):
    """An ore vein or a Gold Wall."""
    return mineable(tile) and (isinstance(tile[2], wall.OreVein) or tile[2].name == "Gold Wall")


def lampWalls(game):
    """The walls the lamps on this floor hang on (a miner leaves those)."""
    walls = set()
    for spot, lamp in metropolis.wallLampsHere(game).items():
        stepColumn, stepRow = metropolis.SIDES[lamp.side]
        walls.add(spot + stepColumn + stepRow * game.rowLength)
    return walls


def pickSeam(game, position, miner):
    """The wall a miner works next: the nearest seam beside a tile it can walk to that no other miner is working;
    with none, the wall it can reach that's nearest the nearest seam (it tunnels toward it). None if there's
    nothing to mine."""
    reach = expansion.walkingDistances(game, position, SEAM_REACH)
    worked = {getattr(other, "target", None) for _, other in dwellers.cityDwellers(game) if other is not miner}
    keepOff = worked | lampWalls(game)
    reachable = {}  # wall -> steps to stand beside it
    for spot, steps in reach.items():
        for near in game.neighbors(spot):
            if near not in keepOff and mineable(game.grid[near]) and steps < reachable.get(near, math.inf):
                reachable[near] = steps
    seams = [spot for spot in reachable if isSeam(game.grid[spot])]
    if seams:
        return min(seams, key=lambda spot: reachable[spot])
    everySeam = [spot for spot, tile in game.grid.items() if isSeam(tile) and spot not in keepOff]
    if not everySeam or not reachable:
        return None
    nearestSeam = min(everySeam, key=lambda spot: dwellers.distance(game, position, spot))
    return min(reachable, key=lambda spot: dwellers.distance(game, spot, nearestSeam))


def mine(game, position, miner):
    """A miner's turn: to its seam, and a swing at it once it's there."""
    target = getattr(miner, "target", None)
    if target is None or not mineable(game.grid[target]):
        target = miner.target = pickSeam(game, position, miner)
    if target is None:
        return None
    if target not in game.neighbors(position):
        return walkTo(game, position, miner, target)
    swing(game, target, miner)
    return position


def swing(game, target, miner):
    """A miner hits the wall at target; once it breaks, what it gives goes in the miner's pockets."""
    seam = game.grid[target][2]
    seam.takeDamage(MINE_SWING, game.tileSize)
    if seam.hp > 0:
        return
    game.grid[target] = [FLOOR, game.grid[target][1]]
    for materialId, amount in loot.rollWall(seam.name, MINER_WISDOM):
        miner.materials[materialId] = carrying(miner).get(materialId, 0) + amount
    miner.target = None
    game.change = True


# ---------------------------------------------------------------- farming

def grubsHere(game):
    """(position, Dew Grub) for every Dew Grub on the floor (the ones that have moved this turn too)."""
    return [(spot, dweller) for spot, dweller in dwellers.cityDwellers(game) if dweller.role == "grub"]


def nearest(game, position, spots):
    return min(spots, key=lambda spot: dwellers.distance(game, position, spot)) if spots else None


def feed(grub, farmer):
    """The farmer feeds a herb from its pockets to a Dew Grub (it's no longer hungry): after FEEDINGS_FOR_DEW
    feedings, a grown grub has made Dew; a young one grows (dewgrubs.FEEDINGS_TO_GROW). False if it had no food."""
    if not dwellerfarming.takeFood(farmer):
        return False
    grub.hunger = 0
    if not grub.grown:
        dewgrubs.growOn(grub)
        return True
    grub.feedings += 1
    if grub.feedings >= FEEDINGS_FOR_DEW:
        grub.feedings = 0
        grub.dewReady = True
    return True


def collectDew(grub, farmer):
    """The farmer takes a Dew Grub's Dew into its pockets (it takes it in next)."""
    grub.dewReady = False
    farmer.materials["dew"] = carrying(farmer).get("dew", 0) + random.randint(*DEW_PER_GRUB)


def grubTurn(game, position, grub):
    """A Dew Grub's turn: now and then it shuffles to a free tile beside it, never out of its pen (nor while a
    farmer is coming to pick it up)."""
    if dewgrubs.isBeingLed(game, grub) or random.random() >= GRUB_SHUFFLE:
        return position
    free = [spot for spot in game.neighbors(position) if spot in grub.pen and organizers.passable(game.grid[spot])]
    return organizers.moveTo(game, position, random.choice(free)) if free else position
