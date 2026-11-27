import math

from cruel.inventory import items
from cruel.world import dwellerfarming
from cruel.world import dwellers
from cruel.world import dwellerwork
from cruel.world import expansion
from cruel.world import farmhouses
from cruel.world import metropolis
from cruel.world import mineshafts
from cruel.world import organizers
from cruel.world import quelling
from cruel.world import wall

"""
The Dwellers building on their city's works floors (mineshafts.py): a new storehouse when every storage chest is full
and on a farm a new pen when the pens are full (dewgrubs.py) or a new farmhouse (farmhouses.py) when the farm needs
more crops (dwellerfarming.py), wherever there's room for them.

A building is planned on a site (findSite; a worker that finds none waits SEARCH_AGAIN_TURNS to look again): a box near the shaft (its middle within SITE_REACH, outside the
clearing) of open floor or rock the miners could break, clear of the fields, the shaft, the lamps and other
buildings, with a step of ground outside its door that you can walk to from the shaft. Its margin, the ground
within mineshafts.CLEARANCE of it, can't have another building in it, and its rock is dug out with the site's, so
nothing blocks the building's doors. Of the sites that fit, the
one nearest the shaft with the least rock to dig wins. The box's edge is its walls (a storehouse's or a pen fence)
but for its two doors: one in the middle of the side facing the shaft, one in the middle of the far side (a back
door, with a way dug from it to ground you can walk to, BACK_WAY_MOST long at most); a storehouse has
STOREHOUSE_CHESTS chests along its back wall.

The plan is shared by the floor's workers (worker.plans). Up to BUILDERS of them (never a farm's keepers) build it at once (and any worker
with something to store and no chest with room for it), one piece a turn, standing beside it (a wall or chest is
put in from inside the building or its doorway, beside it or diagonal to it, so no builder walls itself out and the
corners can be reached):
  1. dig out the rock on the site, nearest the door first (MINE_SWING a swing, no more than the rock's hardness);
  2. put up the walls;
  3. put in the chests.
A piece with someone standing on it waits. When it's done, a pen joins the farm's pens (worker.pens) and the plan
is crossed off.
"""

BUILDERS = 2                # workers putting up a building at once
SITE_REACH = 24             # how far from the shaft a new building's middle can be
BACK_WAY_MOST = 12          # a back door's way out to open ground is dug this far at most
SEARCH_AGAIN_TURNS = 200    # a worker that found no site for a building doesn't look again for this long
WALLS = {"storehouse": wall.ShopWall, "pen": wall.PenFence, "farmhouse": wall.FarmhouseWall}


def shaftOf(game, position):
    """The works floor's shaft (where new buildings go near), or position off a works floor."""
    side = getattr(game, "sideFloor", None)
    return side[1] if side else position


# ---------------------------------------------------------------- the site

