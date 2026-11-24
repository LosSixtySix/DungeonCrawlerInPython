import math
import random

from cruel.inventory import items
from cruel.inventory import loot
from cruel.inventory import resources
from cruel.world import dwellers
from cruel.world import expansion
from cruel.world import metropolis
from cruel.world import organizers
from cruel.world import plants
from cruel.world import wall

"""
The Dwellers at work on their city's works floors (mineshafts.py). A worker is a Dweller citizen whose work is
"mine" or "farm" (enemies.Dweller.work). While it's calm it works instead of wandering (dwellers.calmTurn); seeing
you do something hostile, or an enemy of the city, it stops to deal with that first, like any Dweller.

What a worker brings in it carries in its pockets (its materials, like any enemy that picks things up: kill one and
you get your share). Once it has something, it takes it to the nearest storage chest (items.StorageChest, in the
storehouses by the shaft) and puts it in, adding to a stack of the same thing if there is one. A stack holds up to
STACK_LIMIT; what doesn't fit goes up the shaft to the city (it's gone).

  Miner   picks the nearest seam it can walk to: an ore vein or a Gold Wall beside a tile it can reach (one no
          other miner is working). It hits it for MINE_SWING a turn (no more than the wall's hardness) until it breaks,
          then rolls what the wall gives (loot.rollWall, with MINER_WISDOM) and takes it in. With no seam it can
          reach, it tunnels: it breaks the wall it can reach that's nearest the nearest seam. It never breaks the
          city's own walls (the storehouses) or a wall a lamp hangs on.
  Farmer  tends the farm's fields (its fields: {tile: crop kind}, shared by the farm's farmers) and its Dew Grubs,
          doing the first of these it can:
            - carrying Dew: takes it in.
            - holding food (a crop it picked): feeds it to the nearest Dew Grub that's hungry (one whose Dew isn't
              waiting to be collected).
            - a Dew Grub has Dew ready: collects it (DEW_PER_GRUB) into its pockets.
            - a crop is ripe: picks it (that's its food) and sows the field tile again with a sprout.
            - a field tile is bare (its crop withered or was taken): sows it.

The Dew Grub (enemies.DewGrub) stays in its pen, shuffling about it now and then (GRUB_SHUFFLE). Each time it's fed
it counts a feeding; after FEEDINGS_FOR_DEW it has made Dew, and eats no more until a farmer collects it.
"""

