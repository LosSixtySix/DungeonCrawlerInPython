import random

from cruel.world import dewgrubs
from cruel.world import dwellers
from cruel.world import expansion
from cruel.world import livingfloors
from cruel.world import mineshafts
from cruel.world import occupancy
from cruel.world import organizers
from cruel.world import peddler
from cruel.world import queen

"""
The Pheromone Crown (relics.py: "pheromones", dropped by the Dweller Queen) and the followers it wins you.

  Wearing it   every Dweller is hostile to you (crownMood): one that wasn't turns hostile, and when you take the
               crown off, those go back to how they were. (The crown also gives +2 Defense and +0.5 speed.)
  Converting   each turn you wear it, with room for another follower (MOST_FOLLOWERS), there's a CONVERT_CHANCE
               that a Dweller beside you (a citizen, noble or guard, Royal Guards too) becomes your follower
               (stepConvert). It drops whatever work it had.
  A follower   stays near you (within KEEP_CLOSE), and goes after anything hostile to you that it can see within
               FIGHT_REACH of you: hostile Dwellers and every other monster but a calm trader. It never hurts you;
               walking into it swaps places with it (swapWithYou), and interacting with it does nothing (Shift +
               interact still hits it). The city treats it as an enemy (dwellers.isCityEnemy). It comes with you
               when you change floors (bringAlong), set down on the free tile nearest you. Your followers are
               player.followers; one that dies is forgotten.
"""

MOST_FOLLOWERS = 1      # how many followers you can have (more may come later)
CONVERT_CHANCE = 0.05   # each turn, while you wear the crown, beside a Dweller that could follow you
CONVERTIBLE = ("citizen", "noble", "guard")
KEEP_CLOSE = 2          # a follower stays this close to you...
FIGHT_REACH = 6         # ...and fights what it sees within this of you


def wearsCrown(game):
    return game.player.hasEffect("pheromones")


def isFollower(unit):
    return getattr(unit, "follower", False)


def followersOf(player):
    """Your followers (player.followers), made if an old save has none."""
    if getattr(player, "followers", None) is None:
        player.followers = []
    return player.followers


# ---------------------------------------------------------------- the crown and the city

def crownMood(game, dweller):
    """Wearing the crown, a Dweller that wasn't hostile to you turns hostile (marked crownHostile); taken off, those
    calm down again. Followers, eggs, pupae and grubs don't change."""
    if isFollower(dweller) or getattr(dweller, "role", None) in ("egg", "pupa", "grub"):
        return
    if wearsCrown(game):
        if not dweller.hostile:
            dwellers.turnHostile(game, dweller, None)
            dweller.crownHostile = True
    elif getattr(dweller, "crownHostile", False):
        dweller.hostile = dweller.crownHostile = False
        dweller.sawYouAt = dweller.enemyAt = None
        dweller.toldGuard = False


def canFollow(unit):
    return dwellers.isDweller(unit) and not isFollower(unit) and unit.role in CONVERTIBLE \
        and getattr(unit, "size", 1) == 1


def stepConvert(game):
    """Each turn you wear the crown with room for another follower: maybe (CONVERT_CHANCE) a Dweller beside you
    becomes your follower. Returns it, or None."""
    if game.peaceful or not wearsCrown(game) or len(followersOf(game.player)) >= MOST_FOLLOWERS:
        return None
    beside = [(spot, unit) for spot in game.neighbors(game.playerPositionFlat)
              for unit in occupancy.unitsAt(game, spot) if canFollow(unit)]
    if not beside or random.random() >= CONVERT_CHANCE:
        return None
    spot, unit = random.choice(beside)
    convert(game, spot, unit)
    return unit


def convert(game, spot, unit):
    """unit, on spot, becomes your follower: calm, with no work, home or leash, and anything it carried set down."""
    dewgrubs.dropHeld(game, spot, unit)
    queen.dropHeld(game, spot, unit)
    unit.heldGrub = unit.heldEgg = unit.movingGrub = unit.eggTarget = None
    unit.follower = True
    unit.hostile = unit.crownHostile = unit.toldGuard = False
    unit.sawYouAt = unit.enemyAt = unit.goal = unit.target = None
    unit.work = unit.joining = None
    unit.home = None
    unit.leash = None
    unit.floorKey = mineshafts.floorKey(game)
    followersOf(game.player).append(unit)
    game.addPopup(f"The {unit.name} follows you", spot)
    game.change = True


# ---------------------------------------------------------------- a follower's turn

def hostileToYou(game, unit):
    """Would this unit hurt you: a hostile Dweller, or any other monster but a calm trader (and never a
    follower)?"""
    if unit is None or isFollower(unit):
        return False
    if dwellers.isDweller(unit):
        return unit.hostile and unit.role not in ("egg", "pupa", "grub")
    return not (getattr(unit, "merchant", False) and peddler.isCalm(unit))


