from cruel.inventory import loot
from cruel.world import dewgrubs
from cruel.world import dwellerbuilding
from cruel.world import dwellers
from cruel.world import dwellerwork
from cruel.world import plants

"""
The farmers of a city's farm floor (mineshafts.py): growers, who farm like the goblin farmers (expansion.py), and
keepers, who feed what they grow to the Dew Grubs (dewgrubs.py). A farm has both (farmer.farmRole); a farmer from
before the roles does both, the keeper's work first.

The fields. The farm's fields ({tile: crop kind}, shared by its farmers: farmer.fields) are the plots of its
farmhouses (farmhouses.py: round buildings, each growing one crop in four triangular plots). They're sown with seeds: a
sprout of the city's crop (plants.Plant, planted: it never withers) grows through its stages, and picking it when
it's ripe gives what any planted plant gives (loot.rollPick): its herb ready to harvest, its seeds gone to seed.
Nothing wild sprouts in a farmhouse (fieldTiles, like a goblin farming hut). A grower tends its own fields (myFields: the
farm's crops dealt out among the growers there are, so every crop has one; growers that share a crop split its
fields between them): it picks each ripe crop in the stage it wants (gone to seed while the farm is short of seeds of it:
fewer than its bare tiles need plus SEEDS_KEPT, on the grower and in the storehouse chests; else ready to harvest; in
its last stage, whatever it gives), sows the bare tiles (fetching seeds from the chests when it has none), and pulls
up anything else growing there. It keeps SEEDS_KEPT seeds and takes the rest, and every herb, to the chests once it
has FARMER_HAUL. While the fields have fewer than FIELD_TILES_PER_GRUB tiles a grub (and FIELD_TILES_PER_GROWER a
grower), the growers build another farmhouse (dwellerbuilding.farmhousePlan), growing the crop the farm has least of.

The grubs. The keepers look after KEEPER_HERD grubs each, as many as they can feed in time (caredFor): the grown ones
first (they make the Dew), then the young nearest grown, then the least hungry. Any more than that nobody feeds, and
they starve. Each keeper looks after its own pens (keeperPens: the farm's pens dealt out among the keepers there are,
so a keeper's death hands its pens to the others). It keeps FOOD_KEPT herbs (any herb is food for a grub), fetching
more from the chests under FOOD_LOW, and does the first of these it can:
  1. feeds the nearest hungry grub (one it looks after that has gone HUNGRY_TURNS without food, isn't waiting with
     Dew and no other keeper is going to): a starving one (STARVING_TURNS) anywhere first, then one in its own pens, then any. It
     feeds from up to dewgrubs.REACH tiles away (over the pen's fence: it doesn't have to go in). A grub it can't get to (GIVE_UP_TURNS) it leaves to the
     others for SKIP_TURNS.
  2. collects a grub's Dew, the same way (it takes it in with a load, or when it goes for food).
  3. moves a grub to another pen, or plans a new pen (dewgrubs.herdTurn).
  4. tops up its food from the chests.
  5. waits by its pens.
A grower with herbs on it feeds a starving grub the keepers look after (one that has gone STARVING_TURNS) before
its own work.
A Dew Grub that goes STARVE_TURNS turns without food (not counting turns its Dew is waiting) starves (starveTurn).
"""

FOOD_KEPT = 20              # herbs a keeper keeps in its pockets for the grubs...
FOOD_LOW = 5                # ...fetching more when it has fewer than this
SEEDS_KEPT = 4              # seeds of its crop a grower keeps (and the farm keeps in hand beyond its bare tiles)
FARMER_HAUL = 8             # a farmer takes in what it doesn't keep once it has this much
STARVE_TURNS = 100          # a Dew Grub that goes this long without food starves (10 plant growth steps)...
HUNGRY_TURNS = STARVE_TURNS // 2  # ...and is fed once it has gone this long...
STARVING_TURNS = STARVE_TURNS * 3 // 4  # ...and before any other once it has gone this long
SKIP_TURNS = 20             # a keeper that couldn't get to a grub leaves it for this long
KEEPER_HERD = 5             # grubs a keeper can feed in time; the keepers let any more than that starve
FIELD_TILES_PER_GRUB = 3    # the growers build another farmhouse while there's less field than this a grub...
FIELD_TILES_PER_GROWER = 20  # ...and less than this a grower (what they can tend: a farmhouse's plots each)
FOODS = {info["herb"] for info in plants.PLANTS.values()}
SEEDS = {info["seed"] for info in plants.PLANTS.values()}
FLOOR, PLANT = 0, 8


