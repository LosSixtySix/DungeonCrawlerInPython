import math
import random

from cruel.entities import enemies
from cruel.world import dewgrubs
from cruel.world import dwellers
from cruel.world import dwellerfarming
from cruel.world import dwellerwork
from cruel.world import expansion
from cruel.world import followers
from cruel.world import livingfloors
from cruel.world import metropolis
from cruel.world import mineshafts
from cruel.world import occupancy
from cruel.world import organizers

"""
The Dweller Queen and her court (design sheet: https://claude.ai/artifact/8crUvVgcwiWWNoooJmPKyY).

  The Queen       one to a city, in the middle of the Queen's Chamber (metropolis.placeCourt). A large unit (2 x 2,
                  enemies.DwellerQueen) that never moves. Each turn she hits one thing within her reach of her body
                  that she can see: you, once she's hostile (she saw you do something hostile, or you hurt her), or
                  else the nearest enemy of the city (dwellers.isCityEnemy). Hurting her is hostile, like hurting
                  any Dweller.
  Royal Guards    stronger guards in royal colors (enemies.RoyalGuard) at posts round her. They take a guard's turn
                  but never go more than their leash from their post (dwellers.withinLeash).
  Pupating        Royal Guards are never hatched. While there are fewer than metropolis.ROYAL_GUARDS (pupae count),
                  each turn there's a PUPATE_CHANCE that the city guard nearest the Queen pupates where it stands
                  (one at a time): it becomes a Royal Pupa (enemies.RoyalPupa) that can't move or fight, and
                  PUPA_TURNS turns on comes out a Royal Guard (takeTurn), which goes to a free post beside the Queen.
  Dew carriers    metropolis.CARRIERS of a city's citizens are set aside (work "dew") to feed the Queen Dew from the
                  farm (carrierTurn). Empty-handed in the city, one walks to the farm's shaft and climbs down
                  (livingfloors.climb), but only AT_ONCE are down on the farm at a time (Queen.carriersAway: so
                  they don't crowd the farmers at the storehouse); on the farm it takes up to CARRY Dew from the storehouse chests, climbs back
                  up, walks to the Queen and feeds it all to her (queen.dew). Finding no Dew there, it climbs back up
                  and goes about the city for REST_TURNS before trying again (so they don't crowd the farm). On any
                  other floor it climbs back up. It deals with the city's enemies like any citizen first.
  Eggs            fed DEW_TO_LAY Dew, the Queen lays CLUTCH eggs (enemies.DwellerEgg) on the free tiles touching her
                  (layEggs). A calm citizen near one (EGG_CALL_REACH) that has no other work comes for it, lifts it
                  (held, off the map, like a farmer carrying a grub), carries it to a free nest in a hatchery
                  (metropolis.nestsIn) and sets it down there (citizenTurn). With every nest taken, eggs wait where
                  they were laid. A citizen killed carrying one drops it (dropHeld).
  Hatching        HATCH_TURNS turns after it's put in a nest, an egg hatches into what the city needs most
                  (neediest): each kind of unit scores how far short the city is of what it wants (Queen.court's
                  "wanted", as a share of it), weighted: guards +0.5 for each enemy of the city on the city, its
                  mine or its farm (up to 3); miners x1.5 while the mine's chests hold less than PLENTY, x0.5 with
                  plenty (farmers the same with food); carriers x2 (the Queen depends on them); citizens x0.8. The
                  highest wins (a tie: at random); with nothing short, a citizen. The works floors count from their
                  census (recordCensus, taken every CENSUS_TURNS turns as each takes its turn). A hatchling guard
                  goes to the post with the fewest guards, a citizen or carrier to a house, and a miner or farmer
                  walks to the city's shaft for its works, climbs down and joins the workers there (joinWorks).
  Farm hands      a city (Queen or not) keeps its farm running: every CENSUS_TURNS turns, if the farm's census says
                  it's short of farmers (farmersWanted: a keeper for every dwellerfarming.KEEPER_HERD grubs and a
                  grower for every dwellerfarming.FIELD_TILES_PER_GROWER field tiles, at least one of each), counting
                  those already on their way, it sends one idle citizen down (sendFarmHands: the one nearest the
                  farm's shaft, keeping CITY_CITIZENS_KEPT citizens in the city). It goes like a hatchling would
                  (joinTurn), and keeps the grubs if the herd needs more keepers, or else grows crops (joinWorks).
                  With no farmer left down there to learn from, it takes up what the farm's census kept of its fields,
                  pens and plans (game.workShared).
"""