def shape(rowLength, left, top, width, height, toward):
    """A building's box with its top-left corner at (left, top): its walls, inside, door (in the middle of the side
    facing toward, a (column, row)), the tile outside the door, its back door (in the middle of the far side) and
    the tile outside that, and the inside tiles along its back wall."""
    box = {column + row * rowLength for row in range(top, top + height) for column in range(left, left + width)}
    walls = {spot for spot in box if spot % rowLength in (left, left + width - 1) or spot // rowLength in (top, top + height - 1)}
    middleColumn, middleRow = left + width // 2, top + height // 2
    towardColumn, towardRow = toward
    if abs(towardColumn - middleColumn) > abs(towardRow - middleRow):
        step = -1 if towardColumn < middleColumn else 1
        door = (left if step < 0 else left + width - 1) + middleRow * rowLength
        backDoor = (left + width - 1 if step < 0 else left) + middleRow * rowLength
        backColumn = left + width - 2 if step < 0 else left + 1
        back = [backColumn + (middleRow + offset) * rowLength for offset in (-1, 1)]
    else:
        step = -rowLength if towardRow < middleRow else rowLength
        door = middleColumn + (top if step < 0 else top + height - 1) * rowLength
        backDoor = middleColumn + (top + height - 1 if step < 0 else top) * rowLength
        backRow = top + height - 2 if step < 0 else top + 1
        back = [middleColumn + offset + backRow * rowLength for offset in (-1, 1)]
    return {"box": box, "walls": walls - {door, backDoor}, "inside": frozenset(box - walls), "door": door,
            "outside": door + step, "backDoor": backDoor, "backOutside": backDoor - step, "back": back}


def plannedTiles(plans):
    tiles = set()
    for plan in plans:
        tiles |= plan["box"] | plan["margin"] | set(plan.get("backWay", ()))
    return tiles


def lampTiles(game):
    """The lamps on this floor and the walls they hang on (nothing is built over either)."""
    return set(metropolis.wallLampsHere(game)) | dwellerwork.lampWalls(game)


def findSite(game, position, worker, width, height, round_=False):
    """The best site for a width x height building (see the top of this file; round_: a farmhouse, its box width
    across): its shape plus "margin" (the ring round it) and "rock" (its tiles to dig out). None if nothing fits."""
    rowCount = len(game.grid) // game.rowLength
    shaft = shaftOf(game, position)
    shaftColumn, shaftRow = shaft % game.rowLength, shaft // game.rowLength
    reach = expansion.walkingDistances(game, shaft, SITE_REACH * 4)
    keepOff = set(getattr(worker, "fields", {})) | plannedTiles(getattr(worker, "plans", [])) | lampTiles(game) | \
        {shaft, game.playerPositionFlat}
    best = None
    for middleRow in range(shaftRow - SITE_REACH, shaftRow + SITE_REACH + 1):
        for middleColumn in range(shaftColumn - SITE_REACH, shaftColumn + SITE_REACH + 1):
            away = math.hypot(middleColumn - shaftColumn, middleRow - shaftRow)
            if away > SITE_REACH or away < mineshafts.CLEARING_RADIUS + max(width, height):
                continue
            left, top = middleColumn - width // 2, middleRow - height // 2
            if left < 2 or top < 2 or left + width > game.rowLength - 2 or top + height > rowCount - 2:
                continue
            site = farmhouses.shape(game.rowLength, middleColumn, middleRow, (shaftColumn, shaftRow)) if round_ else \
                shape(game.rowLength, left, top, width, height, (shaftColumn, shaftRow))
            if site["outside"] not in reach:
                continue
            rock = siteRock(game, site, keepOff)
            if rock is None:
                continue
            margin = mineshafts.withClearance(game.rowLength, left, top, width, height) - site["box"]
            if not marginFits(game, margin, keepOff - set(getattr(worker, "fields", {}))):
                continue
            rock |= {spot for spot in margin if clearable(game.grid[spot])}
            backWay = wayOut(game, site["backOutside"], reach, keepOff | site["box"])
            if backWay is None:
                continue
            site["backWay"] = backWay
            rock |= {spot for spot in backWay if clearable(game.grid[spot])}
            score = away + 3 * len(rock)
            if best is None or score < best[0]:
                site["margin"], site["rock"] = margin, rock
                best = (score, site)
    return best[1] if best else None


def wayOut(game, start, reach, keepOff):
    """The tiles from start (outside a back door) to ground in reach (that you can walk to from the shaft), through
    floor, rock a miner could break or wild plants, round keepOff: start's included, BACK_WAY_MOST long at most. [] if start is
    already in reach; None if there's no way."""
    if start in reach:
        return []
    cameFrom, frontier = {start: None}, [start]
    for _ in range(BACK_WAY_MOST):
        nextFrontier = []
        for spot in frontier:
            for near in game.neighbors(spot):
                if near in cameFrom or near in keepOff:
                    continue
                if near in reach:
                    way, step = [], spot
                    while step is not None:
                        way.append(step)
                        step = cameFrom[step]
                    return way
                tile = game.grid[near]
                if tile[0] == dwellerwork.FLOOR or clearable(tile):
                    cameFrom[near] = spot
                    nextFrontier.append(near)
        frontier = nextFrontier
    return None


def clearable(tile):
    """Something a builder clears off a site: rock it can break, or a wild plant (it picks it; a planted crop it
    leaves)."""
    return dwellerwork.mineable(tile) or quelling.isWild(tile)


def siteRock(game, site, keepOff):
    """The rock and wild plants to clear off a site, or None if the site has anything else on it (a unit, a chest,
    a crop, a city wall...)."""
    rock = set()
    for spot in site["box"]:
        tile = game.grid.get(spot)
        if tile is None or spot in keepOff:
            return None
        if clearable(tile):
            rock.add(spot)
        elif tile[0] != dwellerwork.FLOOR:
            return None
    return rock


def marginFits(game, margin, keepOff):
    """Nothing round a site that it would block or join onto: no city wall, chest, shaft or planned building."""
    for spot in margin:
        tile = game.grid.get(spot)
        if tile is None or spot in keepOff or tile[0] in (dwellerwork.CHEST, metropolis.MINESHAFT):
            return False
        if tile[0] == dwellerwork.WALL and len(tile) > 2 and isinstance(tile[2], wall.CityBuildingWall):
            return False
    return True


# ---------------------------------------------------------------- planning

def plansOf(worker):
    return getattr(worker, "plans", None)


def newPlan(game, position, worker, kind, width, height):
    plans = plansOf(worker)
    if game.turnCount < getattr(worker, "searchAgainAt", 0):
        return None
    site = findSite(game, position, worker, width, height, round_=kind == "farmhouse")
    if site is None:
        worker.searchAgainAt = game.turnCount + SEARCH_AGAIN_TURNS
        return None
    site["kind"] = kind
    site["chests"] = {"storehouse": site.get("back"), "farmhouse": [site.get("chest")]}.get(kind) or []
    if kind == "farmhouse":
        site["crop"] = farmhouses.pickCrop(getattr(worker, "fields", None))
    plans.append(site)
    return site


def storehousePlan(game, position, worker):
    """The storehouse being built, or a new one planned (every chest is full). None if this worker can't build or
    there's no site for one."""
    plans = plansOf(worker)
    if plans is None:
        return None
    planned = next((plan for plan in plans if plan["kind"] == "storehouse"), None)
    if planned is not None:
        return planned
    return newPlan(game, position, worker, "storehouse", mineshafts.STOREHOUSE_SIZE, mineshafts.STOREHOUSE_SIZE)


def penPlan(game, position, worker):
    """The pen being built, or a new one planned."""
    plans = plansOf(worker)
    if plans is None:
        return None
    planned = next((plan for plan in plans if plan["kind"] == "pen"), None)
    if planned is not None:
        return planned
    return newPlan(game, position, worker, "pen", mineshafts.PEN_WIDTH, mineshafts.PEN_HEIGHT)


def farmhousePlan(game, position, worker):
    """The farmhouse being built, or a new one planned."""
    plans = plansOf(worker)
    if plans is None:
        return None
    planned = next((plan for plan in plans if plan["kind"] == "farmhouse"), None)
    if planned is not None:
        return planned
    across = 2 * farmhouses.HALF + 1
    return newPlan(game, position, worker, "farmhouse", across, across)


def planFor(game, worker):
    """The building this worker puts up now: the first plan, if it's already building or fewer than BUILDERS are.
    A farm's keepers never build (they have the grubs to feed: dwellerfarming.py)."""
    plans = plansOf(worker)
    if not plans or getattr(worker, "farmRole", None) == "keeper":
        worker.job = None
        return None
    if getattr(worker, "job", None) == "build":
        return plans[0]
    builders = sum(1 for _, dweller in dwellers.cityDwellers(game) if getattr(dweller, "job", None) == "build")
    if builders >= BUILDERS:
        return None
    worker.job = "build"
    return plans[0]


# ---------------------------------------------------------------- building

def isBuilt(game, plan, spot):
    """Is this wall or chest of the plan in place?"""
    tile = game.grid[spot]
    if spot in plan["chests"]:
        return tile[0] == dwellerwork.CHEST
    return tile[0] == dwellerwork.WALL and len(tile) > 2 and isinstance(tile[2], WALLS[plan["kind"]])


def pieces(game, plan):
    """What's left to do, in order: ("dig", spot)s (rock to break and wild plants to pick, on the site, its back
    way and its margin), then ("wall", spot)s, then ("chest", spot)s."""
    toDig = sorted((spot for spot in plan["box"] | set(plan.get("backWay", ())) | set(plan.get("margin", ()))
                    if spot in game.grid and clearable(game.grid[spot])),
                   key=lambda spot: dwellers.distance(game, plan["outside"], spot))
    if toDig:
        return [("dig", spot) for spot in toDig]
    walls = [("wall", spot) for spot in plan["walls"] if not isBuilt(game, plan, spot)]
    if walls:
        return walls
    return [("chest", spot) for spot in plan["chests"] if not isBuilt(game, plan, spot)]


def build(game, position, worker, plan):
    """A turn at putting up the plan: a piece of it if it's beside one, else a step toward one. Returns where it
    ends up, or None if there's nothing it can do now (the plan is done, or what's left is waiting on someone)."""
    left = pieces(game, plan)
    if not left:
        finish(game, worker, plan)
        return None
    action, spot = left[0]
    if action != "dig":  # (walls and chests go up in any order: the nearest free one)
        free = [(action, spot) for action, spot in left if game.grid[spot][0] == dwellerwork.FLOOR]
        if not free:
            return None
        action, spot = min(free, key=lambda piece: dwellers.distance(game, position, piece[1]))
    if position == spot:  # standing where it goes: step off it first
        off = [near for near in game.neighbors(position) if organizers.passable(game.grid[near]) and near not in plan["walls"]]
        return organizers.moveTo(game, position, off[0]) if off else None
    if action == "dig" and spot not in game.neighbors(position):
        return dwellerwork.walkTo(game, position, worker, spot)
    if action != "dig" and position not in standingSpots(game, plan, spot):
        standing = [near for near in standingSpots(game, plan, spot) if organizers.passable(game.grid[near])]
        if not standing:
            return None
        return dwellerwork.walkTo(game, position, worker, min(standing, key=lambda near: dwellers.distance(game, position, near)))
    if action == "dig" and quelling.isWild(game.grid[spot]):  # (a wild plant: picked, like a farmer picks a crop)
        if getattr(worker, "materials", None) is None:
            worker.materials = {}
        dwellerfarming.pickCrop(game, spot, worker)
    elif action == "dig":
        rock = game.grid[spot][2]
        game.chip(spot, position)
        rock.takeDamage(dwellerwork.MINE_SWING, game.tileSize)
        if rock.hp <= 0:
            game.grid[spot] = [dwellerwork.FLOOR, game.grid[spot][1]]
    elif action == "wall":
        game.grid[spot] = [dwellerwork.WALL, game.grid[spot][1], WALLS[plan["kind"]]()]
    else:
        game.grid[spot] = [dwellerwork.CHEST, game.grid[spot][1], items.StorageChest()]
    game.change = True
    return position


def around(game, spot):
    """The up to eight tiles round spot (diagonals too; no wrapping round the map's edges)."""
    column = spot % game.rowLength
    return [spot + columnStep + rowStep * game.rowLength for rowStep in (-1, 0, 1) for columnStep in (-1, 0, 1)
            if (columnStep or rowStep) and 0 <= column + columnStep < game.rowLength
            and spot + columnStep + rowStep * game.rowLength in game.grid]


def standingSpots(game, plan, spot):
    """Where a builder stands to put in the wall or chest at spot: inside the building or in its doorway, beside it
    or diagonal to it (so it never walls itself out, and it can reach the corners)."""
    return [near for near in around(game, spot) if near in plan["inside"] or near == plan["door"]]


def finish(game, worker, plan):
    """The plan is built: a pen joins the farm's pens; the plan is crossed off."""
    plans = plansOf(worker)
    if plan in plans:
        plans.remove(plan)
    if plan["kind"] == "farmhouse" and getattr(worker, "fields", None) is not None:  # its floor laid, its plots the farm's
        farmhouses.layFloor(game.rooms, plan["inside"], plan["crop"])
        for bed in plan["beds"]:
            worker.fields[bed] = plan["crop"]
        if getattr(worker, "farmhouses", None) is not None:
            worker.farmhouses.append({key: plan[key] for key in ("box", "walls", "inside", "door", "backDoor", "beds", "chest", "crop")})
    if plan["kind"] == "pen" and getattr(worker, "pens", None) is not None:
        worker.pens.append({"fence": set(plan["walls"]) | {plan["door"], plan["backDoor"]}, "inside": plan["inside"],
                            "gate": plan["door"], "backGate": plan["backDoor"]})
    worker.job = None