def roleOf(farmer):
    """"keeper", "grower", or None (a farmer from before the roles: both)."""
    return getattr(farmer, "farmRole", None)


def keeps(farmer, what):
    return roleOf(farmer) in (None, what)


# ---------------------------------------------------------------- what's in hand

def foodIn(materials):
    return sum(amount for materialId, amount in materials.items() if materialId in FOODS)


def foodCarried(farmer):
    return foodIn(dwellerwork.carrying(farmer))


def takeFood(farmer):
    """One herb out of the farmer's pockets (to feed a grub). True if it had one."""
    for materialId, amount in sorted(dwellerwork.carrying(farmer).items()):
        if materialId in FOODS:
            dwellerwork.drop(farmer, {materialId: 1})
            return True
    return False


def seedOf(kind):
    return plants.PLANTS[kind]["seed"]


def toStore(farmer):
    """What the farmer takes in: its Dew, and the herbs (a keeper keeps FOOD_KEPT) and seeds (a grower keeps
    SEEDS_KEPT of each) it doesn't keep ({id: amount})."""
    load, store = dwellerwork.carrying(farmer), {}
    foodLeft = FOOD_KEPT if keeps(farmer, "keeper") else 0
    for materialId, amount in sorted(load.items()):
        if materialId in FOODS:
            keep = min(amount, foodLeft)
            foodLeft -= keep
        elif materialId in SEEDS:
            keep = min(amount, SEEDS_KEPT) if keeps(farmer, "grower") else 0
        else:
            keep = 0
        if amount > keep:
            store[materialId] = amount - keep
    return store


def needsHauling(farmer):
    """Time to take things in: a load of it, or Dew on a keeper going to the chests for food anyway."""
    load = toStore(farmer)
    return sum(load.values()) >= FARMER_HAUL or ("dew" in load and keeps(farmer, "keeper") and foodCarried(farmer) < FOOD_LOW)


def stockOf(game, wanted):
    """{storage chest spot: amount} of what's in wanted (a set of material ids) in each storage chest that has some."""
    stock = {}
    for spot in dwellerwork.storageChests(game):
        amount = sum(stack.amount for stack in game.grid[spot][2] if getattr(stack, "materialId", None) in wanted)
        if amount:
            stock[spot] = amount
    return stock


def takeFromChest(game, chestSpot, farmer, wanted, most):
    """Up to most of what's in wanted out of the chest, into the farmer's pockets."""
    chest = game.grid[chestSpot][2]
    for stack in [thing for thing in chest if getattr(thing, "materialId", None) in wanted]:
        if most <= 0:
            break
        taken = min(most, stack.amount)
        stack.amount -= taken
        most -= taken
        farmer.materials[stack.materialId] = farmer.materials.get(stack.materialId, 0) + taken
        if stack.amount <= 0:
            chest.remove(stack)
    game.change = True


def fetch(game, position, farmer, wanted, most):
    """To the nearest storage chest with some of wanted, and take up to most. None if no chest has any."""
    stock = stockOf(game, wanted)
    if not stock:
        return None
    chestSpot = dwellerwork.nearest(game, position, list(stock))
    if chestSpot in game.neighbors(position):
        takeFromChest(game, chestSpot, farmer, wanted, most)
        return position
    return dwellerwork.walkTo(game, position, farmer, chestSpot)


# ---------------------------------------------------------------- the turn

def farmTurn(game, position, farmer):
    """A farmer's turn (see the top of this file). Returns where it ends up, or None with nothing to do."""
    if keeps(farmer, "keeper"):
        moved = keeperTurn(game, position, farmer)
        if moved is not None:
            return moved
    if keeps(farmer, "grower"):
        grubs = dwellerwork.grubsHere(game)
        if foodCarried(farmer):  # (a grower helps with a starving grub, with the herbs it has picked)
            moved = feedTurn(game, position, farmer, grubs, onlyStarving=True)
            if moved is not None:
                return moved
        if needsMoreField(game, farmer, len(grubs)):
            dwellerbuilding.farmhousePlan(game, position, farmer)
        return fieldTurn(game, position, farmer)
    return None