PUPATE_CHANCE = 0.02
PUPA_TURNS = 40
CARRY = 10                  # Dew a carrier takes from the farm each trip
REST_TURNS = 50             # a carrier that found no Dew on the farm waits this long in the city before going again
AT_ONCE = 2                 # carriers down on the farm at a time...
AWAY_LIMIT = 300            # ...not counting one that went down this long ago and hasn't come back (it may have died there)
DEW_TO_LAY = 30             # fed this much Dew, the Queen lays...
CLUTCH = 5                  # ...this many eggs
HATCH_TURNS = 50            # an egg hatches this long after it's put in a nest
EGG_CALL_REACH = 30         # a citizen this close to a waiting egg comes for it
CLAIM_TURNS = 60            # a citizen coming for an egg that hasn't got it in this long lets another come instead
CENSUS_TURNS = 10           # a works floor counts itself this often (recordCensus)
PLENTY = 60                 # a works floor's chests hold plenty with this much ore (mine) or food (farm)
CITY_CITIZENS_KEPT = 5      # the city never sends its last this many citizens down to the farm
WORKS_JOBS = {"miner": "mine", "farmer": "farm"}


def isQueen(unit):
    return getattr(unit, "role", None) == "queen"


def isRoyal(unit):
    return getattr(unit, "royal", False)


def isPupa(unit):
    return getattr(unit, "role", None) == "pupa"


def isEgg(unit):
    return getattr(unit, "role", None) == "egg"


def courtOf(game):
    """(her anchor, the Queen) on this floor, or None."""
    return next(((spot, unit) for spot, unit in dwellers.cityDwellers(game) if isQueen(unit)), None)


# ---------------------------------------------------------------- the Queen's turn

def sees(game, anchor, queen, spot):
    """Can the Queen see spot from her body: right beside it, or within her vision with a clear line from one of
    her tiles?"""
    if game.reachOf(queen, anchor, spot) <= 1:
        return True
    return any(dwellers.distance(game, tile, spot) <= queen.visionRange and game.lineOfSight(tile, spot)
               for tile in game.footprint(anchor, queen.size))


def youInReach(game, anchor, queen):
    """Are you within her reach and in her sight, with her hostile to you?"""
    return not game.peaceful and queen.hostile and game.reachOf(queen, anchor, game.playerPositionFlat) <= queen.reach \
        and sees(game, anchor, queen, game.playerPositionFlat)


def enemyInReach(game, anchor, queen):
    """(position, enemy) of the nearest enemy of the city within her reach that she can see, or None."""
    found = []
    for spot in set(game.EnemyPositions) | getattr(game, "movedEnemies", set()):
        tile = game.grid.get(spot)
        if not (tile and tile[0] == 5 and len(tile) > 2 and dwellers.isCityEnemy(tile[2])):
            continue
        reach = game.reachOf(queen, anchor, spot)
        if reach <= queen.reach and sees(game, anchor, queen, spot):
            found.append((reach, spot, tile[2]))
    if not found:
        return None
    _, spot, enemy = min(found, key=lambda item: item[0])
    return spot, enemy


