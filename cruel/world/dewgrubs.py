import random

from cruel.entities import enemies
from cruel.world import dwellerbuilding
from cruel.world import dwellerfarming
from cruel.world import dwellers
from cruel.world import dwellerwork
from cruel.world import occupancy
from cruel.world import organizers

"""
The Dew Grubs of a city's farm floor (enemies.DewGrub, mineshafts.py) and how the farmers keep them.

Young. Each time a grown grub is fed, if another grown grub that's been fed (not yet hungry:
dwellerfarming.HUNGRY_TURNS) is within MATE_RANGE of it, there's a BIRTH_CHANCE it gives birth to a young one, on a
free tile of its pen (or beside it, with no free tile; a farmer then takes it in). Nothing else holds the herd back:
it can grow past what its keepers can feed, and they look after dwellerfarming.KEEPER_HERD grubs each and let the
rest starve (dwellerfarming.caredFor), so the herd settles at what the keepers can feed. A grub that
isn't fed starves (dwellerfarming.STARVE_TURNS). A young grub eats like any other, but its feedings make it grow: after FEEDINGS_TO_GROW
it's grown, and only then does it make Dew.

Pens. There's no hard limit on a pen, but the farmers want every pen to hold PEN_FEWEST to PEN_MOST grubs (the farm's pens are shared by its farmers:
farmer.pens, each {"fence", "inside", "gate"}; a grub's pen is its inside tiles). A farmer with nothing more pressing
moves one grub at a time, the first of these that needs doing:
  - a grub out of its pen (pushed out, or born outside it) goes back to it, or to a pen with room if it's full.
  - a pen with more than PEN_MOST: one of its grubs goes to the pen with the fewest that has room.
  - a pen with fewer than PEN_FEWEST: if the pens with more than PEN_FEWEST can spare enough to bring it up to
    PEN_FEWEST, one comes from the fullest of them; if not, a lone grub leaves it for a pen with some in it.
When every pen is full (PEN_MOST), the farmers build a new one (dwellerbuilding.py), wherever there's room.

Only one farmer at a time moves grubs between pens (any farmer may take one that's out of its pen back, or one
out of a pen with more than PEN_MOST). Moving a
grub, the farmer walks up to it, lifts it out (from up to REACH tiles away: over the fence, so a crowded pen is no
trouble) (farmer.heldGrub: it's off the map while it's carried), takes
it to the pen it's going to and sets it down on a free tile of it beside the farmer: that's its pen now. A farmer
that can't get any further for CARRY_GIVE_UP turns sets it down where it is (another farmer takes it on later). A
farmer killed while carrying one drops it (dropHeld).
"""

BIRTH_CHANCE = 0.2          # a grown grub gives birth when it's fed this often...
MATE_RANGE = 3              # ...if another fed grown grub is this close to it
FEEDINGS_TO_GROW = 4        # plants a young grub eats to grow up
PEN_FEWEST = 2              # the farmers want at least this many grubs in a pen...
PEN_MOST = 6                # ...and no more than this
BIRTH_NOTICE_RANGE = 8      # you see "A young Dew Grub" when one is born this close to you
CARRY_GIVE_UP = 12          # turns a farmer moving a grub can be stuck before it gives up
REACH = 3                   # how far (across or diagonally) a farmer reaches to lift a grub out or set it down


# ---------------------------------------------------------------- young

def growOn(grub):
    """A young grub has been fed: after FEEDINGS_TO_GROW it's grown."""
    grub.growth += 1
    if grub.growth >= FEEDINGS_TO_GROW:
        grub.growUp()


def hasMate(game, spot, grub):
    """Is another grown grub that's been fed (not yet hungry) within MATE_RANGE of the grub on spot?"""
    return any(other is not grub and getattr(other, "grown", True)
               and dwellerfarming.hunger(other) < dwellerfarming.HUNGRY_TURNS
               and dwellers.distance(game, spot, otherSpot) <= MATE_RANGE
               for otherSpot, other in dwellerwork.grubsHere(game))


def maybeGiveBirth(game, spot, grub):
    """A grown grub on spot was just fed: now and then (BIRTH_CHANCE) it gives birth to a young one, if a fed grown
    grub is near it (hasMate). Returns where the young one is, or None."""
    if not getattr(grub, "grown", True) or not hasMate(game, spot, grub) or random.random() >= BIRTH_CHANCE:
        return None
    free = [tile for tile in grub.pen if tile in game.grid and organizers.passable(game.grid[tile])]
    if not free:
        free = [tile for tile in game.neighbors(spot) if organizers.passable(game.grid[tile])]
    if not free:
        return None
    birthSpot = min(free, key=lambda tile: dwellers.distance(game, spot, tile))
    young = enemies.DewGrub(grown=False)
    young.pen = grub.pen
    young.home = birthSpot
    placeUnit(game, birthSpot, young)
    if dwellers.distance(game, birthSpot, game.playerPositionFlat) < BIRTH_NOTICE_RANGE:
        game.addPopup("A young Dew Grub", birthSpot)
    game.change = True
    return birthSpot