MINE_SWING = 4              # damage a miner does to the wall it's working each turn
MINER_WISDOM = 4            # how lucky a miner is with what a wall gives (loot.wallOdds)
SEAM_REACH = 40             # how far a miner looks for a seam (in steps)
GIVE_UP_TURNS = 6           # a worker that can't get any closer for this long gives up on where it's going
FEEDINGS_FOR_DEW = 3        # plants a Dew Grub eats to make its Dew
DEW_PER_GRUB = (1, 2)       # Dew a farmer collects from a grub
GRUB_SHUFFLE = 0.3          # a Dew Grub moves about its pen this often
STACK_LIMIT = 30            # a storage chest's stack of one thing holds this much; the rest goes up to the city
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
    wanders like any calm Dweller)."""
    if carrying(worker):
        return haul(game, position, worker)
    if worker.work == "mine":
        return mine(game, position, worker)
    if worker.work == "farm":
        return farm(game, position, worker)
    return None


def walkTo(game, position, worker, goal):
    """A step toward goal (a tile or the wall or chest beside where it's going). A worker that hasn't got any closer
    for GIVE_UP_TURNS turns forgets its target."""
    newPosition = dwellers.stepToward(game, position, goal)
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
    """Where this floor's storage chests are."""
    return [spot for spot, tile in game.grid.items() if tile[0] == CHEST and len(tile) > 2 and isinstance(tile[2], items.StorageChest)]


def putInChest(chest, materials):
    """Puts materials ({id: amount}) in a chest, on top of a stack of the same thing if there is one, up to
    STACK_LIMIT (the rest goes up to the city)."""
    for materialId, amount in materials.items():
        stack = next((thing for thing in chest if isinstance(thing, resources.MaterialStack) and thing.materialId == materialId), None)
        if stack is None:
            chest.append(resources.MaterialStack(materialId, min(amount, STACK_LIMIT)))
        else:
            stack.amount = min(STACK_LIMIT, stack.amount + amount)


def haul(game, position, worker):
    """Takes what it carries to the nearest storage chest and puts it in."""
    chests = storageChests(game)
    if not chests:
        return None
    chestSpot = min(chests, key=lambda spot: dwellers.distance(game, position, spot))
    if chestSpot in game.neighbors(position):
        putInChest(game.grid[chestSpot][2], carrying(worker))
        worker.materials = {}
        game.change = True
        return position
    return walkTo(game, position, worker, chestSpot)


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


def farm(game, position, farmer):
    """A farmer's turn: feed, collect Dew, pick or sow, whichever comes first (see the top of this file)."""
    grubs = grubsHere(game)
    if getattr(farmer, "food", None):
        hungry = nearest(game, position, [spot for spot, grub in grubs if not grub.dewReady])
        if hungry is not None:
            if hungry in game.neighbors(position):
                feed(game.grid[hungry][2], farmer)
                return position
            return walkTo(game, position, farmer, hungry)
    ready = nearest(game, position, [spot for spot, grub in grubs if grub.dewReady])
    if ready is not None:
        if ready in game.neighbors(position):
            collectDew(game.grid[ready][2], farmer)
            return position
        return walkTo(game, position, farmer, ready)
    fields = getattr(farmer, "fields", {})
    if not getattr(farmer, "food", None):
        ripe = nearest(game, position, [spot for spot in fields if isRipeCrop(game.grid[spot])])
        if ripe is not None:
            if ripe in game.neighbors(position):
                pickCrop(game, ripe, farmer)
                return position
            return walkTo(game, position, farmer, ripe)
    bare = nearest(game, position, [spot for spot, kind in fields.items() if plants.canGrow(kind, spot, game.grid, game.rooms)])
    if bare is not None:
        if bare in game.neighbors(position):
            sow(game, bare, fields[bare])
            return position
        return walkTo(game, position, farmer, bare)
    return None


def isRipeCrop(tile):
    """A city crop in one of its ripe stages."""
    return tile[0] == PLANT and len(tile) > 2 and getattr(tile[2], "cityCrop", False) and tile[2].stage in ("harvest", "seed")


def sow(game, spot, kind):
    """A new sprout of the city's crop on spot."""
    crop = plants.Plant(kind, planted=True)
    crop.cityCrop = True
    game.grid[spot] = [PLANT, game.grid[spot][1], crop]
    game.change = True


def pickCrop(game, spot, farmer):
    """The farmer picks the ripe crop on spot (its food for the grubs) and sows the tile again."""
    crop = game.grid[spot][2]
    farmer.food = plants.PLANTS[crop.kind]["herb"]
    sow(game, spot, crop.kind)


def feed(grub, farmer):
    """The farmer feeds its food to a Dew Grub: after FEEDINGS_FOR_DEW feedings, the grub has made Dew."""
    farmer.food = None
    grub.feedings += 1
    if grub.feedings >= FEEDINGS_FOR_DEW:
        grub.feedings = 0
        grub.dewReady = True


def collectDew(grub, farmer):
    """The farmer takes a Dew Grub's Dew into its pockets (it takes it in next)."""
    grub.dewReady = False
    farmer.materials["dew"] = carrying(farmer).get("dew", 0) + random.randint(*DEW_PER_GRUB)


def grubTurn(game, position, grub):
    """A Dew Grub's turn: now and then it shuffles to a free tile beside it, never out of its pen."""
    if random.random() >= GRUB_SHUFFLE:
        return position
    free = [spot for spot in game.neighbors(position) if spot in grub.pen and organizers.passable(game.grid[spot])]
    return organizers.moveTo(game, position, random.choice(free)) if free else position