def queenTurn(game, anchor, queen):
    """One action for the Queen: she never moves. She hits you if you're within reach and she's hostile, otherwise
    the nearest enemy of the city within reach. Returns her anchor."""
    followers.crownMood(game, queen)  # (wearing the Pheromone Crown, she's hostile to you too)
    if youInReach(game, anchor, queen):
        game.hitPlayer(queen, anchor)
        return anchor
    found = enemyInReach(game, anchor, queen)
    if found is not None:
        enemySpot, enemy = found
        expansion.attack(game, anchor, queen, enemy, enemySpot)  # (it fights back)
    return anchor


# ---------------------------------------------------------------- Royal Guards and pupating

def royalCount(game):
    """Royal Guards and pupae on the floor."""
    return sum(1 for _, unit in dwellers.cityDwellers(game) if isRoyal(unit) or isPupa(unit))


def freePost(game, queen):
    """A post round the Queen with no Royal Guard (or pupa) going to it, or her first post."""
    units = dwellers.cityDwellers(game)
    claimed = {unit.home for _, unit in units if isRoyal(unit)} | {unit.post for _, unit in units if isPupa(unit)}
    free = [post for post in queen.royalPosts if post not in claimed]
    return free[0] if free else (queen.royalPosts[0] if queen.royalPosts else queen.anchor)


def stepCourt(game):
    """The court's turn (gameManager.enemyTurn and awayTurn). On a works floor, it counts itself for the city now
    and then (recordCensus). In a city with a Queen: fed enough Dew, she lays (layEggs); and short of Royal Guards
    maybe a guard pupates (pupate). Returns the pupa, or None."""
    if not dwellers.onDwellerFloor(game):
        return None
    if getattr(game, "sideFloor", None) is not None:
        recordCensus(game)
        return None
    sendFarmHands(game)
    court = courtOf(game)
    if court is None:
        return None
    anchor, queen = court
    layEggs(game, anchor, queen)
    return pupate(game, anchor, queen)


def pupate(game, anchor, queen):
    """Short of Royal Guards, with no guard already pupating, maybe (PUPATE_CHANCE) the city guard nearest the
    Queen pupates where it stands. Returns the pupa, or None."""
    units = dwellers.cityDwellers(game)
    if any(isPupa(unit) for _, unit in units) or royalCount(game) >= metropolis.ROYAL_GUARDS:
        return None
    if random.random() >= PUPATE_CHANCE:
        return None
    guards = [(spot, unit) for spot, unit in units if unit.role == "guard" and not isRoyal(unit)]
    if not guards:
        return None
    spot, guard = min(guards, key=lambda found: game.reachOf(queen, anchor, found[0]))
    pupa = enemies.RoyalPupa(PUPA_TURNS, freePost(game, queen))
    pupa.hostile = guard.hostile
    if occupancy.sharedTiles(game).get(spot) is guard:
        occupancy.sharedTiles(game)[spot] = pupa
    else:
        game.grid[spot][2] = pupa
    game.change = True
    return pupa


def takesTurn(unit):
    """Does this unit take its turn here (takeTurn) rather than as a Dweller?"""
    return isPupa(unit) or isEgg(unit)


def takeTurn(game, position, unit):
    """One action for a Royal Pupa or an egg. A pupa waits, and when its time is up comes out a Royal Guard
    headed for its post. An egg waits; in its nest it counts down, and hatches (hatch). Returns (where it is, the
    unit there now)."""
    if isEgg(unit):
        if unit.nest != position or unit.hatchIn is None:
            return position, unit
        unit.hatchIn -= 1
        if unit.hatchIn > 0:
            return position, unit
        game.change = True
        return position, hatch(game, unit, neediest(game, unit.court))
    unit.turnsLeft -= 1
    if unit.turnsLeft > 0:
        return position, unit
    royal = enemies.RoyalGuard()
    royal.home = royal.goal = unit.post if unit.post is not None else position
    royal.hostile = unit.hostile
    game.change = True
    return position, royal


# ---------------------------------------------------------------- the Dew carriers