def placeUnit(game, spot, unit):
    """Puts a unit on spot (an item pile or plant there stays underneath it). It takes its next turn next turn."""
    tile = game.grid[spot]
    if tile[0] != dwellerwork.FLOOR:
        game.enemyOccupiedItemSpaces[spot] = tile
    game.grid[spot] = [dwellerwork.ENEMY, tile[1], unit]
    for positions in (game.EnemyPositions, getattr(game, "movedEnemies", set())):
        positions.add(spot)


def takeUnit(game, spot, unit):
    """Takes unit off spot and off the map (what it stood on is left there, and anyone sharing the space stays).
    Returns it."""
    first = occupancy.primaryAt(game, spot) is unit
    occupancy.lift(game, spot, unit)
    if first:
        for positions in (game.EnemyPositions, getattr(game, "movedEnemies", set())):
            positions.discard(spot)
        occupancy.leave(game, spot)
    game.change = True
    return unit


# ---------------------------------------------------------------- pens

def pensOf(farmer):
    return getattr(farmer, "pens", None) or []


def heldGrubs(game):
    """The grubs being carried right now: [(farmer, grub)]."""
    return [(dweller, dweller.heldGrub) for _, dweller in dwellers.cityDwellers(game) if getattr(dweller, "heldGrub", None)]


def headcounts(grubs, pens, held=()):
    """{pen inside: grubs that live there or are being taken there}. grubs: [(spot, grub)] on the map; held: grubs
    being carried."""
    counts = {frozenset(pen["inside"]): 0 for pen in pens}
    for grub in [grub for _, grub in grubs] + list(held):
        home = grub.headedTo or grub.pen
        if home in counts:
            counts[home] += 1
    return counts


def chosenGrubs(game):
    """The grubs a farmer is on its way to pick up ({id})."""
    return {id(dweller.movingGrub) for _, dweller in dwellers.cityDwellers(game) if getattr(dweller, "movingGrub", None)}


def isBeingLed(game, grub):
    """Is a farmer on its way to pick this grub up? (It stays put for it.)"""
    return getattr(grub, "headedTo", None) is not None and id(grub) in chosenGrubs(game)


def grubToMove(game, farmer):
    """(grub, the pen it should go to) for the first grub that needs moving (see the top of this file), or None."""
    pens = pensOf(farmer)
    chosen = chosenGrubs(game)
    grubs = dwellerwork.grubsHere(game)
    farmerSpot = next((spot for spot, dweller in dwellers.cityDwellers(game) if dweller is farmer), None) or 0
    for _, grub in grubs:  # a farmer that was coming for one is gone: it's no longer headed anywhere
        if grub.headedTo is not None and id(grub) not in chosen:
            grub.headedTo = None
    counts = headcounts(grubs, pens, [grub for _, grub in heldGrubs(game)])
    free = [(spot, grub) for spot, grub in grubs if id(grub) not in chosen]

    def withRoom(besides=None):
        roomy = [inside for inside, count in counts.items() if count < PEN_MOST and inside != besides]
        return min(roomy, key=lambda inside: counts[inside]) if roomy else None

    def oneFrom(inside):  # (the one nearest the farmer)
        here = [(spot, grub) for spot, grub in free if grub.pen == inside and spot in inside]
        return min(here, key=lambda pair: dwellers.distance(game, farmerSpot, pair[0]))[1] if here else None

    for spot, grub in free:  # out of its pen
        if spot not in grub.pen:
            target = grub.pen if counts.get(grub.pen, PEN_MOST + 1) <= PEN_MOST else withRoom(grub.pen)
            if target is not None:
                return grub, target
    for inside, count in counts.items():  # too many in a pen
        if count > PEN_MOST:
            target, grub = withRoom(inside), oneFrom(inside)
            if target is not None and grub is not None:
                return grub, target
    spare = sum(count - PEN_FEWEST for count in counts.values() if count > PEN_FEWEST)
    for inside, count in counts.items():  # too few in a pen
        if count >= PEN_FEWEST:
            continue
        if spare >= PEN_FEWEST - count:
            grub = oneFrom(max(counts, key=lambda other: counts[other]))
            if grub is not None:
                return grub, inside
        elif count == 1:  # a lone grub joins a pen that has some already (so it isn't just as lonely there)
            joinable = [other for other, otherCount in counts.items()
                        if other != inside and PEN_FEWEST - 1 <= otherCount < PEN_MOST]
            grub = oneFrom(inside)
            if joinable and grub is not None:
                return grub, min(joinable, key=lambda other: counts[other])
    return None


def overfull(game, farmer, inside):
    """Has this pen more than PEN_MOST grubs?"""
    counts = headcounts(dwellerwork.grubsHere(game), pensOf(farmer), [grub for _, grub in heldGrubs(game)])
    return counts.get(inside, 0) > PEN_MOST