def keeperTurn(game, position, farmer):
    farmer.grubTarget = None  # (it picks again: walkToGrub)
    grubs = dwellerwork.grubsHere(game)
    moved = feedTurn(game, position, farmer, grubs)
    if moved is not None:
        return moved
    ready = [spot for spot, grub in grubs if grub.dewReady and not skipped(game, farmer, grub) and not takenBy(game, farmer, grub)]
    if ready:
        spot = dwellerwork.nearest(game, position, ready)
        if withinReach(game, position, spot):
            dwellerwork.collectDew(game.grid[spot][2], farmer)
            farmer.grubTarget = None
            return position
        return walkToGrub(game, position, farmer, spot)
    moved = dewgrubs.herdTurn(game, position, farmer)
    if moved is not None:
        return moved
    if foodCarried(farmer) < FOOD_LOW:
        moved = fetch(game, position, farmer, FOODS, FOOD_KEPT - foodCarried(farmer))
        if moved is not None:
            return moved
    pens = keeperPens(game, farmer)
    if pens:
        gate = dwellerwork.nearest(game, position, [pen["gate"] for pen in pens])
        if dwellers.distance(game, position, gate) > dewgrubs.REACH:
            return dwellerwork.walkTo(game, position, farmer, gate)
        return position  # (waiting by its pens)
    return None


def keeperPens(game, farmer):
    """The pens this keeper looks after: the farm's pens dealt out in turn among the keepers on the floor."""
    pens = dewgrubs.pensOf(farmer)
    keepers = sorted(id(dweller) for _, dweller in dwellers.cityDwellers(game) if roleOf(dweller) == "keeper")
    if roleOf(farmer) != "keeper" or id(farmer) not in keepers:
        return pens
    place = keepers.index(id(farmer))
    return [pen for index, pen in enumerate(pens) if index % len(keepers) == place]


def hunger(grub):
    return getattr(grub, "hunger", 0)


def isKeeper(dweller):
    """A farmer that feeds the grubs (a keeper, or a farmer from before the roles)."""
    return roleOf(dweller) in ("keeper", None) and getattr(dweller, "work", None) == "farm"


def keeperCount(game, farmer=None):
    """The keepers on the floor. farmer: one taking its turn (off the map while it does, so counted here)."""
    keepers = {id(dweller) for _, dweller in dwellers.cityDwellers(game) if isKeeper(dweller)}
    if farmer is not None and isKeeper(farmer):
        keepers.add(id(farmer))
    return len(keepers)


def caredFor(game, grubs, farmer=None):
    """The ids of the grubs ([(spot, grub)]) the keepers look after: KEEPER_HERD a keeper (one keeper's worth with
    none left), the grown ones first, then the young nearest grown, then the least hungry. The rest starve."""
    most = KEEPER_HERD * max(1, keeperCount(game, farmer))
    ranked = sorted(grubs, key=lambda pair: (not getattr(pair[1], "grown", True), -getattr(pair[1], "growth", 0),
                                             hunger(pair[1])))
    return {id(grub) for _, grub in ranked[:most]}


def withinReach(game, position, spot):
    return dewgrubs.withinReach(game, position, spot)


def skipped(game, farmer, grub):
    """Is this a grub the keeper couldn't get to lately?"""
    return getattr(farmer, "skippedGrubs", {}).get(id(grub), -1) > game.turnCount


def takenBy(game, farmer, grub):
    """Is another keeper already going to this grub?"""
    return any(other is not farmer and getattr(other, "grubTarget", None) == id(grub) for _, other in dwellers.cityDwellers(game))