def shaftsHere(game, kind=None):
    """Where this floor's mineshafts are (of kind, if given: the works kind each goes to)."""
    return [spot for spot, tile in game.grid.items() if tile[0] == metropolis.MINESHAFT and len(tile) > 2
            and (kind is None or getattr(tile[2], "kind", None) == kind)]


def climbOrWalk(game, position, carrier, shaftSpot):
    """Beside the shaft, the carrier climbs it; otherwise it takes a step toward it."""
    if shaftSpot in game.neighbors(position):
        livingfloors.climb(game, position, carrier, shaftSpot)
        return position
    return dwellerwork.walkTo(game, position, carrier, shaftSpot, reach=dwellers.FAR_PATH_REACH)


def carriersAway(game, dwellerQueen):
    """{carrier: the turn it went down}: the Queen's carriers down on the farm now (forgetting any gone longer than
    AWAY_LIMIT)."""
    away = getattr(dwellerQueen, "carriersAway", None)
    if away is None:
        away = dwellerQueen.carriersAway = {}
    for carrier in [carrier for carrier, went in away.items() if game.turnCount - went > AWAY_LIMIT]:
        del away[carrier]
    return away


def feed(dwellerQueen, carrier):
    """The carrier feeds the Queen all the Dew it carries. Returns how much."""
    dew = carrier.materials.pop("dew", 0)
    dwellerQueen.dew = getattr(dwellerQueen, "dew", 0) + dew
    return dew


def carrierTurn(game, position, carrier):
    """A Dew carrier's turn (see the top of this file). Returns where it ends up, or None with nothing to do (no
    Queen, or no farm shaft: it wanders like any citizen)."""
    dew = carrier.materials.get("dew", 0)
    side = getattr(game, "sideFloor", None)
    if side is None:  # the city
        court = courtOf(game)
        if court is None:
            return None
        anchor, dwellerQueen = court
        away = carriersAway(game, dwellerQueen)
        away.pop(carrier, None)  # (it's back)
        if dew:
            if game.reachOf(dwellerQueen, anchor, position) <= 1:
                feed(dwellerQueen, carrier)
                game.change = True
                return position
            return dwellerwork.walkTo(game, position, carrier, anchor, reach=dwellers.FAR_PATH_REACH)
        farmShafts = shaftsHere(game, "farm")
        if not farmShafts or game.turnCount < getattr(carrier, "restUntil", 0) or len(away) >= AT_ONCE:
            return None
        moved = climbOrWalk(game, position, carrier, dwellerwork.nearest(game, position, farmShafts))
        if livingfloors.leaving(carrier):
            away[carrier] = game.turnCount
        return moved
    kind, shaftSpot = side
    if kind == "farm" and dew < CARRY:
        fetched = dwellerfarming.fetch(game, position, carrier, {"dew"}, CARRY - dew)
        if fetched is not None:
            return fetched
        if not dew:  # (none in the chests: back up, and it rests a while before trying again)
            carrier.restUntil = game.turnCount + REST_TURNS
    return climbOrWalk(game, position, carrier, shaftSpot)


# ---------------------------------------------------------------- eggs

def layEggs(game, anchor, queen):
    """Fed DEW_TO_LAY Dew, the Queen lays CLUTCH eggs on the free floor tiles touching her (as many as there's room
    for; with none free she waits). Returns how many she laid."""
    if getattr(queen, "dew", 0) < DEW_TO_LAY:
        return 0
    free = [spot for tile in game.footprint(anchor, queen.size) for spot in game.neighbors(tile)
            if game.reachOf(queen, anchor, spot) == 1 and game.grid[spot][0] == 0 and spot != game.playerPositionFlat]
    free = list(dict.fromkeys(free))  # (in order, once each)
    if not free:
        return 0
    queen.dew -= DEW_TO_LAY
    laid = 0
    for spot in free[:CLUTCH]:
        dewgrubs.placeUnit(game, spot, enemies.DwellerEgg(queen.court))
        laid += 1
    return laid