def grubInPen(game, grub):
    """Is the grub on a tile of its own pen?"""
    return any(spot in grub.pen for spot, other in dwellerwork.grubsHere(game) if other is grub)


def needsNewPen(game, farmer):
    """Every pen is full (PEN_MOST, or more)."""
    counts = headcounts(dwellerwork.grubsHere(game), pensOf(farmer), [grub for _, grub in heldGrubs(game)])
    return bool(counts) and all(count >= PEN_MOST for count in counts.values())


def herdTurn(game, position, farmer):
    """A farmer's turn at moving grubs between pens (see the top of this file). Returns where it ends up, or None if
    there's no grub to move."""
    if not pensOf(farmer):
        return None
    if getattr(farmer, "heldGrub", None) is None and getattr(farmer, "movingGrub", None) is None:
        job = grubToMove(game, farmer)
        if job is not None and chosenGrubs(game) and grubInPen(game, job[0]) and not overfull(game, farmer, job[0].pen):
            job = None  # (one farmer at a time moves grubs between pens: the others feed them)
        if job is None:
            if needsNewPen(game, farmer):
                dwellerbuilding.penPlan(game, position, farmer)
            return None
        farmer.movingGrub, job[0].headedTo = job[0], job[1]
        farmer.carryStuck = 0
    return moveGrub(game, position, farmer)


def letGo(farmer):
    """The farmer stops moving its grub (if it's carrying it, see setDown first)."""
    grub = getattr(farmer, "movingGrub", None)
    if grub is not None:
        grub.headedTo = None
    farmer.movingGrub = None
    farmer.heldGrub = None


def setDown(game, farmer, spot):
    """The farmer sets the grub it carries down on spot (a free tile): in the pen it was taking it to, that's its
    pen now."""
    grub = farmer.heldGrub
    if grub.headedTo is not None and spot in grub.headedTo:
        grub.pen = grub.headedTo
    grub.home = spot
    placeUnit(game, spot, grub)
    letGo(farmer)


def dropHeld(game, position, dweller):
    """A Dweller died on position: a grub it was carrying is set down there (or beside it)."""
    if getattr(dweller, "heldGrub", None) is None:
        return
    spots = [position] + game.neighbors(position)
    free = [spot for spot in spots if organizers.passable(game.grid[spot])]
    if free:
        setDown(game, dweller, free[0])


def moveGrub(game, position, farmer):
    """A step at moving its grub: to it and pick it up, or carry it to its new pen and set it down there."""
    grub = farmer.movingGrub
    target = grub.headedTo
    if getattr(farmer, "heldGrub", None) is None:
        grubSpot = next((spot for spot, dweller in dwellers.cityDwellers(game) if dweller is grub), None)
        if grubSpot is None or target is None:  # it's dead
            letGo(farmer)
            return None
        if grubSpot in target:  # (it got there some other way)
            grub.pen = target
            letGo(farmer)
            return None
        if not withinReach(game, position, grubSpot):  # another from the same pen it can reach will do
            chosen = chosenGrubs(game)
            reachable = [(spot, other) for spot, other in dwellerwork.grubsHere(game) if other.pen == grub.pen
                         and spot in grub.pen and id(other) not in chosen and withinReach(game, position, spot)]
            if reachable and grubSpot in grub.pen:
                grub.headedTo = None
                grubSpot, grub = reachable[0]
                grub.headedTo, farmer.movingGrub = target, grub
        if withinReach(game, position, grubSpot):  # (lifted out over the fence)
            farmer.heldGrub = takeUnit(game, grubSpot, grub)
            return position
        return stepOrGiveUp(game, position, farmer, grubSpot)
    into = [spot for spot in target if withinReach(game, position, spot) and organizers.passable(game.grid[spot])]
    if into:  # (set down over the fence)
        setDown(game, farmer, min(into, key=lambda spot: dwellers.distance(game, position, spot)))
        return position
    goal = min(target, key=lambda spot: (not organizers.passable(game.grid[spot]), dwellers.distance(game, position, spot)))
    return stepOrGiveUp(game, position, farmer, goal)


def withinReach(game, position, spot):
    """Is spot within REACH tiles of position, across or diagonally (a farmer lifts grubs over a pen's fence)?"""
    rowLength = game.rowLength
    return max(abs(position % rowLength - spot % rowLength), abs(position // rowLength - spot // rowLength)) <= REACH


def stepOrGiveUp(game, position, farmer, goal):
    """A step toward goal; a farmer stuck for CARRY_GIVE_UP turns gives up (setting down what it carries)."""
    newPosition = dwellerwork.walkTo(game, position, farmer, goal)
    if newPosition != position:
        farmer.carryStuck = 0
        return newPosition
    farmer.carryStuck = getattr(farmer, "carryStuck", 0) + 1
    if farmer.carryStuck >= CARRY_GIVE_UP:
        if farmer.heldGrub is not None:
            free = [spot for spot in game.neighbors(position) if organizers.passable(game.grid[spot])]
            if not free:
                return position
            setDown(game, farmer, free[0])
        letGo(farmer)
    return position