def walkToGrub(game, position, farmer, spot):
    """A step toward the grub on spot (it's this keeper's to see to now); one it can't get to, it leaves for
    SKIP_TURNS."""
    farmer.grubTarget = id(game.grid[spot][2])
    newPosition = dwellerwork.walkTo(game, position, farmer, spot)
    if newPosition == position and getattr(farmer, "stuckTurns", 0) >= dwellerwork.GIVE_UP_TURNS - 1:
        farmer.skippedGrubs = {grubId: until for grubId, until in getattr(farmer, "skippedGrubs", {}).items()
                               if until > game.turnCount}
        farmer.skippedGrubs[farmer.grubTarget] = game.turnCount + SKIP_TURNS
        farmer.grubTarget = None
        farmer.stuckTurns = 0
    return newPosition


def feedTurn(game, position, farmer, grubs, onlyStarving=False):
    """Feed the nearest hungry grub the keepers look after (onlyStarving: starving), or fetch food for one. None if
    there's no feeding to do."""
    cared = caredFor(game, grubs, farmer)
    hungry = [(spot, grub) for spot, grub in grubs if id(grub) in cared and not grub.dewReady and hunger(grub) >= HUNGRY_TURNS
              and not skipped(game, farmer, grub) and not takenBy(game, farmer, grub)]
    if not hungry:
        return None
    starving = [spot for spot, grub in hungry if hunger(grub) >= STARVING_TURNS]
    if onlyStarving:
        hungry = starving
    else:
        mine = set().union(*[set(pen["inside"]) for pen in keeperPens(game, farmer)])
        hungry = starving or [spot for spot, grub in hungry if grub.pen <= mine and grub.pen] or [spot for spot, _ in hungry]
    if not hungry:
        return None
    if foodCarried(farmer) == 0:
        return fetch(game, position, farmer, FOODS, FOOD_KEPT)
    spot = dwellerwork.nearest(game, position, hungry)
    if not withinReach(game, position, spot):
        return walkToGrub(game, position, farmer, spot)
    grub = game.grid[spot][2]
    wasGrown = grub.grown
    dwellerwork.feed(grub, farmer)
    farmer.grubTarget = None
    if wasGrown:
        dewgrubs.maybeGiveBirth(game, spot, grub)
    return position


# ---------------------------------------------------------------- the fields

def fieldTiles(game):
    """Every field tile of the farms on this floor and the rest of their farmhouses (nothing wild sprouts there:
    plants.step's noBirth)."""
    tiles = set()
    for _, dweller in dwellers.cityDwellers(game):
        tiles |= set(getattr(dweller, "fields", ()))
        for farmhouse in getattr(dweller, "farmhouses", ()):
            tiles |= set(farmhouse["inside"])
    return tiles


def isCityCrop(tile):
    return tile[0] == PLANT and len(tile) > 2 and getattr(tile[2], "cityCrop", False)


def isRipeCrop(tile):
    """A city crop in one of its ripe stages."""
    return isCityCrop(tile) and tile[2].ready


def sow(game, spot, kind):
    """A new sprout of the city's crop on spot."""
    crop = plants.Plant(kind, planted=True)
    crop.cityCrop = True
    game.grid[spot] = [PLANT, game.grid[spot][1], crop]
    game.change = True


def pickCrop(game, spot, farmer):
    """The farmer picks the ripe crop on spot: what it gives goes in its pockets, and the tile is bare."""
    crop = game.grid[spot][2]
    stage = crop.pick()
    for materialId, amount in loot.rollPick(crop, stage) if stage else ():
        farmer.materials[materialId] = farmer.materials.get(materialId, 0) + amount
    game.grid[spot] = [FLOOR, game.grid[spot][1]]
    game.change = True


def shortOfSeeds(game, farmer, kind, bare):
    """Has the farm fewer seeds of this kind (on the farmer and in the chests) than its bare tiles need plus
    SEEDS_KEPT?"""
    have = dwellerwork.carrying(farmer).get(seedOf(kind), 0) + sum(stockOf(game, {seedOf(kind)}).values())
    return have < bare + SEEDS_KEPT