def heldEggs(game):
    """[(citizen, egg)] for the eggs being carried right now on this floor."""
    return [(dweller, dweller.heldEgg) for _, dweller in dwellers.cityDwellers(game) if getattr(dweller, "heldEgg", None)]


def freeNests(game, court):
    """The nests with no egg (or anyone) in them and no carried egg going to them."""
    going = {egg.nestTarget for _, egg in heldEggs(game)}
    return [nest for nest in court.get("nests", ()) if nest not in going and nest in game.grid
            and organizers.passable(game.grid[nest])]


def claimed(game, egg):
    """Is a citizen already coming for this egg (lately)?"""
    return egg.carrier is not None and game.turnCount - (egg.claimedAt or 0) < CLAIM_TURNS


def waitingEggs(game):
    """[(position, egg)] for the eggs not in a nest yet."""
    return [(spot, unit) for spot, unit in dwellers.cityDwellers(game) if isEgg(unit) and unit.nest != spot]


def anyEggsWaiting(game):
    """Are there eggs not in a nest on this floor? Worked out once a turn (every calm citizen asks), so it can be
    out of date within the turn: whoever acts on it looks again (fetchEgg)."""
    key = (mineshafts.floorKey(game), game.turnCount)
    cache = game.__dict__.setdefault("eggsWaiting", {})
    if key not in cache:
        cache.clear()
        cache[key] = bool(waitingEggs(game))
    return cache[key]


def citizenTurn(game, position, citizen):
    """What a calm citizen does for the Queen before going about its day: a hatchling headed for a works floor goes
    there (joinTurn); one carrying an egg takes it to its nest; one coming for an egg goes and lifts it; one near a
    waiting egg, with a nest free for it, comes for it. Returns where it ends up, or None (nothing to do)."""
    if getattr(citizen, "joining", None):
        return joinTurn(game, position, citizen)
    if getattr(game, "sideFloor", None) is not None:
        return None
    if getattr(citizen, "heldEgg", None) is not None:
        return carryEgg(game, position, citizen)
    egg = getattr(citizen, "eggTarget", None)
    if egg is not None:
        return fetchEgg(game, position, citizen, egg)
    if not anyEggsWaiting(game):
        return None
    eggs = [(spot, egg) for spot, egg in waitingEggs(game) if not claimed(game, egg)
            and dwellers.distance(game, position, spot) <= EGG_CALL_REACH]
    if not eggs or not freeNests(game, eggs[0][1].court):
        return None
    spot, egg = min(eggs, key=lambda found: dwellers.distance(game, position, found[0]))
    egg.carrier, egg.claimedAt = citizen, game.turnCount
    citizen.eggTarget = egg
    return fetchEgg(game, position, citizen, egg)


def fetchEgg(game, position, citizen, egg):
    """A step toward the egg it's coming for, or, beside it, lifts it (off the map: it carries it now)."""
    where = next((spot for spot, unit in waitingEggs(game) if unit is egg), None)
    if where is None or egg.carrier is not citizen:  # (gone, hatched, or someone else has it)
        citizen.eggTarget = None
        return None
    egg.claimedAt = game.turnCount
    if where in game.neighbors(position):
        nests = freeNests(game, egg.court)
        if not nests:
            return position  # (it waits beside it for a nest to come free)
        dewgrubs.takeUnit(game, where, egg)
        egg.nestTarget = dwellerwork.nearest(game, position, nests)
        citizen.heldEgg, citizen.eggTarget = egg, None
        return position
    return dwellerwork.walkTo(game, position, citizen, where, reach=dwellers.FAR_PATH_REACH)