def foeInSight(game, position, follower):
    """(position, unit) of the nearest thing hostile to you this follower can see, within FIGHT_REACH of you."""
    found = []
    for spot, unit in occupancy.allUnits(game):
        if unit is follower or not hostileToYou(game, unit):
            continue
        if dwellers.distance(game, spot, game.playerPositionFlat) <= FIGHT_REACH and dwellers.canSee(game, position, follower, spot):
            found.append((dwellers.distance(game, position, spot), spot, unit))
    if not found:
        return None
    _, spot, unit = min(found, key=lambda item: item[0])
    return spot, unit


def followerTurn(game, position, follower):
    """One action for your follower: it hits something hostile to you beside it, goes after one it sees near you,
    or keeps close to you. Returns where it ends up."""
    follower.floorKey = mineshafts.floorKey(game)
    if game.peaceful:  # (you're not on this floor: it waits for you)
        return position
    foe = foeInSight(game, position, follower)
    if foe is not None:
        foeSpot, unit = foe
        if foeSpot in game.neighbors(position):
            expansion.attack(game, position, follower, unit, foeSpot)
            return position
        return dwellers.stepToward(game, position, foeSpot, unit=follower)
    if dwellers.distance(game, position, game.playerPositionFlat) > KEEP_CLOSE:
        return dwellers.stepToward(game, position, game.playerPositionFlat, unit=follower, reach=dwellers.FAR_PATH_REACH)
    return position


def forgetTheDead(game):
    """Followers that died on the floor you're on are forgotten."""
    here = mineshafts.floorKey(game)
    alive = {id(unit) for _, unit in occupancy.allUnits(game)}
    game.player.followers = [unit for unit in followersOf(game.player)
                             if getattr(unit, "floorKey", here) != here or id(unit) in alive]


# ---------------------------------------------------------------- you and your followers

def swapWithYou(game, newPosition):
    """You walk into your follower: you swap places (it goes where you were). True if you did."""
    tile = game.grid.get(newPosition)
    if not tile or tile[0] != 5 or len(tile) < 3 or not isFollower(tile[2]) or newPosition in occupancy.sharedTiles(game):
        return False  # (not alone on its space: you can't swap with it)
    follower = tile[2]
    old = game.playerPositionFlat
    under = game.enemyOccupiedItemSpaces.pop(newPosition, [0, tile[1]])  # (what it stood on: you stand there now)
    behind = game.currentLocation  # (what you stood on: it stands there now)
    if behind[0] != 0:
        game.enemyOccupiedItemSpaces[old] = list(behind)
    game.grid[old] = [5, behind[1], follower]
    game.EnemyPositions.discard(newPosition)
    game.EnemyPositions.add(old)
    game.grid[newPosition] = list(under)
    game.currentLocation = list(under)
    game.playerPositionFlat = newPosition
    game.change = True
    return True


def takeOff(data, unit):
    """Takes unit off a saved floor (data: livingfloors.FLOOR_FIELDS plus its shared spaces). True if it was
    there."""
    grid, enemyPositions, underneath = data[0], data[3], data[4]
    shared = data[8] if len(data) > 8 else {}
    for spot, second in list(shared.items()):
        if second is unit:
            del shared[spot]
            return True
    for spot, tile in grid.items():
        if tile[0] == 5 and len(tile) > 2 and tile[2] is unit:
            enemyPositions.discard(spot)
            second = shared.pop(spot, None)
            if second is not None:
                tile[2] = second
                enemyPositions.add(spot)
            else:
                grid[spot] = underneath.pop(spot, [0, tile[1]])
            return True
    return False


def bringAlong(game):
    """You've just changed floors (gameManager.afterLevelChange): your followers on the floor you left come with
    you, each set down on the free tile nearest you. One that isn't there any more (it died) is forgotten."""
    here = mineshafts.floorKey(game)
    kept = []
    for unit in followersOf(game.player):
        key = getattr(unit, "floorKey", here)
        if key == here:
            kept.append(unit)
            continue
        data = livingfloors.floorData(game, key)
        if data is None or not takeOff(data, unit):
            continue
        spot = livingfloors.nearestFree(game, game.playerPositionFlat)
        if spot is None or spot == game.playerPositionFlat:
            spot = next((near for near in game.neighbors(game.playerPositionFlat) if organizers.passable(game.grid[near])), None)
        if spot is None:
            continue  # (nowhere to stand: it's lost)
        dewgrubs.placeUnit(game, spot, unit)
        unit.floorKey = here
        kept.append(unit)
    game.player.followers = kept