def myFields(game, farmer):
    """{tile: kind} of the fields this grower tends: the farm's crops dealt out in turn among the growers on the
    floor; with more growers than crops, the growers on a crop each take a share of its tiles (in order, so each
    share is mostly one patch). Every field, for a farmer from before the roles."""
    fields = getattr(farmer, "fields", {})
    crops = sorted(set(fields.values()))
    growers = sorted(id(dweller) for _, dweller in dwellers.cityDwellers(game) if roleOf(dweller) == "grower")
    if roleOf(farmer) != "grower" or id(farmer) not in growers or not crops:
        return dict(fields)
    place = growers.index(id(farmer))
    if len(growers) <= len(crops):
        mine = {crop for index, crop in enumerate(crops) if index % len(growers) == place}
        return {spot: kind for spot, kind in fields.items() if kind in mine}
    crop = crops[place % len(crops)]
    sharers = [index for index in range(len(growers)) if index % len(crops) == place % len(crops)]
    tiles = sorted(spot for spot, kind in fields.items() if kind == crop)
    share = sharers.index(place)
    chunk = -(-len(tiles) // len(sharers))
    return {spot: crop for spot in tiles[share * chunk:(share + 1) * chunk]}


def fieldJob(game, position, farmer):
    """("weed" | "pick" | "sow" | "fetch", tile, kind) for the grower's next job in its fields, or None."""
    fields = myFields(game, farmer)
    weeds = [spot for spot in fields if game.grid[spot][0] == PLANT and not isCityCrop(game.grid[spot])]
    if weeds:
        spot = dwellerwork.nearest(game, position, weeds)
        return ("weed", spot, fields[spot])
    bare = [spot for spot, kind in fields.items() if game.grid[spot][0] == FLOOR and plants.canGrow(kind, spot, game.grid, game.rooms)]
    bareOf = {}
    for spot in bare:
        bareOf[fields[spot]] = bareOf.get(fields[spot], 0) + 1
    ripe = []
    for spot, kind in fields.items():
        tile = game.grid[spot]
        if isRipeCrop(tile):
            want = "seed" if shortOfSeeds(game, farmer, kind, bareOf.get(kind, 0)) else "harvest"
            if tile[2].stage == want or tile[2].lastStage:
                ripe.append(spot)
    sowable = [spot for spot in bare if spot != position and dwellerwork.carrying(farmer).get(seedOf(fields[spot]), 0) > 0]
    if ripe or sowable:
        spot = dwellerwork.nearest(game, position, ripe + sowable)
        return ("pick" if spot in ripe else "sow", spot, fields[spot])
    for spot in bare:  # bare tiles and no seed of their kind: fetch some
        if stockOf(game, {seedOf(fields[spot])}):
            return ("fetch", spot, fields[spot])
    return None


def fieldTurn(game, position, farmer):
    job = fieldJob(game, position, farmer)
    if job is None:
        return None
    action, spot, kind = job
    if action == "fetch":
        return fetch(game, position, farmer, {seedOf(kind)}, SEEDS_KEPT)
    if spot not in game.neighbors(position) and spot != position:
        return dwellerwork.walkTo(game, position, farmer, spot)
    if action == "weed":
        game.grid[spot] = [FLOOR, game.grid[spot][1]]  # pulled up: nothing kept
        game.change = True
    elif action == "pick":
        pickCrop(game, spot, farmer)
    else:
        dwellerwork.drop(farmer, {seedOf(kind): 1})
        sow(game, spot, kind)
    return position


def needsMoreField(game, farmer, grubCount):
    """Has the farm fewer field tiles than FIELD_TILES_PER_GRUB a grub (and FIELD_TILES_PER_GROWER a grower)?"""
    fields = getattr(farmer, "fields", None)
    if fields is None:
        return False
    growers = sum(1 for _, dweller in dwellers.cityDwellers(game)
                  if roleOf(dweller) in ("grower", None) and getattr(dweller, "fields", None) is fields)
    return len(fields) < min(FIELD_TILES_PER_GRUB * grubCount, FIELD_TILES_PER_GROWER * max(1, growers))


# ---------------------------------------------------------------- starving

def starveTurn(game):
    """A turn of hunger for every Dew Grub on the floor (not while its Dew is waiting): one that has gone
    STARVE_TURNS without food starves."""
    for spot, grub in dwellerwork.grubsHere(game):
        if grub.dewReady:
            continue
        grub.hunger = hunger(grub) + 1
        if grub.hunger >= STARVE_TURNS:
            if game.grid[spot][1] == 1:
                game.addPopup("A Dew Grub starved", spot)
            game.killEnemy(spot, None)