def carryEgg(game, position, citizen):
    """A step toward the nest its egg is going to, or, beside it, sets it down there to hatch."""
    egg = citizen.heldEgg
    nest = egg.nestTarget
    if nest is None or not organizers.passable(game.grid[nest]):  # (someone's in it: another nest)
        nests = freeNests(game, egg.court)
        egg.nestTarget = nest = dwellerwork.nearest(game, position, nests) if nests else None
        if nest is None:
            return position
    if nest in game.neighbors(position):
        dewgrubs.placeUnit(game, nest, egg)
        egg.nest, egg.hatchIn, egg.nestTarget, egg.carrier = nest, HATCH_TURNS, None, None
        citizen.heldEgg = None
        game.change = True
        return position
    return dwellerwork.walkTo(game, position, citizen, nest, reach=dwellers.FAR_PATH_REACH)


def dropHeld(game, position, dweller):
    """A Dweller died on position: an egg it was carrying is set down there (or beside it)."""
    egg = getattr(dweller, "heldEgg", None)
    if egg is None:
        return
    dweller.heldEgg = None
    egg.nestTarget = egg.carrier = None
    free = [spot for spot in [position] + game.neighbors(position) if organizers.passable(game.grid[spot])]
    if free:
        dewgrubs.placeUnit(game, free[0], egg)


# ---------------------------------------------------------------- hatching

def census(game):
    """How many of each kind of unit this floor has, how many enemies of the city are on it, and what its storehouse
    chests hold ({"guard", "citizen", "carrier", "miner", "farmer", "enemies", "stock", "food"}); and for a farm,
    its "grubs", "keepers", "growers" and "fieldTiles"."""
    counts = dict.fromkeys(("guard", "citizen", "carrier", "miner", "farmer", "enemies", "grubs", "keepers", "growers"), 0)
    counts["fieldTiles"] = 0
    for _, unit in occupancy.allUnits(game):
        if dwellers.isCityEnemy(unit):
            counts["enemies"] += 1
            continue
        if getattr(unit, "role", None) == "grub":
            counts["grubs"] += 1
        kind = jobOf(unit)
        if kind in counts:
            counts[kind] += 1
        if kind == "farmer" and unit.work == "farm":
            counts["keepers" if dwellerfarming.roleOf(unit) == "keeper" else "growers"] += 1
            counts["fieldTiles"] = max(counts["fieldTiles"], len(getattr(unit, "fields", {}) or {}))
    chests = [game.grid[spot][2] for spot in dwellerwork.storageChests(game)]
    counts["stock"] = sum(getattr(thing, "amount", 0) for chest in chests for thing in chest)
    counts["food"] = sum(getattr(thing, "amount", 0) for chest in chests for thing in chest
                         if getattr(thing, "materialId", None) in dwellerfarming.FOODS)
    return counts


def jobOf(unit):
    """What kind of unit this is to the city: "guard" (not royal), "carrier", "miner", "farmer", "citizen" (with
    no work, or on its way to it: a hatchling joining a works floor counts as what it will be), or its role."""
    if not dwellers.isDweller(unit) or followers.isFollower(unit):
        return None
    if unit.role == "guard":
        return None if isRoyal(unit) else "guard"
    work = getattr(unit, "joining", None) or unit.work
    return {"dew": "carrier", "mine": "miner", "farm": "farmer"}.get(work, unit.role)


def recordCensus(game):
    """A works floor counts itself for its city every CENSUS_TURNS turns (game.workCensus: {floor key: census})."""
    key = mineshafts.floorKey(game)
    records = game.__dict__.setdefault("workCensus", {})
    if key not in records or game.turnCount % CENSUS_TURNS == 0:
        records[key] = census(game)
        worker = next((unit for _, unit in dwellers.cityDwellers(game) if getattr(unit, "work", None) in ("mine", "farm")), None)
        if worker is not None:  # (what its workers share, for a newcomer when none are left: joinWorks)
            shared = {name: getattr(worker, name) for name in ("plans", "fields", "pens", "farmhouses") if hasattr(worker, name)}
            sharedOf(game)[key] = shared


def sharedOf(game):
    """{works floor key: what its workers share (plans, fields, pens, farmhouses)} (saved with the game)."""
    if getattr(game, "workShared", None) is None:
        game.workShared = {}
    return game.workShared


# ---------------------------------------------------------------- farm hands

def farmersWanted(record):
    """How many farmers a farm needs, from its census: a keeper for every KEEPER_HERD grubs and a grower for every
    FIELD_TILES_PER_GROWER field tiles, at least one of each."""
    keepers = max(1, math.ceil(record.get("grubs", 0) / dwellerfarming.KEEPER_HERD))
    growers = max(1, math.ceil(record.get("fieldTiles", 0) / dwellerfarming.FIELD_TILES_PER_GROWER))
    return keepers + growers


def idleCitizen(unit):
    """A citizen with nothing else to do: no work, not on its way to any, calm, not carrying or fetching an egg,
    not following you."""
    return getattr(unit, "role", None) == "citizen" and unit.work is None and not getattr(unit, "joining", None) \
        and not unit.hostile and not followers.isFollower(unit) and getattr(unit, "heldEgg", None) is None \
        and getattr(unit, "eggTarget", None) is None


def sendFarmHands(game):
    """Every CENSUS_TURNS turns in a city: if its farm is short of farmers (see the top of this file), one idle
    citizen sets off down to it. Returns who was sent, or None."""
    if game.turnCount % CENSUS_TURNS != 0:
        return None
    records = getattr(game, "workCensus", {})
    for shaft in shaftsHere(game, "farm"):
        key = (game.level, shaft)
        record = records.get(key)
        if record is None:
            continue
        units = dwellers.cityDwellers(game)
        onTheWay = sum(1 for _, unit in units if getattr(unit, "joining", None) == "farm")
        onTheWay += sum(1 for unit, _ in livingfloors.arrivals(game).get(key, []) if getattr(unit, "joining", None) == "farm")
        if record["farmer"] + onTheWay >= farmersWanted(record):
            continue
        idle = [(spot, unit) for spot, unit in units if idleCitizen(unit)]
        citizens = sum(1 for _, unit in units if getattr(unit, "role", None) == "citizen" and unit.work is None
                       and not followers.isFollower(unit))
        if not idle or citizens <= CITY_CITIZENS_KEPT:
            continue
        spot, citizen = min(idle, key=lambda found: dwellers.distance(game, found[0], shaft))
        citizen.joining = "farm"
        citizen.goal = None
        return citizen
    return None

def needScores(counts, wanted):
    """{kind: score} from counts (what the city has, its works floors included: census) and wanted (what it wants).
    See the top of this file."""
    def short(kind):
        want = wanted.get(kind, 0)
        return max(0, want - counts.get(kind, 0)) / want if want else 0
    def stocked(amount):
        return 0.5 if amount >= PLENTY else 1.5
    return {"guard": short("guard") + 0.5 * min(3, counts.get("enemies", 0)),
            "miner": short("miner") * stocked(counts.get("ore", 0)),
            "farmer": short("farmer") * stocked(counts.get("food", 0)),
            "carrier": short("carrier") * 2,
            "citizen": short("citizen") * 0.8}


def cityCounts(game):
    """The city's census with its works floors' added (their last census), carriers down on the farm and anyone on
    their way up or down a shaft; "ore" is what the mine's chests hold, "food" what the farm's do."""
    counts = census(game)
    counts["ore"] = counts["food"] = 0
    records = getattr(game, "workCensus", {})
    for spot in shaftsHere(game):
        record = records.get((game.level, spot))
        if record is None:
            continue
        for kind in ("carrier", "miner", "farmer", "enemies"):  # (its guards are its own: the city wants its posts manned)
            counts[kind] += record[kind]
        if game.grid[spot][2].kind == "mine":
            counts["ore"] += record["stock"]
        else:
            counts["food"] += record["food"]
    for key, waiting in livingfloors.arrivals(game).items():
        if mineshafts.floorNumber(key) == game.level:
            for unit, _ in waiting:
                kind = jobOf(unit)
                if kind in counts:
                    counts[kind] += 1
    return counts


def neediest(game, court):
    """The kind of unit the city needs most (see the top of this file)."""
    scores = needScores(cityCounts(game), court.get("wanted", {}))
    best = max(scores.values())
    if best <= 0:
        return "citizen"
    return random.choice(sorted(kind for kind, score in scores.items() if score == best))


def hatch(game, egg, kind):
    """The unit an egg hatches into, given its home (see the top of this file)."""
    homes = egg.court.get("homes") or [egg.nest]
    if kind == "guard":
        hatchling = enemies.DwellerGuard()
        posts = egg.court.get("posts") or [egg.nest]
        guarded = [unit.home for _, unit in dwellers.cityDwellers(game) if jobOf(unit) == "guard"]
        hatchling.home = min(posts, key=lambda post: (guarded.count(post), dwellers.distance(game, egg.nest, post)))
    else:
        hatchling = enemies.DwellerCitizen()
        hatchling.home = random.choice(homes)
        if kind == "carrier":
            hatchling.work = "dew"
        elif kind in WORKS_JOBS:
            hatchling.joining = WORKS_JOBS[kind]
    hatchling.goal = hatchling.home
    hatchling.farWalk = True
    return hatchling


def joinTurn(game, position, hatchling):
    """A hatchling headed for a works floor: in the city it walks to the shaft for it and climbs down; on that
    floor it joins the workers (joinWorks); on any other it climbs back up."""
    kind = hatchling.joining
    side = getattr(game, "sideFloor", None)
    if side is None:
        shafts = shaftsHere(game, kind)
        if not shafts:
            hatchling.joining = None  # (the city has no such works: it stays a citizen)
            return None
        return climbOrWalk(game, position, hatchling, dwellerwork.nearest(game, position, shafts))
    if side[0] == kind:
        joinWorks(game, position, hatchling)
        return position
    return climbOrWalk(game, position, hatchling, side[1])


def joinWorks(game, position, hatchling):
    """A newcomer (a hatchling, or a citizen sent to help) arriving on its works floor becomes one of its workers:
    what they share (plans, and on a farm its fields, pens and farmhouses) it shares (from the last census, if none
    are left: game.workShared), and its home is theirs. On a farm it keeps the grubs if they need more keepers (one
    for every KEEPER_HERD), or else grows crops."""
    kind = hatchling.joining
    workers = [unit for _, unit in dwellers.cityDwellers(game) if getattr(unit, "work", None) == kind]
    hatchling.joining = None
    hatchling.work = kind
    hatchling.farWalk = False
    shared = {name: getattr(workers[0], name) for name in ("plans", "fields", "pens", "farmhouses") if hasattr(workers[0], name)} \
        if workers else sharedOf(game).get(mineshafts.floorKey(game), {})
    hatchling.home = workers[0].home if workers else position
    hatchling.plans = shared.get("plans", [])
    if kind == "farm":
        hatchling.fields = shared.get("fields", {})
        hatchling.pens = shared.get("pens", [])
        hatchling.farmhouses = shared.get("farmhouses", [])
        keepers = sum(1 for unit in workers if dwellerfarming.roleOf(unit) == "keeper")
        grubs = sum(1 for _, unit in dwellers.cityDwellers(game) if getattr(unit, "role", None) == "grub")
        keepersWanted = max(1, math.ceil(grubs / dwellerfarming.KEEPER_HERD))
        hatchling.farmRole = "keeper" if keepers < keepersWanted else "grower"
    record = getattr(game, "workCensus", {}).get(mineshafts.floorKey(game))
    if record is not None:  # (counted at once, so the city doesn't send another before the next census)
        record[jobOf(hatchling)] = record.get(jobOf(hatchling), 0) + 1
        if kind == "farm":
            record[hatchling.farmRole + "s"] = record.get(hatchling.farmRole + "s", 0) + 1
