import math
import random as rand

from cruel.entities import enemies
from cruel.inventory import loot
from cruel.world import organizers
from cruel.world import plants
from cruel.inventory import resources
from cruel.world import wall

"""
The Expansion event: a goblin war band (a Goblin Chief, 2 Goblins and 3 Goblin Builders, see WARBAND) turns up somewhere out of
sight and starts a camp. Until the camp has TOGETHER_HUTS finished huts, its builders work together on the same hut
(each on its own tile, all helping with the spawner); after that each one builds its own.

Factions: every expansion is a faction with its own colors (one of LOOKS). Its bonfires, huts, spawners and goblins
all belong to it. Goblins that were already on the floor are "wild" (no faction).

  Goblin Builder  lights a bonfire if there's none of its faction's within BONFIRE_REACH, then builds huts around
                  it, one after another, forever: picks a site, floors every tile of it with Stone one at a time
                  (breaking any wall in the way first), builds every hut wall one at a time, then builds the
                  spawner in the middle. When there's no room left around its bonfires it lights a new one further
                  out. A wall already standing where a hut wall goes is claimed (CLAIM_TURNS) instead of broken.
                  Huts that lose walls or their spawner are built back up before any new hut. It only fights
                  things right beside it.
  Goblin Farmer   farms only in its farming hut, which a builder builds with it on a floor that suits its seeds
                  (see "the farmer" below): sows the beds, picks each crop when it's ripe, waiting for its seed
                  stage while it's short of seeds, and stores what it doesn't keep in the hut's chest. It walks through any plant, and never
                  picks one it didn't sow.
  Spawner         every SPAWN_TURNS makes a Goblin, Goblin Chief, Goblin Builder or Goblin Farmer (SPAWN_ODDS) on a free tile
                  inside its hut, eating FOOD_PER_SPAWN of the food stocked in it. It waits while the hut is full
                  or it's out of food. It holds SPAWNER_FOOD_MAX food and starts with SPAWNER_START_FOOD.
  Food            FOOD: plant herbs and Raw Meat (a goblin gets KILL_MEAT when it kills anything). Squads haul it
                  home with the rest of their loot, farmers store their harvest, and builders carry it from the war
                  chests to any spawner that's running low (HUNGRY_AT); so do goblins waiting at the bonfire.
  Bonfire         lights the camp (BONFIRE_LIGHT_RADIUS, through the firelight system) and draws wild goblins in
                  to fight the faction.
  Squads          3 Goblins and a Chief. New goblins wait at the bonfire until they make a squad; a squad short of
                  members takes them first. While a squad waits at the bonfire for more goblins, it breaks walls
                  within CLEAR_RADIUS of its bonfires and in its unfinished huts (helping the builders); it never
                  builds or changes floors. Squads hunt anything that isn't their faction (you, wild goblins, other
                  factions, any other enemy). With nothing to fight they go on gathering missions: the chief leads
                  them to a random spot anywhere on the floor (at least MISSION_MIN from home) and back, and they
                  gather whatever they pass, there and back. Back home they stash what they brought.
  Schisms         a faction with SPLIT_UNITS goblins (and SPLIT_BUILDERS builders and SPLIT_FARMERS farmers) rolls
                  for a schism every turn: SCHISM_CHANCE at first, growing by SCHISM_CHANCE_STEP each turn it
                  doesn't happen (faster while its food is low, see schismStep), and back to SCHISM_CHANCE once it
                  does. In a schism half its squads, builders and farmers become a new faction in new colors, taking
                  half its stored food (up to SCHISM_FOOD) and, for their farmers, seeds from its war chests, and
                  march off to set up a camp at least SCHISM_DISTANCE from every bonfire, hut and other leaving
                  group's destination. Huts and chests stay. The two are at peace until the new camp's first bonfire
                  is lit (SCHISM_PEACE turns at most), then at war. On a floor too crowded for another camp, the new
                  faction rises up where it is instead (takeOver): at war at once, it takes half the faction's huts. NO_SCHISM_CHANCE of factions (war bands and
                  schisms' new factions alike) never split.

Hauling: marching squads with nothing to fight empty floor chests and item piles near them (items, materials and
gold), mine ore veins and Gold Walls near their camp, keeping everything they dig out (and what they take from
enemies they kill), and pick wild plants near their camp (never crops, nor anything in a farming hut). Every goblin carries
CARRY_SLOTS slots, stacked like your pouch but smaller: each material takes a slot per GOBLIN_STACK of it,
picked-up gold one slot, each item one. Once the squad is HAUL_AT full it heads home, still stopping for anything within HAUL_DETOUR
of it on the way until it's full, and puts everything in a war chest: a storage hut's first, else one by its
bonfire (it builds one there if needed). Then it heads out again. Items a goblin carries drop where it dies. Squads
at war raid the other faction's chests: they smash one open, take what fits and haul it home.

Storage huts: once a faction has FIRST_STORAGE_HUTS huts, builders build a storage hut (a bigger hut lined with
war chests, STORAGE_CHESTS). Whenever every storage chest is full, all its builders work on the next one.

Neutral factions: each new faction (the war band, a schism's new half) is neutral to you NEUTRAL_CHANCE of the
time. A neutral faction keeps to itself:
  - it sets up camp as far from the other factions as it can (a war band arrives at the spot farthest from every
    camp, a schism's new half marches to the farthest spot it finds);
  - its squads never raid and never go on gathering missions: they stay home, and only fight what comes within
    GUARD_REACH of its camp (other factions, wild goblins, any other enemy);
  - it leaves you alone, unless you provoke it: damage one of its goblins, break one of its hut walls or spawners,
    or take anything from one of its chests. Then it's hostile to you for GRUDGE_TURNS turns (each new offence
    starts the count again), and after that it leaves you alone again.
A faction that isn't neutral is hostile to you from the start, as always.

No two units ever share a tile: every move, spawn and build checks the tile is free.
The camp's state for each floor lives in gameManager.camps[floor] (saved with the game); the pieces on the map are
grid tiles of type CAMP holding a Structure.
"""

CAMP = 10                   # grid tile type for camp structures (spawners and bonfires)
HOLE = 11                   # grid tile type for broken floor (a bomb's collapse): step on it and you fall to the floor below

SPAWN_TURNS = (30, 50)      # turns between a spawner's goblins
SPAWN_ODDS = [("Goblin", 64), ("Goblin Chieftan", 22), ("Goblin Builder", 8), ("Goblin Farmer", 6)]
WORKERS = ("Goblin Builder", "Goblin Farmer")  # they don't join squads, and only fight what's right beside them
UNIT_CLASSES = {"Goblin": enemies.Goblin, "Goblin Chieftan": enemies.GoblinChief,
                "Goblin Builder": enemies.GoblinBuilder, "Goblin Farmer": enemies.GoblinFarmer}
SPAWNER_HP = 30
SPAWNER_DROPS = [("stone", 2), ("scrap", 1)]
BONFIRE_HITS = 3            # hits to put a bonfire out
BONFIRE_LIGHT_RADIUS = 5

BONFIRE_TURNS = 4           # a builder's turns to light a bonfire
FLOOR_TURNS = 1             # ...to floor one tile with Stone
WALL_TURNS = 2              # ...to build one hut wall
CLAIM_TURNS = 1             # ...to make a wall already standing where a hut wall goes into one (no ore veins)
SPAWNER_TURNS = 8           # ...to build a spawner
BUILDER_REST = (10, 20)
BREAK_DAMAGE = 40           # a builder's hit on a wall in its way (one hit for any plain wall)
BONFIRE_REACH = 12          # huts go 4 to this many tiles from a bonfire
BONFIRE_GIVE_UP = 80        # a builder that hasn't reached the spot for a new bonfire after this many turns gives it up
HOME_REACH = 30             # a builder further than this from all its faction's bonfires lights one where it is
HUT_DISTANCE = (4, 12)
NEW_BONFIRE_DISTANCE = (13, 18)
CAMP_GAP = 30               # a faction lights no bonfire this close to another faction's (bar a new camp's first)

SQUAD_GOBLINS = 3           # plus a chief
SIGHT = 6                   # how far a squad member spots a target
CHASE_LIMIT = 15            # a squad drops a target this far from its leader
PATROL_RADIUS = 15
CLEAR_RADIUS = 6            # squads waiting for more goblins break the walls this close to their bonfires
MISSION_MIN = 25            # a gathering mission goes at least this far (walking) from home...
MISSION_TURNS = 400         # ...and a leg of it (there, or back) that takes longer than this is cut short
FOLLOW_DISTANCE = 2

TOGETHER_HUTS = 2           # until a faction has this many finished huts, all its builders work on the same hut
# who the event brings: a chief and 2 goblins (one squad, guarding the camp), 3 builders and a farmer (who brings
# seeds of one plant, FARMER_START_SEEDS)
WARBAND = ["Goblin Chieftan", "Goblin", "Goblin", "Goblin Builder", "Goblin Builder", "Goblin Builder", "Goblin Farmer"]

# Food: what spawners eat. Each of these materials is 1 food.
FOOD = [info["herb"] for info in plants.PLANTS.values() if info.get("wild", True)] + ["meat"]
FOOD_PER_SPAWN = 2          # food a spawner eats for each goblin it makes
SPAWNER_FOOD_MAX = 10       # food a spawner holds
SPAWNER_START_FOOD = 4      # food a new spawner is built with
HUNGRY_AT = 4               # a spawner with less food than this gets a builder bringing it more
KILL_MEAT = (1, 2)          # Raw Meat a goblin takes from anything it kills

CARRY_SLOTS = 15            # what a goblin can carry (see "Hauling" above)
GOBLIN_STACK = 10           # how much of one material fits in one of its slots (a goblin's pouch is small)
HAUL_AT = 0.7               # a squad this full heads home to stash what it carries...
HAUL_DETOUR = 4             # ...stopping for things this close to it on the way, until it's full
MINE_REACH = 6              # squad members mine ore veins and Gold Walls this close to their leader...
MINE_RANGE = PATROL_RADIUS + 5  # ...within this far of their bonfire
CHEST_TURNS = 3             # turns to build a warcamp chest
CAMP_CHEST_SLOTS = 20       # a warcamp chest's room: each material takes one slot however much of it, each item one
FARM_CHEST_SLOTS = 40       # a farming hut's chest is bigger
                            # (20 rows is what the Items Here window fits on a 768-pixel-tall screen)
CHEST_HP = 12               # hits (of a goblin's damage) to smash one open
CHEST_SPOT = (2, 4)         # a warcamp chest goes this many tiles from its bonfire
RAID_REACH = 60             # squads raid another faction's chests this close to their own bonfire

SPLIT_UNITS = 25            # a faction with this many goblins (builders and farmers too)...
SPLIT_BUILDERS = 2          # ...and at least this many builders (so both halves can build)...
SPLIT_FARMERS = 2           # ...and farmers (so both halves can farm) has a schism
SCHISM_FOOD = 30            # the half that leaves takes half the faction's stored food along, at most this much
HUT_SPAWNS = 2              # a faction starts a new spawner hut only once each of its spawner huts has made this many goblins
MAX_STORAGE_HUTS = 3        # a faction has at most this many storage huts
SCHISM_CHANCE = 0.0005      # a faction meeting the requirements above rolls this chance of a schism each turn...
SCHISM_CHANCE_STEP = 0.00005  # ...which grows by this much each turn it doesn't happen (back to SCHISM_CHANCE after one)
SCHISM_HUNGER = 3           # the growth is up to (1 + this) times faster while the faction's food runs low...
FOOD_NEED_SPAWNER = 5       # ...against what it needs: this much food per spawner...
FOOD_NEED_UNIT = 1          # ...and this much per goblin
NO_SCHISM_CHANCE = 0.1      # a new faction (a war band, or a schism's new half) never splits, this often
SCHISM_DISTANCE = 45        # the half that leaves makes its camp at least this far from every faction's bonfires,
                            # huts and war chests, and from where any other leaving half is going...
SCHISM_CLEAR = 10           # ...and this far from you, any other enemy and any crafting station
SCHISM_PEACE = 400          # the two are at peace until its first bonfire is lit, or for this many turns at most
ARRIVE_REACH = 5            # its builders light that bonfire this close to where they were going
SEIZE_FIGHT = 12            # a group off to seize a spawner (it lost its builders) fights all it sees this close to it

# Storage huts: walls STORAGE_RADIUS from the middle (a 9x9 square with the corners left out), an entrance in the
# middle of each side, and a war chest on each of these spots inside, along the walls
STORAGE_RADIUS = 4
# Chests along the inside of its walls: the corners and the spots beside them on the top and bottom rows... but not
# (+-2, +-3), so every corner opens onto the middle: no chest is boxed in by others, and no tile is a pocket that
# would seal in a goblin standing there when the last chest goes in.
STORAGE_CHESTS = [(dx, dy) for d in (-1, 1) for dx, dy in ((d, -3), (d, 3))] + \
    [(dx, dy) for d in (-2, -1, 1, 2) for dx, dy in ((-3, d), (3, d))] + [(-3, -3), (3, -3), (-3, 3), (3, 3)]
FIRST_STORAGE_HUTS = 2      # builders start the first storage hut once the faction has this many huts

WILD_SIGHT = 5              # a wild goblin attacks expansionists this close
RALLY_TURNS = 10            # every this many turns...
RALLY_REACH = 30            # ...wild goblins this close to a bonfire...
RALLY_CHANCE = 0.25         # ...may march to it
WANDERER_TURNS = 60         # a wild goblin wanders in from out of sight this often while a bonfire burns

# Faction colors (sprites.py draws them). An expansion picks one of the first three; a split picks one no living
# faction on the floor is using.
LOOKS = ["warpaint", "ashen", "ochre", "nightcult", "tidewater", "ember"]
FIRST_LOOKS = LOOKS[:3]
NEUTRAL_LOOK = "abandoned"  # a dead faction's camp, until someone claims it (never one of LOOKS)

# Neutral factions (see "Neutral factions" above). NEUTRAL_LOOK is something else: an abandoned camp's colors.
NEUTRAL_CHANCE = 0.3        # a new faction is neutral to you this often
GUARD_REACH = 18            # a neutral faction's squads only fight what comes this close to its bonfires and huts
GRUDGE_TURNS = 150          # provoke a neutral faction and it's hostile to you for this many turns
FAR_SPOTS_WEIGHED = 300     # how many open spots a neutral faction compares when it looks for the farthest one

GOBLIN_NAMES = ("Goblin", "Goblin Chieftan")

# The hut: offsets from its center. A 7x7 square with the corners left out, an entrance in the middle of each of
# its 4 sides, a 5x5 room inside and the spawner in the middle. The Stone floor covers it and a 1-tile border.
HUT_SIDES = [(0, -3), (0, 3), (-3, 0), (3, 0)]
HUT_FLOOR = [(dx, dy) for dy in range(-4, 5) for dx in range(-4, 5)]
HUT_INSIDE = [(dx, dy) for dy in range(-2, 3) for dx in range(-2, 3) if (dx, dy) != (0, 0)]


def hutWalls(doors, r=3):
    """Wall offsets of a hut whose walls are r from its middle: the square ring with its corners left out."""
    return [(dx, dy) for dy in range(-r, r + 1) for dx in range(-r, r + 1)
            if max(abs(dx), abs(dy)) == r and not (abs(dx) == r and abs(dy) == r) and (dx, dy) not in doors]


def paintHutWall(gm, hut, t, look):
    """Paints the hut wall at t in a faction's colors: the renderer draws its mortar joints in the look's cloak color
    (renderer.drawMortar). wall.paint is (look, side of the hut it's on, parity): the joints are turned to face out
    of the hut and alternate from one wall tile to the next, like laid stone. When its faction dies out, the camp
    is repainted in NEUTRAL_LOOK (abandon)."""
    w, r = gm.grid[t][2], hut.get("radius", 3)
    for dx, dy in hutWalls((), r):
        if offsetTile(gm, hut["center"], dx, dy) == t:
            side = "n" if dy == -r else "s" if dy == r else "w" if dx == -r else "e"
            w.paint = (look, side, (dx + dy) % 2)
            return


# ---------------------------------------------------------------- state

class Structure:
    """A spawner or a bonfire, standing on a CAMP tile."""

    def __init__(self, kind, faction, hut=None):
        self.kind = kind          # "spawner" or "bonfire"
        self.faction = faction
        self.hut = hut            # a spawner's hut center
        self.hp = SPAWNER_HP if kind == "spawner" else BONFIRE_HITS
        self.maxHp = self.hp
        self.food = SPAWNER_START_FOOD if kind == "spawner" else 0
        self.feeder = None        # the builder bringing it food, if any
        self.timer = rand.randint(*SPAWN_TURNS)

    @property
    def name(self):
        return "Goblin Spawner" if self.kind == "spawner" else "Bonfire"


class Faction:
    def __init__(self, fid, look):
        self.id, self.look = fid, look
        self.bonfires = []        # positions
        self.first = None         # its first bonfire (splits measure from it)
        self.huts = []            # {"center", "floor", "walls", "inside", "done"}
        self.squads = []
        self.farms = []           # (farm plots, from before farming huts: unused)
        self.migrating = None     # where a schism's new half is going to set up camp
        self.peaceWith = None     # the faction it's at peace with for now (a schism's other half)
        self.seizing = None       # (faction id, hut center): the spawner a group that lost its builders goes to take
        self.abandoned = False    # died out (no goblins, no food to spawn more): its camp stands empty, for the taking
        self.neutral = False      # neutral to you (see "Neutral factions"): defends its camp, never raids
        self.grudge = 0           # turns a neutral faction stays hostile to you after you provoked it

    def walls(self):
        """Its huts' walls, built or planned: its own goblins never dig through these."""
        return {t for h in self.huts for t in h["walls"]}


class Squad:
    def __init__(self, marching=False):
        self.members = []
        self.marching = marching  # False: still gathering at the bonfire
        self.target = None        # "player" or an enemy
        self.goal = None          # patrol spot
        self.goalTurns = 0
        self.hauling = False      # heading home to stash what it carries
        self.raid = None          # another faction's chest it's going to smash


class CampChest(list):
    """A warcamp chest: the items in it (a list, like any chest on the map), plus whose it is. You can open and
    loot it like any other chest."""

    def __init__(self, faction, look, items=(), slots=CAMP_CHEST_SLOTS):
        super().__init__(items)
        self.faction, self.look, self.hp = faction, look, CHEST_HP
        self.slots = slots


def camp(gm):
    """This floor's camp state."""
    camps = gm.__dict__.setdefault("camps", {})
    if gm.level not in camps:
        camps[gm.level] = {"factions": {}, "next": 0, "structures": set()}
    return camps[gm.level]


def dropOut(gm, thing):
    """A faction goblin or goblin chest fell through the floor (gameManager.collapseFloor): it remembers which floor
    and faction it fell from (fellFrom), so it lands as that faction on the floor below (land). A goblin leaves its
    squad and forgets whatever it was doing."""
    if getattr(thing, "faction", None) is None or isinstance(thing, plants.Plant):
        return  # (a goblin crop that falls lands as a plain plant)
    thing.fellFrom = (gm.level, thing.faction)
    squad = getattr(thing, "squad", None)
    if squad is not None and thing in squad.members:
        squad.members.remove(thing)
    for attr in ("squad", "task", "rally", "foe", "seizing"):
        if hasattr(thing, attr):
            setattr(thing, attr, None)


def fallenFaction(gm, origin, look):
    """The faction on this floor for goblins and goblin chests that fell from origin (floor, faction id): made the
    first time one of them lands here, in the same colors. It has no camp: a builder of it lights one and it starts
    over; without one it goes to seize the nearest other faction's spawner (seizeStep), or with none to take its
    goblins wander, fighting anything that isn't theirs (wild goblins included)."""
    state = camp(gm)
    ids = state.setdefault("fellFrom", {})
    f = state["factions"].get(ids.get(origin))
    if f is None or getattr(f, "abandoned", False):
        floor, factionId = origin
        originFaction = gm.camps.get(floor, {}).get("factions", {}).get(factionId)
        f = newFaction(gm, look or NEUTRAL_LOOK, neutral=isNeutral(originFaction))
        f.fallen = True
        ids[origin] = f.id
    return f


def land(gm, thing, t):
    """A goblin or goblin chest that fell (dropOut) has landed at t: it joins its faction on this floor."""
    origin = getattr(thing, "fellFrom", None)
    if origin is None:
        return
    thing.fellFrom = None
    f = fallenFaction(gm, origin, getattr(thing, "look", None))
    if isinstance(thing, CampChest):
        thing.faction, thing.look = f.id, f.look
        chests(gm, f).add(t)
        return
    setFaction(thing, f)
    if thing.name not in WORKERS:
        joinSquad(gm, thing, f)


def factionOf(enemy):
    return getattr(enemy, "faction", None)


def dist(gm, a, b):
    R = gm.rowLength
    return math.hypot(a % R - b % R, a // R - b // R)


def offsetTile(gm, center, dx, dy):
    """center moved by (dx, dy), or None off the map."""
    x = center % gm.rowLength + dx
    if not 0 <= x < gm.rowLength:
        return None
    t = center + dx + dy * gm.rowLength
    return t if t in gm.grid else None


def hostile(unit, other):
    """Would this faction unit fight other? Everything outside its own faction, except a faction it's at peace with."""
    a, b = factionOf(unit), factionOf(other)
    return a != b and not (a is not None and b is not None and atPeace(a, b))


def setFaction(unit, faction):
    if getattr(unit, "baseGold", None) is None:
        unit.baseGold = unit.gold  # its own gold (what you get for killing it): it keeps that, and stashes the rest
    unit.faction, unit.look = faction.id, faction.look


def chests(gm, f):
    """f's warcamp chests still standing."""
    state = camp(gm).setdefault("chests", {})
    mine = state.setdefault(f.id, set())
    for t in list(mine):
        tile = gm.enemyOccupiedItemSpaces.get(t) or gm.grid.get(t)  # (an enemy standing on it keeps it underneath)
        if not tile or tile[0] != 3 or not isinstance(tile[2], CampChest) or tile[2].faction != f.id:
            mine.discard(t)  # smashed, or on another faction's side now
    return mine


def carried(unit):
    """How much a unit carries to stash: its materials and the gold it picked up."""
    return sum(getattr(unit, "materials", {}).values()) + pickedGold(unit) + len(getattr(unit, "loot", []))


def pickedGold(unit):
    return max(0, unit.gold - getattr(unit, "baseGold", unit.gold))


def slotsUsed(unit):
    """Slots it fills: each material a slot per GOBLIN_STACK, picked-up gold one, each item one."""
    stacks = sum(math.ceil(a / GOBLIN_STACK) for a in getattr(unit, "materials", {}).values() if a > 0)
    return stacks + len(getattr(unit, "loot", [])) + (1 if pickedGold(unit) else 0)


def roomFor(unit):
    return CARRY_SLOTS - slotsUsed(unit)


def fitAmount(unit, materialId):
    """How much more of materialId it can carry (topping up its stacks, then filling free slots)."""
    have = unit.materials.get(materialId, 0)
    return (math.ceil(have / GOBLIN_STACK) + max(0, roomFor(unit))) * GOBLIN_STACK - have


def squadLoad(squad):
    """How full the squad is, 0 to 1."""
    alive = [m for m in squad.members if m.hp > 0]
    return sum(min(slotsUsed(m), CARRY_SLOTS) for m in alive) / (CARRY_SLOTS * len(alive)) if alive else 0


def dropExtra(gm, unit, position):
    """Something put it over CARRY_SLOTS (a kill's spoils, what a wall gave): what doesn't fit drops at position."""
    drops = []
    loot_ = unit.__dict__.setdefault("loot", [])
    while slotsUsed(unit) > CARRY_SLOTS:
        if loot_:
            drops.append(loot_.pop())
        elif unit.materials:
            m = min(unit.materials, key=lambda k: unit.materials[k])
            drops.append(resources.MaterialStack(m, unit.materials.pop(m)))
        else:
            break
    if drops:
        gm.placeItems(position, drops)


def isOre(tile):
    return tile[0] == 2 and (isinstance(tile[2], wall.OreVein) or tile[2].name == "Gold Wall")


# ---------------------------------------------------------------- once a turn

def beginTurn(gm):
    """Where every enemy is at the start of the enemy turn, bucketed by area so nearby searches are quick."""
    pos, buckets = {}, {}
    R = gm.rowLength
    for p in gm.EnemyPositions:
        tile = gm.grid.get(p)
        if tile and tile[0] == 5 and len(tile) > 2:
            e = tile[2]
            pos[id(e)] = p
            buckets.setdefault((p % R // 8, p // R // 8), []).append((p, e))
    updatePeace(gm)
    return {"pos": pos, "buckets": buckets, "squadTargets": {}, "fields": {}}


def find(gm, ctx, enemy):
    """Where an enemy is now, or None if it's gone."""
    p = ctx["pos"].get(id(enemy))
    if p is not None and gm.grid[p][0] == 5 and len(gm.grid[p]) > 2 and gm.grid[p][2] is enemy:
        return p
    for p in set(gm.EnemyPositions) | getattr(gm, "movedEnemies", set()):
        tile = gm.grid.get(p)
        if tile and tile[0] == 5 and len(tile) > 2 and tile[2] is enemy:
            ctx["pos"][id(enemy)] = p
            return p
    return None


def near(gm, ctx, position, reach):
    """(position, enemy) for enemies within reach of position (by the turn's starting positions)."""
    R = gm.rowLength
    bx, by, span = position % R // 8, position // R // 8, int(reach) // 8 + 1
    for gx in range(bx - span, bx + span + 1):
        for gy in range(by - span, by + span + 1):
            for p, e in ctx["buckets"].get((gx, gy), ()):
                if dist(gm, p, position) <= reach:
                    yield p, e


def moved(ctx, unit, position):
    ctx["pos"][id(unit)] = position


def makeWay(gm, ctx, i, t, f, b):
    """A builder at i needs tile t, where someone is standing. One of its own goblins gets moved off (nudge); if it
    can't be (it's boxed in, often by the builders themselves), the builder steps away instead so it can get out.
    Returns where the builder is now."""
    if nudge(gm, ctx, t, f):
        return i
    away = [n for n in gm.neighbors(i) if organizers.passable(gm.grid[n], demise=False) and n not in gm.neighbors(t)]
    if not away:
        return i
    b.rest = 2  # it stays out of the way a couple of turns (coming straight back would box the other one in again)
    return organizers.moveTo(gm, i, rand.choice(away))


def nudge(gm, ctx, t, f):
    """Moves a goblin of faction f off tile t onto a free tile beside it (a builder needs t). True if t is clear."""
    tile = gm.grid[t]
    if tile[0] != 5 or len(tile) < 3 or factionOf(tile[2]) != f.id:
        return tile[0] == 0
    clear = keepClear(gm, ctx, f)  # never onto a doorway or a spot the huts still need (it'd be shoved back and forth)
    free = [n for n in gm.neighbors(t) if organizers.passable(gm.grid[n], demise=False) and n not in clear]
    if not free:
        return False
    n, unit = rand.choice(free), tile[2]
    if gm.grid[n][0] != 0:  # a pile or a plant: it stays underneath
        gm.enemyOccupiedItemSpaces[n] = gm.grid[n]
    gm.grid[n] = [5, gm.grid[n][1], unit]
    gm.grid[t] = gm.enemyOccupiedItemSpaces.pop(t) if t in gm.enemyOccupiedItemSpaces else [0, tile[1]]
    # it's at n now, both for the rest of this turn and for next turn (if it hadn't moved yet this turn, it misses
    # this turn's move, but it stays in the game)
    for positions in (gm.EnemyPositions, getattr(gm, "movedEnemies", set())):
        positions.discard(t)
        positions.add(n)
    moved(ctx, unit, n)
    gm.change = True
    return gm.grid[t][0] == 0


# ---------------------------------------------------------------- moving and fighting

PATH_REACH = 40             # how far (in steps) the shared path maps reach
BLOCKED_TURNS = 2           # a unit blocked this many turns in a row digs itself a new way (see step)
SWAP_COOLDOWN = 6           # a goblin that swapped places with another (swapWith) can't swap again for this many turns


BONFIRE_PATH_TURNS = 10     # a bonfire's floor-wide path map is redone this often


def bonfireField(gm, goal):
    """A path map to a bonfire covering the whole floor, for wild goblins marching to it. Bonfires don't move, so
    it's kept and redone every BONFIRE_PATH_TURNS turns."""
    cache = gm.__dict__.setdefault("bonfirePaths", {})
    turn, paths = cache.get(goal, (None, None))
    if paths is None or gm.turnCount - turn >= BONFIRE_PATH_TURNS:
        paths = walkingDistances(gm, goal, gm.numberOfSpots)
        cache[goal] = (gm.turnCount, paths)
    return paths


def field(gm, ctx, goal, start, plantsOpen=False):
    """Walking distance to goal over open floor (tiles someone stands on count as open, since they move), reaching
    far enough for a trip from start (up to PATH_REACH). Worked out once a turn per goal and shared by everyone
    heading there; redone further out if someone further away needs it. With plantsOpen (farmers), through any
    plant too."""
    fields = ctx.setdefault("fields", {})
    key = (goal, "plants") if plantsOpen else goal
    reach = min(PATH_REACH, int(dist(gm, start, goal) * 2) + 8)
    if key not in fields or (fields[key][0] < reach and start not in fields[key][1]):
        fields[key] = (reach, walkingDistances(gm, goal, reach, plantsOpen))
    if start not in fields[key][1] and fields[key][0] < PATH_REACH:  # the way round is longer: look further
        fields[key] = (PATH_REACH, walkingDistances(gm, goal, PATH_REACH, plantsOpen))
    return fields[key][1]


def canEnter(tile, throughPlants=False):
    """Can a goblin step onto this tile? Open floor, item piles, walkable plants; with throughPlants (farmers), any
    plant but Organizer's Demise."""
    return organizers.passable(tile, demise=False) or \
        (throughPlants and tile[0] == 8 and not organizers.isDemise(tile))


def neighborTable(gm):
    """Each tile's neighbors, worked out once per map (gameManager.neighbors is called a lot)."""
    key = (gm.rowLength, gm.numberOfSpots)
    cache = gm.__dict__.get("neighborCache")
    if cache is None or cache[0] != key:
        cache = (key, [tuple(gm.neighbors(t)) if t in gm.grid else () for t in range(gm.numberOfSpots)])
        gm.neighborCache = cache
    return cache[1]


def walkingDistances(gm, goal, reach, plantsOpen=False):
    """{tile: steps to goal} for tiles up to reach steps away, walking over open floor, item piles and walkable
    plants (not Organizer's Demise; with plantsOpen, any other plant too) and anyone standing on them."""
    out, frontier = {goal: 0}, [goal]
    table, grid = neighborTable(gm), gm.grid
    for d in range(1, reach + 1):
        if not frontier:
            break
        nxt = []
        for p in frontier:
            for n in table[p]:
                if n not in out and (grid[n][0] in (1, 5) or canEnter(grid[n], plantsOpen)):
                    out[n] = d
                    nxt.append(n)
        frontier = nxt
    return out


def step(gm, i, unit, goal, protected, ctx=None, paths=None):
    """One step toward goal. With a path to it (see field), along the path onto a free tile. Without one, straight
    at it: onto free floor that gets closer, or (for a unit that digs) through a wall in the way that isn't
    protected, sliding sideways round small obstacles. Returns where it is now."""
    farmer = unit.name == "Goblin Farmer"  # (farmers walk through any plant)
    if ctx is not None or paths is not None:
        paths = paths if paths is not None else field(gm, ctx, goal, i, farmer)
        if i in paths:
            closer = [j for j in gm.neighbors(i) if paths.get(j, 1e9) < paths[i]]
            better = [j for j in closer if canEnter(gm.grid[j], farmer)]
            if not better and unit.name == "Goblin Builder" and ctx is not None:  # its own goblins in the way: shoo one
                f = camp(gm)["factions"].get(factionOf(unit))
                better = [j for j in closer if f is not None and nudge(gm, ctx, j, f)]
            if not better and ctx is not None:  # still blocked by its own goblins (nowhere to shoo them): swap places
                j = swapWith(gm, ctx, i, unit, sorted((j for j in closer if j != goal), key=lambda j: paths[j]))
                if j is not None:
                    unit.blockedTurns = 0
                    return j
            if better:
                unit.blockedTurns = 0
                return organizers.moveTo(gm, i, min(better, key=lambda j: paths[j]))
            # the way is blocked by someone. After BLOCKED_TURNS of that, a unit that digs carves its own way: it digs
            # into the wall beside it nearest where it's going (never its own camp's hut walls), making a new passage
            # so units stuck nose to nose in a corridor get past each other. One that can't dig steps aside now and then.
            unit.blockedTurns = getattr(unit, "blockedTurns", 0) + 1
            if unit.blockedTurns >= BLOCKED_TURNS and unit.wallDamage > 0:
                diggable = [j for j in gm.neighbors(i) if gm.grid[j][0] == 2 and j not in protected]
                if diggable:
                    j = min(diggable, key=lambda j: dist(gm, j, goal))
                    digWall(gm, i, unit, j, BREAK_DAMAGE if unit.name == "Goblin Builder" else unit.wallDamage)
                    return i
            aside = [j for j in gm.neighbors(i) if canEnter(gm.grid[j], farmer) and j in paths]
            if aside and rand.random() < 0.3:
                return organizers.moveTo(gm, i, rand.choice(aside))
            return i
    here = dist(gm, i, goal)
    options = sorted(gm.neighbors(i), key=lambda j: dist(gm, j, goal))
    for j in options:
        if dist(gm, j, goal) >= here:
            break
        tile = gm.grid[j]
        if canEnter(tile, farmer):
            return organizers.moveTo(gm, i, j)
        if tile[0] == 2 and unit.wallDamage > 0 and j not in protected:
            digWall(gm, i, unit, j, BREAK_DAMAGE if unit.name == "Goblin Builder" else unit.wallDamage)
            return i
    sideways = [j for j in options if canEnter(gm.grid[j], farmer) and dist(gm, j, goal) <= here + 0.5]
    if sideways and rand.random() < 0.5:
        return organizers.moveTo(gm, i, rand.choice(sideways))
    if ctx is not None:  # its own goblins in the way: swap places with one that's closer
        j = swapWith(gm, ctx, i, unit, [j for j in options if dist(gm, j, goal) < here and j != goal])
        if j is not None:
            return j
    return i


def swapWith(gm, ctx, i, unit, tiles):
    """unit (taken off tile i for its turn) swaps places with the first goblin of its own faction standing on one of
    tiles: that goblin goes to i, and unit's new position is returned (None if there's nobody to swap with). Whatever
    lies under each tile stays where it is. The other goblin keeps its turn if it hadn't had it yet.
    Callers never pass the tile unit is heading for: whoever stands on its goal is waited for, not swapped out (else
    two goblins after the same tile, like a squad member following its leader, swap back and forth for ever). And a
    goblin that swapped can't swap again for SWAP_COOLDOWN turns, either way round, so no pair can ping-pong."""
    mine = factionOf(unit)
    cooling = lambda u: gm.turnCount - getattr(u, "swappedAt", -SWAP_COOLDOWN) < SWAP_COOLDOWN
    if mine is None or cooling(unit):
        return None
    for j in tiles:
        tile = gm.grid[j]
        if tile[0] != 5 or len(tile) < 3 or factionOf(tile[2]) != mine or cooling(tile[2]):
            continue
        other = tile.pop()  # (j stays an enemy tile: unit goes there)
        unit.swappedAt = other.swappedAt = gm.turnCount
        gm.grid[i].append(other)
        for positions in (gm.EnemyPositions, getattr(gm, "movedEnemies", set())):
            positions.add(i)
        moved(ctx, other, i)
        gm.change = True
        return j
    return None


def digWall(gm, i, unit, t, damage):
    w = gm.grid[t][2]
    gm.chip(t, i)
    w.takeDamage(damage, gm.tileSize)
    if w.hp <= 0:
        gm.enemyBrokeWall(t, unit)
    gm.change = True


def attack(gm, i, unit, target, targetPosition):
    """unit hits target ("player" or an enemy). Whatever it hits fights back."""
    if target == "player":
        gm.hitPlayer(unit, i)
        return
    target.hp -= gm.enemyDodge(target, unit.damage, targetPosition)
    gm.bleed(targetPosition)
    gm.change = True
    if isinstance(target, enemies.Organizer):
        organizers.placedBy(target)
        if target.aggro is None and not isinstance(target, enemies.PlantOrganizer):
            target.aggro, target.aggroTurns = unit, 0
    elif factionOf(target) is None:
        target.foe = unit
    if target.hp <= 0:
        gm.killEnemy(targetPosition, killer=unit)
        if factionOf(unit) is not None:  # food for the camp
            meat = min(rand.randint(*KILL_MEAT), fitAmount(unit, "meat"))
            if meat > 0:
                unit.materials["meat"] = unit.materials.get("meat", 0) + meat


def adjacentFoe(gm, i, unit):
    """(target, position) of something hostile right beside unit, or None."""
    if huntsPlayer(gm, unit) and gm.playerPositionFlat in gm.neighbors(i):
        return "player", gm.playerPositionFlat
    for j in gm.neighbors(i):
        tile = gm.grid[j]
        if tile[0] == 5 and len(tile) > 2 and hostile(unit, tile[2]):
            return tile[2], j
    return None


# ---------------------------------------------------------------- the faction's turn

def takeTurn(gm, i, unit, ctx):
    """A faction unit's turn. Returns where it is now."""
    acted = ctx.setdefault("acted", set())
    if id(unit) in acted:  # it was swapped onto a tile that hadn't had its turn yet: it already had its own
        return i
    acted.add(id(unit))
    foe = adjacentFoe(gm, i, unit)
    if foe:
        attack(gm, i, unit, *foe)
        if slotsUsed(unit) > CARRY_SLOTS:  # a kill's spoils (and meat) can overfill its pockets
            dropExtra(gm, unit, i)
        return i
    if unit.name == "Goblin Builder":
        position = builderTurn(gm, i, unit, ctx)
    elif unit.name == "Goblin Farmer":
        position = farmerTurn(gm, i, unit, ctx)
    else:
        position = soldierTurn(gm, i, unit, ctx)
    if slotsUsed(unit) > CARRY_SLOTS:
        dropExtra(gm, unit, position)
    if position == i and not (unit.name == "Goblin Builder" and getattr(unit, "task", None)):
        position = stepOffClear(gm, ctx, i, unit)
    moved(ctx, unit, position)
    return position


def keepClear(gm, ctx, f):
    """Tiles f's goblins shouldn't stand still on: its huts' doorways, and the spots in unfinished huts where walls,
    chests or a spawner still have to go. Worked out once a turn."""
    cache = ctx.setdefault("clear", {})
    if f.id not in cache:
        tiles = set()
        for h in f.huts:
            r = h.get("radius", 3)
            tiles |= {t for t in (offsetTile(gm, h["center"], dx, dy) for dx, dy in ((0, -r), (0, r), (-r, 0), (r, 0)))
                      if t is not None}
            if h.get("kind") == "farm" and h["done"]:
                tiles |= set(h["beds"])  # (farmers work in them: see stepOffClear)
            if not h["done"]:
                tiles |= {t for t in h["walls"] if gm.grid[t][0] != 2}
                tiles |= {t for t in h.get("chests", ()) if gm.grid[t][0] != 3}
                if h.get("kind", "hut") == "hut":
                    tiles.add(h["center"])
        cache[f.id] = tiles
    return cache[f.id]


def stepOffClear(gm, ctx, i, unit):
    """A goblin that ended its turn standing still in a doorway or on a build spot steps off it, if it can."""
    f = faction(gm, unit)
    if f is None:
        return i
    clear = keepClear(gm, ctx, f)
    if i not in clear:
        return i
    if unit.name == "Goblin Farmer" and any(i in h.get("beds", ()) for h in farms(f)):
        return i  # tending its beds
    off = [n for n in gm.neighbors(i) if organizers.passable(gm.grid[n], demise=False) and n not in clear]
    return organizers.moveTo(gm, i, rand.choice(off)) if off else i


def faction(gm, unit):
    return camp(gm)["factions"].get(factionOf(unit))


def homeBonfire(gm, f, position):
    return min(f.bonfires, key=lambda b: dist(gm, b, position)) if f and f.bonfires else None


def joinSquad(gm, unit, f):
    """Puts a new goblin or chief into a squad: one short of its kind first, else the one gathering at the bonfire."""
    chief = unit.name == "Goblin Chieftan"
    alive = lambda s: [m for m in s.members if m.hp > 0]

    def wants(s):
        members = alive(s)
        return not any(m.name == "Goblin Chieftan" for m in members) if chief else \
            sum(m.name == "Goblin" for m in members) < SQUAD_GOBLINS

    squad = next((s for s in f.squads if s.marching and wants(s)), None) or \
        next((s for s in f.squads if not s.marching and wants(s)), None)
    if squad is None:
        squad = Squad()
        f.squads.append(squad)
    squad.members = alive(squad) + [unit]
    unit.squad = squad
    if not squad.marching and len(squad.members) >= SQUAD_GOBLINS + 1:
        squad.marching = True


def squadTarget(gm, squad, ctx, current, currentAt):
    """(target, position) the whole squad is after this turn, or None. Worked out once a turn per squad.
    current is the unit taking its turn (off the map while it moves), standing at currentAt."""
    key = id(squad)
    if key in ctx["squadTargets"]:
        return ctx["squadTargets"][key]
    ctx["pos"][id(current)] = currentAt
    where = lambda m: currentAt if m is current else find(gm, ctx, m)
    squad.members = [m for m in squad.members if m.hp > 0 and where(m) is not None]
    leader = squadLeader(squad)
    result = None
    leaderAt = where(leader) if leader else None
    squadFaction = faction(gm, leader) if leader else None
    guarding = isNeutral(squadFaction)  # a neutral faction only fights what comes near its camp
    chasesPlayer = leader is not None and huntsPlayer(gm, leader)

    def worthFighting(position):
        return not guarding or nearCamp(gm, squadFaction, position)

    if squad.target is not None and leaderAt is not None:  # keep after the same target while it's close
        at = gm.playerPositionFlat if squad.target == "player" and chasesPlayer else \
            (find(gm, ctx, squad.target) if squad.target != "player" else None)
        if at is not None and dist(gm, at, leaderAt) <= CHASE_LIMIT and worthFighting(at):
            result = (squad.target, at)
    if result is None:
        squad.target = None
        best = None
        lookouts = list(squad.members)
        if not squad.marching and leaderAt is not None:  # guarding the camp: also whatever comes at its builders
            lookouts += [b for p, b in near(gm, ctx, leaderAt, CHASE_LIMIT)
                         if b.name in WORKERS and factionOf(b) == factionOf(leader)]
        for m in lookouts:
            at = where(m)
            if at is None:
                continue
            if at in gm.smoke:
                continue  # can't see out of smoke
            if chasesPlayer and gm.playerPositionFlat not in gm.smoke and dist(gm, at, gm.playerPositionFlat) <= SIGHT \
                    and worthFighting(gm.playerPositionFlat) and gm.lineOfSight(at, gm.playerPositionFlat):
                d = dist(gm, at, gm.playerPositionFlat)
                if best is None or d < best[0]:
                    best = (d, "player", gm.playerPositionFlat)
            for p, e in near(gm, ctx, at, SIGHT):
                if hostile(m, e) and e.hp > 0 and p not in gm.smoke and worthFighting(p) and gm.lineOfSight(at, p):
                    d = dist(gm, at, p)
                    if best is None or d < best[0]:
                        best = (d, e, p)
        if best:
            squad.target = best[1]
            result = (best[1], best[2])
        elif getattr(gm, "torchLight", None) and not guarding:  # nobody to fight, but your torchlight in sight: into the light
            for m in squad.members:
                at = where(m)
                if at is None or at in gm.smoke:
                    continue
                spot = gm.torchSpotSeen({t for t in gm.torchLight if dist(gm, at, t) <= SIGHT and gm.lineOfSight(at, t)})
                if spot is not None:
                    result = ("light", spot)
                    break
    ctx["squadTargets"][key] = result
    return result


def squadLeader(squad):
    alive = [m for m in squad.members if m.hp > 0]
    return next((m for m in alive if m.name == "Goblin Chieftan"), alive[0] if alive else None)


def soldierTurn(gm, i, unit, ctx):
    f = faction(gm, unit)
    if f is None:
        return i
    squad = getattr(unit, "squad", None)
    if squad is None or unit not in squad.members:
        joinSquad(gm, unit, f)
        squad = unit.squad
    protected = f.walls()
    seizing = getattr(f, "seizing", None) is not None
    fighting = migrating(f) is None or (seizing and dist(gm, i, f.migrating) <= SEIZE_FIGHT)
    target = squadTarget(gm, squad, ctx, unit, i) if fighting else None
    if target:
        return step(gm, i, unit, target[1], protected, ctx)
    if migrating(f) is not None:  # leaving after a schism: the leader heads for the new camp, the rest follow it.
        # They don't stop to hunt anything on the way (they still fight whatever is right beside them, takeTurn).
        # Off to seize a spawner, the leader goes right up to it, into its hut.
        leader = squadLeader(squad)
        leaderAt = None if leader is unit else find(gm, ctx, leader)
        if leaderAt is None:
            close = 1.5 if seizing else 3
            return migrateTurn(gm, i, unit, f, ctx) if dist(gm, i, f.migrating) > close else organizers.wander(gm, i)
        return step(gm, i, unit, leaderAt, protected, ctx) if dist(gm, i, leaderAt) > FOLLOW_DISTANCE else i
    if squad.marching:
        home = homeBonfire(gm, f, i)
        if home is not None:
            if not squad.hauling and squadLoad(squad) >= HAUL_AT:
                squad.hauling, squad.mission = True, None  # full enough: straight home
            if squad.hauling:
                return haulTurn(gm, i, unit, squad, f, home, ctx)
            if squad.raid is None and not isNeutral(f):  # a neutral faction never raids
                squad.raid = raidTarget(gm, f, home)
            if squad.raid is not None:
                return raidTurn(gm, i, unit, squad, f, ctx)
            position = scavengeTurn(gm, i, unit, squad, f, home, ctx)
            if position is not None:
                return position
            position = gatherTurn(gm, i, unit, squad, f, home, ctx)
            if position is not None:
                return position
            position = mineTurn(gm, i, unit, squad, f, home, ctx)
            if position is not None:
                return position
    if not squad.marching:  # waiting at the bonfire for more goblins: feed hungry spawners and clear walls meanwhile
        task = getattr(unit, "task", None)
        if task is None or task.get("kind") != "feed":
            task = unit.task = feedTask(gm, i, unit, f)
        if task is not None:
            return feedTurn(gm, i, unit, f, task, ctx)
        position = clearTurn(gm, i, unit, f, ctx)
        if position is not None:
            return position
    leader = squadLeader(squad)
    leaderAt = i if leader is unit else (find(gm, ctx, leader) if leader is not None else None)
    if leader is unit or leaderAt is None:
        home = homeBonfire(gm, f, i)
        if home is None:
            return organizers.wander(gm, i)
        if not squad.marching:  # gathering: stay near the bonfire
            return step(gm, i, unit, home, protected, ctx) if dist(gm, i, home) > 3 else organizers.wander(gm, i)
        position = None if isNeutral(f) else missionTurn(gm, i, unit, squad, f, home, ctx)  # (neutral: stays home)
        if position is not None:
            return position
        squad.goalTurns += 1  # nowhere to send it: patrol round the bonfire
        if squad.goal is None or dist(gm, i, squad.goal) <= 1 or squad.goalTurns > 25:
            squad.goal, squad.goalTurns = patrolSpot(gm, home), 0
        return step(gm, i, unit, squad.goal, protected, ctx) if squad.goal is not None else i
    if dist(gm, i, leaderAt) > FOLLOW_DISTANCE:
        return step(gm, i, unit, leaderAt, protected, ctx)
    return i


# ---------------------------------------------------------------- hauling, mining and raiding

def haulTurn(gm, i, unit, squad, f, home, ctx):
    """Home to a war chest with room (stashChest; it builds one by the bonfire if there's none) to stash what the
    squad carries. On the way, while the squad isn't full, it stops for anything within HAUL_DETOUR of it."""
    protected = f.walls()
    chest = stashChest(gm, f, unit, i, home)
    if chest is None:  # no chest with room: build one by the bonfire
        own = chests(gm, f)
        spot = getattr(squad, "chestSpot", None)
        if spot is None or gm.grid[spot][0] != 0:
            spot = squad.chestSpot = chestSpot(gm, home)
        if spot is None:
            squad.hauling = False  # nowhere to put one: carry on and try again later
            return i
        if spot in gm.neighbors(i):
            if work(f, ("chest", spot), CHEST_TURNS):
                gm.grid[spot] = [3, gm.grid[spot][1], CampChest(f.id, f.look)]
                own.add(spot)
                squad.chestSpot = None
                gm.change = True
            return i
        return step(gm, i, unit, spot, protected, ctx)
    if carried(unit) > 0:
        if chest in gm.eightAround(i):  # beside it, diagonals too
            stash(gm, chest, unit)
            return i
        if dist(gm, i, chest) > 3 and squadLoad(squad) < 1:
            position = pickUpNear(gm, i, unit, f, ctx)
            if position is not None:
                return position
        return step(gm, i, unit, chest, protected, ctx)
    if all(carried(m) == 0 for m in squad.members if m.hp > 0):
        squad.hauling = False  # all stashed: back out
    if chest in gm.eightAround(i):  # done: step back so the others can reach the chest
        away = [n for n in gm.neighbors(i) if organizers.passable(gm.grid[n], demise=False) and chest not in gm.eightAround(n)]
        return organizers.moveTo(gm, i, rand.choice(away)) if away else i
    return step(gm, i, unit, chest, protected, ctx) if dist(gm, i, chest) > 3 else i


def pickUpNear(gm, i, unit, f, ctx):
    """On its way home: loot, a plant or ore within HAUL_DETOUR of it, while it has room. Where it is after going
    for it, or None if there's nothing."""
    if roomFor(unit) <= 0:
        return None
    aside, protected, farmed = setAside(gm, unit), f.walls(), allFarmTiles(gm)
    wanted = lambda t: t not in aside and (loose(gm, t) or pickable(gm, t, farmed=farmed)
                                           or (isOre(gm.grid[t]) and t not in protected))
    t = getattr(unit, "detour", None)
    if t is None or not wanted(t) or dist(gm, t, i) > HAUL_DETOUR:
        best = None
        for dy in range(-HAUL_DETOUR, HAUL_DETOUR + 1):
            for dx in range(-HAUL_DETOUR, HAUL_DETOUR + 1):
                n = offsetTile(gm, i, dx, dy)
                if n is not None and wanted(n) and (best is None or dist(gm, n, i) < best[0]):
                    best = (dist(gm, n, i), n)
        unit.detour = t = best[1] if best else None
    if t is None:
        return None
    if loose(gm, t) and t in gm.eightAround(i):
        takeFrom(gm, unit, t)
        unit.detour = None
        return i
    if t in gm.neighbors(i):
        if gm.grid[t][0] == 8:
            harvestBy(gm, unit, t)
            unit.detour = None
        else:
            digWall(gm, i, unit, t, unit.wallDamage)
        return i
    if tooLong(gm, unit, t, GATHER_GIVE_UP):
        unit.detour = None
        return None
    return step(gm, i, unit, t, protected, ctx)


def chestSpot(gm, home):
    claimed = claimedTiles(gm)
    spots = [t for t in (offsetTile(gm, home, dx, dy) for dy in range(-CHEST_SPOT[1], CHEST_SPOT[1] + 1)
                         for dx in range(-CHEST_SPOT[1], CHEST_SPOT[1] + 1))
             if t is not None and gm.grid[t][0] == 0 and t not in claimed and CHEST_SPOT[0] <= dist(gm, t, home) <= CHEST_SPOT[1]]
    return rand.choice(spots) if spots else None


def chestAt(gm, t):
    tile = gm.enemyOccupiedItemSpaces.get(t) or gm.grid[t]
    return tile[2] if tile[0] == 3 else []


def chestSlots(items):
    """How many slots a chest has (CAMP_CHEST_SLOTS, or FARM_CHEST_SLOTS for a farming hut's)."""
    return getattr(items, "slots", CAMP_CHEST_SLOTS)


def roomIn(gm, chest, unit=None):
    """True if the chest has a free slot (or, for unit, already holds a stack of something it carries)."""
    items = chestAt(gm, chest)
    if len(items) < chestSlots(items):
        return True
    held = {it.materialId for it in items if isinstance(it, resources.MaterialStack)}
    return unit is not None and not getattr(unit, "loot", []) and set(getattr(unit, "materials", {})) <= held


def stash(gm, chest, unit):
    """What a unit carries goes into the chest: materials and gold stack up with what's there, items take a slot
    each. Whatever doesn't fit stays with it (it builds another chest)."""
    tile = gm.enemyOccupiedItemSpaces.get(chest) or gm.grid[chest]
    if tile[0] != 3:
        return  # the chest is gone: it keeps what it carries
    items = tile[2]
    base = getattr(unit, "baseGold", unit.gold)
    gold = max(0, unit.gold - base)
    loads = list(getattr(unit, "materials", {}).items()) + ([("gold", gold)] if gold else [])
    kept = {}
    for materialId, amount in loads:
        stack = next((it for it in items if isinstance(it, resources.MaterialStack) and it.materialId == materialId), None)
        if stack is not None:
            stack.amount += amount
        elif len(items) < chestSlots(items):
            items.append(resources.MaterialStack(materialId, amount))
        else:
            kept[materialId] = amount
    unit.gold = base + kept.pop("gold", 0)
    unit.materials = kept
    loot = getattr(unit, "loot", [])
    room = max(0, chestSlots(items) - len(items))
    items.extend(loot[:room])
    unit.loot = loot[room:]
    gm.change = True


def raidTarget(gm, f, home):
    """The nearest chest (war chest or farming hut's) or spawner of another faction (one it isn't at peace with)
    within RAID_REACH of home, or None."""
    theirs = []
    for g in camp(gm)["factions"].values():
        if g is not f and not atPeace(f.id, g.id):
            theirs += list(chests(gm, g)) + farmChests(gm, g) + [t for t, _ in spawnersOf(gm, g)]
    near_ = [c for c in theirs if dist(gm, c, home) <= RAID_REACH]
    return min(near_, key=lambda c: dist(gm, c, home)) if near_ else None


def raidable(gm, f, t):
    """Is t still another faction's chest or spawner?"""
    tile = gm.grid[t]
    if tile[0] == 3:
        return isinstance(tile[2], CampChest) and tile[2].faction != f.id
    return tile[0] == CAMP and tile[2].kind == "spawner" and tile[2].faction != f.id


def wallInTheWay(gm, i, f, target):
    """A wall of the hut target is in (another faction's) right beside i: raiders break through it rather than
    walk round to a door."""
    for g in camp(gm)["factions"].values():
        if g is f:
            continue
        for h in g.huts:
            if target in h["floor"]:
                return next((j for j in gm.neighbors(i) if j in h["walls"] and gm.grid[j][0] == 2), None)
    return None


def raidTurn(gm, i, unit, squad, f, ctx):
    """To the other faction's chest or spawner, breaking through the walls of its hut on the way. A chest it smashes
    open, takes what's in it, then hauls it home; a spawner it smashes to rubble."""
    target = squad.raid
    tile = gm.grid[target]
    if not raidable(gm, f, target):
        squad.raid = None  # someone else got it first
        return i
    owner = camp(gm)["factions"].get(tile[2].faction)
    if owner is not None and getattr(owner, "abandoned", False):  # an empty camp: walk in and claim it (claimStep)
        if target in gm.neighbors(i):
            squad.raid = None
            return i
        return step(gm, i, unit, target, f.walls(), ctx, bonfireField(gm, target))
    if target not in gm.neighbors(i):  # chests don't move: the floor-wide path map, like a bonfire's
        wall_ = wallInTheWay(gm, i, f, target) if unit.wallDamage > 0 else None
        if wall_ is not None:
            digWall(gm, i, unit, wall_, unit.wallDamage)
            return i
        return step(gm, i, unit, target, f.walls(), ctx, bonfireField(gm, target))
    if tile[0] == CAMP:
        s = tile[2]
        damage = max(unit.damage, unit.wallDamage)
        s.hp -= damage
        crack(gm, s, damage)
        gm.change = True
        if s.hp <= 0:
            breakSpawner(gm, target, unit)
            squad.raid = None
        return i
    chest = tile[2]
    chest.hp -= unit.damage
    crack(gm, chest, unit.damage)
    gm.change = True
    if chest.hp > 0:
        return i
    left, gold = take(unit, list(chest))  # the loot goes to whoever broke it open, what fits of it
    gm.grid[target] = [0, tile[1]]
    if left or gold:
        gm.placeItems(target, left, gold)
    squad.raid = None
    squad.hauling = squadLoad(squad) >= HAUL_AT  # home only once it's full enough
    return i


def take(unit, things, gold=0):
    """unit picks up what fits of things (items and material stacks) and gold. Returns (what's left, gold left)."""
    loot_ = unit.__dict__.setdefault("loot", [])
    left = []
    for item in things:
        if isinstance(item, resources.MaterialStack):
            if item.materialId == "gold":
                gold += item.amount
                continue
            took = min(item.amount, fitAmount(unit, item.materialId))
            if took > 0:
                unit.materials[item.materialId] = unit.materials.get(item.materialId, 0) + took
            if item.amount > took:
                left.append(resources.MaterialStack(item.materialId, item.amount - took))
        elif roomFor(unit) > 0:
            loot_.append(item)
        else:
            left.append(item)
    if gold and (pickedGold(unit) or roomFor(unit) > 0):
        unit.gold += gold
        gold = 0
    return left, gold


def takeFrom(gm, unit, t):
    """unit empties what fits from the floor chest or item pile at t."""
    tile = gm.grid[t]
    if tile[0] == 3:
        left, _ = take(unit, list(tile[2]))
        tile[2][:] = left  # an empty chest stays, like when you loot one
    else:
        left, gold = take(unit, tile[2].items, tile[2].gold)
        if left or gold:
            tile[2].items, tile[2].gold = left, gold
        else:
            gm.grid[t] = [0, tile[1]]
    gm.change = True


def loose(gm, t):
    """True if tile t is a floor chest (not a warcamp chest) or an item pile with something in it."""
    tile = gm.grid[t]
    if tile[0] == 3:
        return not isinstance(tile[2], CampChest) and len(tile[2]) > 0
    return tile[0] == 9 and (tile[2].items or tile[2].gold)


def scavengeTurn(gm, i, unit, squad, f, home, ctx):
    """Empties the nearest floor chest or item pile near its leader. None if there's nothing to pick up (or it's
    full)."""
    if roomFor(unit) <= 0:
        return None
    leader = squadLeader(squad)
    leaderAt = i if leader is unit else find(gm, ctx, leader)
    if leaderAt is None:
        return None
    home = None if onMission(squad) else home  # (out on a mission it gathers anywhere)
    t = getattr(unit, "scavenging", None)
    if t is None or not loose(gm, t) or dist(gm, t, leaderAt) > MINE_REACH:
        unit.scavenging = t = lootNear(gm, leaderAt, home)
    if t is None:
        return None
    if t in gm.eightAround(i):
        takeFrom(gm, unit, t)
        unit.scavenging = None
        return i
    return step(gm, i, unit, t, f.walls(), ctx)


def lootNear(gm, position, home):
    best = None
    for dy in range(-MINE_REACH, MINE_REACH + 1):
        for dx in range(-MINE_REACH, MINE_REACH + 1):
            t = offsetTile(gm, position, dx, dy)
            if t is None or not loose(gm, t) or (home is not None and dist(gm, t, home) > MINE_RANGE):
                continue
            d = dist(gm, t, position)
            if best is None or d < best[0]:
                best = (d, t)
    return best[1] if best else None


def mineTurn(gm, i, unit, squad, f, home, ctx):
    """Mines the nearest ore vein or Gold Wall near its leader (and its camp). None if there's nothing to mine (or
    it's full)."""
    if roomFor(unit) <= 0:
        return None
    leader = squadLeader(squad)
    leaderAt = i if leader is unit else find(gm, ctx, leader)
    if leaderAt is None:
        return None
    home = None if onMission(squad) else home
    t = getattr(unit, "mining", None)
    if t is None or not isOre(gm.grid[t]) or dist(gm, t, leaderAt) > MINE_REACH:
        unit.mining = t = oreNear(gm, leaderAt, home, f)
    if t is None:
        return None
    if t in gm.neighbors(i):
        digWall(gm, i, unit, t, unit.wallDamage)  # what it digs out goes in its pockets (gameManager.enemyBrokeWall)
        return i
    return step(gm, i, unit, t, f.walls(), ctx)


def oreNear(gm, position, home, f):
    protected = f.walls()
    best = None
    for dy in range(-MINE_REACH, MINE_REACH + 1):
        for dx in range(-MINE_REACH, MINE_REACH + 1):
            t = offsetTile(gm, position, dx, dy)
            if t is None or t in protected or not isOre(gm.grid[t]) or (home is not None and dist(gm, t, home) > MINE_RANGE):
                continue
            d = dist(gm, t, position)
            if best is None or d < best[0]:
                best = (d, t)
    return best[1] if best else None


def gatherTurn(gm, i, unit, squad, f, home, ctx):
    """Picks the nearest plant near its leader (and its camp), keeping the herb and any seed to haul home. None if
    there's nothing to pick (or it's full). Farm plots are left alone: their farmers pick those."""
    if roomFor(unit) <= 0:
        return None
    leader = squadLeader(squad)
    leaderAt = i if leader is unit else find(gm, ctx, leader)
    if leaderAt is None:
        return None
    t = getattr(unit, "gathering", None)
    if t is None or not pickable(gm, t) or dist(gm, t, leaderAt) > MINE_REACH:
        unit.gathering = t = plantNear(gm, leaderAt, MINE_REACH, *((leaderAt, MINE_REACH) if onMission(squad) else
                                                                   (home, MINE_RANGE)), avoid=setAside(gm, unit))
    if t is None:
        return None
    if t in gm.neighbors(i):
        harvestBy(gm, unit, t)
        unit.gathering = None
        return i
    if tooLong(gm, unit, t, GATHER_GIVE_UP):  # walled in, or someone always in the way: leave it for now
        unit.gathering = None
        return None
    return step(gm, i, unit, t, f.walls(), ctx)


GATHER_GIVE_UP = 15         # turns a goblin spends getting to a plant before it leaves it for a while...
FARM_GIVE_UP = 25           # ...or a farmer to anything it's going to
SET_ASIDE_TURNS = 150       # ...and how long it leaves it


def tooLong(gm, unit, target, limit):
    """Counts the turns unit has been heading for target. Once that's over limit, target is set aside (see setAside)
    for SET_ASIDE_TURNS and this is True."""
    if getattr(unit, "headingFor", None) != target:
        unit.headingFor, unit.headingTurns = target, 0
    unit.headingTurns += 1
    if unit.headingTurns <= limit:
        return False
    aside = unit.__dict__.setdefault("setAsideUntil", {})
    aside[target] = gm.turnCount + SET_ASIDE_TURNS
    unit.headingFor = None
    return True


def setAside(gm, unit):
    """The targets unit has given up on for now (it couldn't get to them)."""
    aside = getattr(unit, "setAsideUntil", None)
    if not aside:
        return set()
    for t in [t for t, until in aside.items() if until <= gm.turnCount]:
        del aside[t]
    return set(aside)


def pickable(gm, t, kind=None, farmed=None):
    """Is there a wild plant at t a goblin can pick (not Organizer's Demise: its thorns, nor a crop), outside every
    farming hut?"""
    tile = gm.grid[t]
    if tile[0] != 8 or organizers.isDemise(tile) or (kind is not None and tile[2].kind != kind):
        return False
    if getattr(tile[2], "planted", False) or not tile[2].ready:
        return False  # somebody's crop (yours, or a farmer's), or not ripe yet
    return t not in (farmed if farmed is not None else allFarmTiles(gm))


def plantNear(gm, position, reach, home, homeReach, kind=None, avoid=()):
    """The nearest pickable plant (of kind, if given, and not in avoid) within reach of position and homeReach of
    home."""
    farmed = allFarmTiles(gm)
    best = None
    for dy in range(-reach, reach + 1):
        for dx in range(-reach, reach + 1):
            t = offsetTile(gm, position, dx, dy)
            if t is None or t in avoid or not pickable(gm, t, kind, farmed) or dist(gm, t, home) > homeReach:
                continue
            d = dist(gm, t, position)
            if best is None or d < best[0]:
                best = (d, t)
    return best[1] if best else None


def harvestBy(gm, unit, t):
    """unit picks the (ripe) plant at t: what its stage gives, its herb or seeds, goes in its pockets (like yours)."""
    tile = gm.grid[t]
    stage = tile[2].pick()
    for materialId, amount in loot.rollPick(tile[2], stage) if stage else ():
        unit.materials[materialId] = unit.materials.get(materialId, 0) + amount
    gm.grid[t] = [0, tile[1]]
    gm.change = True


def wallsToClear(gm, ctx, f):
    """Walls f's waiting squads break: the ones in its unfinished huts the builders have to break, then any within
    CLEAR_RADIUS of its bonfires that aren't hut walls, farm plots, Organizer patterns, someone else's ground or the
    map's edge. Worked out once a turn."""
    cache = ctx.setdefault("toClear", {})
    if f.id in cache:
        return cache[f.id]
    walls = set()
    for h in f.huts:
        if not h["done"]:
            walls |= {t for t in h["floor"] if gm.grid[t][0] == 2 and not floored(gm, h, t)}
    claimed, protected, R = claimedTiles(gm), f.walls(), gm.rowLength
    for b in f.bonfires:
        for dy in range(-CLEAR_RADIUS, CLEAR_RADIUS + 1):
            for dx in range(-CLEAR_RADIUS, CLEAR_RADIUS + 1):
                t = offsetTile(gm, b, dx, dy)
                if t is None or gm.grid[t][0] != 2 or t in claimed or t in protected or dist(gm, t, b) > CLEAR_RADIUS:
                    continue
                if t % R in (0, R - 1) or t < R or t + R >= gm.numberOfSpots:
                    continue  # (the map's edge stays)
                walls.add(t)
    cache[f.id] = walls
    return walls


def clearTurn(gm, i, unit, f, ctx):
    """A goblin waiting at the bonfire breaks the nearest wall to clear (wallsToClear). None if there's none (or it's
    full: what walls give goes in its pockets)."""
    if roomFor(unit) <= 0 or not f.bonfires:
        return None
    walls = wallsToClear(gm, ctx, f)
    t = getattr(unit, "clearing", None)
    if t is None or t not in walls or gm.grid[t][0] != 2:
        aside = setAside(gm, unit)
        taken = ctx.setdefault("clearTaken", set())
        standing = [w for w in walls if gm.grid[w][0] == 2 and w not in aside]  # (some may be broken this turn)
        options = [w for w in standing if w not in taken] or standing
        unit.clearing = t = min(options, key=lambda w: dist(gm, w, i)) if options else None
    if t is None:
        return None
    ctx.setdefault("clearTaken", set()).add(t)
    if t in gm.neighbors(i):
        digWall(gm, i, unit, t, unit.wallDamage)
        if gm.grid[t][0] != 2:
            unit.clearing = None
        return i
    if tooLong(gm, unit, t, GATHER_GIVE_UP):
        unit.clearing = None
        return None
    return step(gm, i, unit, t, f.walls(), ctx)


def onMission(squad):
    return getattr(squad, "mission", None) is not None


def missionTurn(gm, i, leader, squad, f, home, ctx):
    """The leader of a squad with nothing to fight: out to a random spot anywhere on the floor and back home (the
    others follow it, and everyone gathers what they pass on the way, see soldierTurn). None if there's nowhere
    to go."""
    m = getattr(squad, "mission", None)
    if m is None:
        goal = missionSpot(gm, home)
        if goal is None:
            return None
        m = squad.mission = {"goal": goal, "back": False, "turns": 0}
    m["turns"] += 1
    target = home if m["back"] else m["goal"]
    if dist(gm, i, target) <= 3 or m["turns"] > MISSION_TURNS:
        if m["back"]:  # home again: it stashes what it brought back, then the next mission starts
            squad.mission = None
            squad.hauling = any(carried(u) > 0 for u in squad.members if u.hp > 0)
            return i
        m["back"], m["turns"], target = True, 0, home
    return step(gm, i, leader, target, f.walls(), ctx, bonfireField(gm, target))


def missionSpot(gm, home):
    """A random open tile anywhere on the floor that can be walked to from home, at least MISSION_MIN away."""
    paths = bonfireField(gm, home)
    spots = [t for t, d in paths.items() if d >= MISSION_MIN and gm.grid[t][0] == 0]
    return rand.choice(spots) if spots else None


def patrolSpot(gm, home):
    R = gm.rowLength
    for _ in range(20):
        t = offsetTile(gm, home, rand.randint(-PATROL_RADIUS, PATROL_RADIUS), rand.randint(-PATROL_RADIUS, PATROL_RADIUS))
        if t is not None and gm.grid[t][0] == 0 and dist(gm, t, home) <= PATROL_RADIUS:
            return t
    return None


# ---------------------------------------------------------------- the builder

def builderTurn(gm, i, b, ctx):
    f = faction(gm, b)
    if f is None:
        return organizers.wander(gm, i)
    if migrating(f) is not None and not f.bonfires and dist(gm, i, f.migrating) > ARRIVE_REACH:
        return migrateTurn(gm, i, b, f, ctx)  # (once there, it lights the new camp's bonfire: planTask)
    if getattr(b, "rest", 0) > 0:
        b.rest -= 1
        return organizers.wander(gm, i)
    home = homeBonfire(gm, f, i)
    if getattr(b, "task", None) is None and home is not None and BONFIRE_REACH < dist(gm, home, i) <= HOME_REACH:
        return step(gm, i, b, home, f.walls(), ctx)  # wandered off: back to camp first
    if getattr(b, "task", None) is None:
        b.task = planTask(gm, i, b, f)
        if b.task is None:
            b.rest = 10
            return organizers.wander(gm, i)
    task = b.task
    if task["kind"] == "feed":
        return feedTurn(gm, i, b, f, task, ctx)
    if task["kind"] == "bonfire":
        return buildBonfire(gm, i, b, f, task, ctx)
    return buildHut(gm, i, b, f, task, ctx)


def finishTask(b):
    b.task = None
    b.rest = rand.randint(*BUILDER_REST)


def claimedTiles(gm):
    """Tiles no new hut may cover: every faction's huts and every Organizer's patterns."""
    claimed = set(organizers.gather(gm)["claimed"])
    for f in camp(gm)["factions"].values():
        for h in f.huts:
            claimed |= h["floor"]
        claimed |= farmTiles(f)
    return claimed


def nearestEnemyBonfire(gm, f, position):
    others = [b for g in camp(gm)["factions"].values() if g is not f for b in g.bonfires]
    return min((dist(gm, b, position) for b in others), default=None)


def finishedHuts(f):
    """Its finished huts with spawners (not storage huts)."""
    return sum(1 for h in f.huts if h["done"] and h.get("kind", "hut") == "hut")


def planTask(gm, i, b, f):
    home = homeBonfire(gm, f, i)
    together = finishedHuts(f) < TOGETHER_HUTS
    if home is None or dist(gm, home, i) > HOME_REACH:  # no camp to go back to: start one here
        if together:  # ...or help the builder already lighting the camp's first bonfire
            shared = next((other.task for other in builders(gm) if other is not b and factionOf(other) == f.id
                           and getattr(other, "task", None) and other.task["kind"] == "bonfire"), None)
            if shared is not None:
                return {"kind": "bonfire", "at": shared["at"]}
        if not f.bonfires and f.huts:  # a seized hut with no bonfire yet: light one just outside it
            hut = min(f.huts, key=lambda h: dist(gm, h["center"], i))
            spot = bonfireSpot(gm, hut["center"], i, hut.get("radius", 3) + 1, HUT_DISTANCE[1])
            if spot is not None:
                return {"kind": "bonfire", "at": spot}
        spot = bonfireSpot(gm, i, i, 0, 3, avoid=f if f.bonfires else None)  # (a camp's first: where it was going)
        return {"kind": "bonfire", "at": spot} if spot is not None else None
    for hut in f.huts:
        if hut["done"] and damaged(gm, hut):
            hut["done"] = False  # it lost walls, its spawner or a chest: it's built back up before any new hut
    feed = feedTask(gm, i, b, f)
    if feed is not None:  # a spawner running low on food, and food in the chests (or on it) to bring it: before
        return feed       # anything else, even storage (a camp that can't spawn dies out while it builds)
    needStorage = storageNeeded(gm, f)
    if needStorage:  # the storage is full (or there's none yet): every builder works on the next storage hut
        building = next((h for h in f.huts if h.get("kind") == "storage" and not h["done"]), None)
        if building is not None:
            return {"kind": "hut", "hut": building}
    for hut in f.huts:
        if hut["done"]:
            continue
        if together:  # the camp's first huts: everyone builds the same one
            return {"kind": "hut", "hut": hut}
        owner = hut.get("builder")  # a hut another builder started and didn't finish comes first
        if owner is None or owner.hp <= 0 or factionOf(owner) != f.id \
                or (getattr(owner, "task", None) or {}).get("hut") is not hut:
            hut["builder"] = b
            return {"kind": "hut", "hut": hut}
    claimed = claimedTiles(gm)
    farmer = unhousedFarmer(gm, f)
    if farmer is not None:  # a farmer with seeds and no farming hut: pair up with it and build it one
        hut = newHutSite(gm, f, i, "farm", claimed)
        if hut is not None:
            hut.update(builder=b, farmer=farmer, floorType=farmFloor(farmer))
            f.huts.append(hut)
            return {"kind": "hut", "hut": hut}
    count = lambda k: sum(1 for h in f.huts if h.get("kind", "hut") == k)
    kind = "storage" if needStorage and count("storage") < MAX_STORAGE_HUTS else "hut"
    if kind == "hut" and any(h.get("spawned", 0) < HUT_SPAWNS for h in f.huts if h.get("kind", "hut") == "hut"):
        # a spawner hut that hasn't made HUT_SPAWNS goblins yet: no new one. Help with one that's being built, if any.
        building = next((h for h in f.huts if not h["done"]), None)
        return {"kind": "hut", "hut": building} if building is not None else None
    hut = newHutSite(gm, f, i, kind, claimed)
    if hut is not None:
        hut["builder"] = b
        f.huts.append(hut)
        return {"kind": "hut", "hut": hut}
    # no room around any bonfire: light a new one further out (one builder at a time, where a hut will fit)
    if any(getattr(other, "task", None) and other.task["kind"] == "bonfire" and other is not b and other.hp > 0
           and factionOf(other) == f.id for other in builders(gm)):
        return None
    spot = bonfireSpot(gm, home, i, *NEW_BONFIRE_DISTANCE, avoid=f, needRoom=claimed)
    return {"kind": "bonfire", "at": spot} if spot is not None else None


def newHutSite(gm, f, i, kind, claimed):
    """A new hut of this kind laid out near one of f's bonfires (the nearest to i first), or None if none fits."""
    sites = []
    reach = HUT_DISTANCE[1]
    for bonfire in sorted(f.bonfires, key=lambda p: dist(gm, p, i)):
        centers = [offsetTile(gm, bonfire, dx, dy) for dy in range(-reach, reach + 1) for dx in range(-reach, reach + 1)]
        rand.shuffle(centers)
        for center in centers:  # every spot around it, so it only lights a new bonfire when there's truly no room
            if center is None or not HUT_DISTANCE[0] <= dist(gm, center, bonfire) <= HUT_DISTANCE[1]:
                continue
            if len(sites) >= 12:
                break
            hut = layOutHut(gm, center, claimed, kind)
            if hut is None:
                continue
            enemyBonfire = nearestEnemyBonfire(gm, f, center)
            if enemyBonfire is not None and enemyBonfire < dist(gm, center, bonfire):
                continue  # the other faction's ground
            sites.append((dist(gm, center, bonfire) + rand.random() * 3, hut))
        if sites:
            break
    return min(sites, key=lambda s: s[0])[1] if sites else None

def builders(gm):
    for p in set(gm.EnemyPositions) | getattr(gm, "movedEnemies", set()):
        tile = gm.grid.get(p)
        if tile and tile[0] == 5 and len(tile) > 2 and tile[2].name == "Goblin Builder":
            yield tile[2]


def roomForHut(gm, bonfire, claimed):
    """True if at least one hut would fit around a bonfire at this spot."""
    reach = HUT_DISTANCE[1]
    centers = [offsetTile(gm, bonfire, dx, dy) for dy in range(-reach, reach + 1) for dx in range(-reach, reach + 1)]
    rand.shuffle(centers)
    for center in centers:
        if center is not None and HUT_DISTANCE[0] <= dist(gm, center, bonfire) <= reach and                 layOutHut(gm, center, claimed | {bonfire}) is not None:
            return True
    return False


def bonfireSpot(gm, center, near_, low, high, avoid=None, needRoom=None):
    """An open floor tile low..high tiles from center, nearest to near_, clear of every hut. With needRoom (the
    claimed tiles), only a spot with room for a hut around it (the nearest few candidates are checked)."""
    claimed = claimedTiles(gm)
    candidates = set()
    for _ in range(60):
        t = offsetTile(gm, center, rand.randint(-high, high), rand.randint(-high, high))
        if t is None or gm.grid[t][0] != 0 or t in claimed or not low <= dist(gm, t, center) <= high:
            continue
        if avoid is not None:
            enemyBonfire = nearestEnemyBonfire(gm, avoid, t)
            if enemyBonfire is not None and (enemyBonfire < dist(gm, t, center) or enemyBonfire < CAMP_GAP):
                continue  # the other faction's ground, or too close to it
        candidates.add(t)
    for t in sorted(candidates, key=lambda t: dist(gm, t, near_))[:8]:
        if needRoom is None or roomForHut(gm, t, needRoom):
            return t
    return None


def layOutHut(gm, center, claimed, kind="hut"):
    """A hut ("hut": a spawner in the middle), storage hut ("storage": war chests along its walls) or farming hut
    ("farm": plant beds round a chest in the middle) centered at center, with an entrance in the middle of each side,
    or None if it doesn't fit."""
    store = kind == "storage"
    r = STORAGE_RADIUS if store else 3
    doors = [(0, -r), (0, r), (-r, 0), (r, 0)]  # an entrance in the middle of every side
    floor = [offsetTile(gm, center, dx, dy) for dy in range(-r - 1, r + 2) for dx in range(-r - 1, r + 2)]
    if None in floor:
        return None
    floor = set(floor)
    if floor & claimed or gm.playerPositionFlat in floor:
        return None
    if any(gm.grid[t][0] in (3, 4, 6, 7, 9, CAMP, HOLE) for t in floor):  # no chests, piles, doors, stations, camp
        # pieces or holes
        return None
    walls = [offsetTile(gm, center, dx, dy) for dx, dy in hutWalls(doors, r)]
    spots = [offsetTile(gm, center, dx, dy) for dx, dy in STORAGE_CHESTS] if store else []
    inside = [offsetTile(gm, center, dx, dy) for dy in range(1 - r, r) for dx in range(1 - r, r)
              if (store or (dx, dy) != (0, 0))]
    hut = {"center": center, "floor": floor, "walls": walls, "inside": [t for t in inside if t not in spots],
           "skip": set(), "done": False, "builder": None, "kind": kind, "radius": r}
    if store:
        hut["chests"] = spots
    if kind == "farm":  # beds in the 4 corners, a cross of paths from the doors to the chest in the middle
        hut["beds"] = [offsetTile(gm, center, dx, dy) for dy in range(1 - r, r) for dx in range(1 - r, r) if dx and dy]
        hut["chest"] = center
    return hut


def goNextTo(gm, i, b, target, f, ctx, standOn=False):
    """Walks toward a spot beside target (or onto it, when standOn). Returns (position, there yet)."""
    spots = ([target] if standOn else []) + gm.neighbors(target)
    if i in spots:
        return i, True
    return step(gm, i, b, target, f.walls(), ctx), False


def work(owner, what, needed):
    """One turn of work on what. The work is kept on owner (a hut or a faction), so builders working together add
    up. True once it has had needed turns (then it's cleared)."""
    progress = owner.__dict__ if not isinstance(owner, dict) else owner
    done = progress.setdefault("progress", {})
    if not isinstance(done, dict):  # huts from before builders shared work
        done = progress["progress"] = {}
    done[what] = done.get(what, 0) + 1
    if done[what] >= needed:
        del done[what]
        return True
    return False

def buildBonfire(gm, i, b, f, task, ctx):
    at = task["at"]
    if gm.grid[at][0] != 0:  # someone's standing there, or it's lit already: pick something else to do
        b.task = None
        return i
    position, there = goNextTo(gm, i, b, at, f, ctx)
    if not there:
        if tooLong(gm, b, at, BONFIRE_GIVE_UP):  # it can't get there: pick something else (another spot, or feeding)
            b.task = None
        return position
    if work(f, ("bonfire", at), BONFIRE_TURNS):
        place(gm, at, Structure("bonfire", f.id))
        f.bonfires.append(at)
        if migrating(f) is not None:  # a schism's new camp is lit: they've settled, and the peace is over
            f.migrating = f.peaceWith = None
        if f.first is None or f.first not in f.bonfires:
            f.first = at
        finishTask(b)
    return i

def place(gm, t, structure):
    gm.grid[t] = [CAMP, gm.grid[t][1], structure]
    camp(gm)["structures"].add(t)
    gm.change = True


def isStone(gm, t):
    return t in gm.rooms["Stone"] and gm.grid[t][0] != 2


def floored(gm, hut, t):
    """True once tile t of the hut is Stone floor. A wall standing where one of the hut's walls goes counts: the
    builder claims it later instead of breaking it (see needsWall), unless it's an ore vein or gold, which it breaks
    so their ore isn't lost."""
    tile = gm.grid[t]
    if tile[0] == 2 and t in hut["walls"]:
        return not isOre(tile)
    if tile[0] == 8 and hut.get("kind") == "farm" and not getattr(tile[2], "planted", False):
        return False  # a wild plant in a farming hut: pulled up as the floor is laid
    return plants.floorOf(t, gm.rooms) == hut.get("floorType", "Stone") and tile[0] != 2


def layFloor(gm, hut, t):
    """Tile t of the hut becomes its floor type (Stone, or a farming hut's own), pulling up any wild plant there."""
    tile = gm.grid[t]
    if tile[0] == 8 and not getattr(tile[2], "planted", False):
        gm.grid[t] = [0, tile[1]]
    for room in gm.rooms.values():
        room.discard(t)
    gm.rooms.setdefault(hut.get("floorType", "Stone"), set()).add(t)
    gm.change = True


def needsWall(gm, hut, t):
    """Does hut wall spot t still need work? Built (painted) walls are done; any other wall there gets claimed."""
    tile = gm.grid[t]
    return t not in hut["skip"] and not (tile[0] == 2 and getattr(tile[2], "paint", None))


def claimWall(gm, hut, t, look):
    """The wall standing at t becomes one of the hut's walls: a fresh Stone Wall in the faction's colors."""
    for room in gm.rooms.values():
        room.discard(t)
    gm.rooms["Stone"].add(t)
    gm.grid[t] = [2, gm.grid[t][1], gm.createWall(t, gm.rooms)]
    paintHutWall(gm, hut, t, look)
    gm.change = True


def hutStage(gm, hut):
    """What a hut needs next: every floor tile laid in its floor type (Stone, or a farming hut's own) first, then
    every wall, then the spawner (a storage hut's chests, a farming hut's chest)."""
    if any(not floored(gm, hut, t) for t in hut["floor"]):
        return "floor"
    if any(needsWall(gm, hut, t) for t in hut["walls"]):
        return "walls"
    return "chests" if hut.get("kind") == "storage" else "spawner"  # (a farming hut's chest goes where a spawner would)


def damaged(gm, hut):
    """Has a finished hut lost a wall (broken, or never painted), its spawner, or (a storage hut) a chest?"""
    if hut.get("kind") == "storage":
        if any(gm.grid[t][0] in (0, 8) for t in hut["chests"]):
            return True
    elif gm.grid[hut["center"]][0] in (0, 8):
        return True
    return any(needsWall(gm, hut, t) and gm.grid[t][0] in (0, 2, 8) for t in hut["walls"])


def pick(gm, hut, b, todo, i):
    """The nearest tile in todo that no other builder is working on (builders on the same hut split the work)."""
    claims = hut.setdefault("claims", {})
    for t, other in list(claims.items()):
        if other is b or other.hp <= 0 or (getattr(other, "task", None) or {}).get("hut") is not hut:
            del claims[t]
    free = [t for t in todo if t not in claims] or todo
    t = min(free, key=lambda t: dist(gm, t, i))
    claims[t] = b
    return t


def buildHut(gm, i, b, f, task, ctx):
    hut = task["hut"]
    if hut not in f.huts or hut["done"]:  # it went to the other faction in a split, or someone finished it
        b.task = None
        return i
    if hut.get("kind") == "farm" and not hut.get("built"):  # a farming hut is built with its farmer: wait for it
        farmer = hut.get("farmer")
        if farmer is not None and farmer.hp > 0 and factionOf(farmer) == f.id:
            p = ctx["pos"].get(id(farmer))
            if p is None or dist(gm, p, hut["center"]) > FARM_PAIR_REACH:
                return goNextTo(gm, i, b, hut["center"], f, ctx)[0] if dist(gm, i, hut["center"]) > 4 else i
    stage = hutStage(gm, hut)
    if stage == "floor":
        t = pick(gm, hut, b, [t for t in hut["floor"] if not floored(gm, hut, t)], i)
        if gm.grid[t][0] == 2:  # a wall in the way: break it first
            position, there = goNextTo(gm, i, b, t, f, ctx)
            if there:
                digWall(gm, i, b, t, BREAK_DAMAGE)
            return position
        position, there = goNextTo(gm, i, b, t, f, ctx, standOn=True)
        if there and work(hut, ("floor", t), FLOOR_TURNS):
            layFloor(gm, hut, t)
        return position
    if stage == "walls":
        todo = []
        for t in hut["walls"]:
            kind = gm.grid[t][0]
            if not needsWall(gm, hut, t):
                continue
            if kind == 2:  # a wall already standing here: claim it
                todo.append(t)
                continue
            if kind in (3, 4, 6, 7, 9, CAMP, HOLE):  # something there now (or the floor's gone): leave a gap
                hut["skip"].add(t)
                continue
            if kind == 8:  # a plant grew there: pull it up
                gm.grid[t] = [0, gm.grid[t][1]]
            if gm.grid[t][0] in (0, 5) and t != i:
                todo.append(t)
        if not todo:  # the rest are occupied (or it's standing on the last one): step off and wait
            return organizers.wander(gm, i)
        t = pick(gm, hut, b, todo, i)
        position, there = goNextTo(gm, i, b, t, f, ctx)
        if gm.grid[t][0] == 2:
            if there and work(hut, ("claim", t), CLAIM_TURNS):
                claimWall(gm, hut, t, f.look)
            return position
        if there and gm.grid[t][0] != 0:  # one of its own goblins standing there: shoo it
            return makeWay(gm, ctx, i, t, f, b)
        if there and wouldTrap(gm, t) is not None:  # it would shut someone (maybe itself) in: let them out first
            return leaveNook(gm, ctx, i, b, t, f)
        if there and work(hut, ("wall", t), WALL_TURNS):
            gm.grid[t] = [2, gm.grid[t][1], gm.createWall(t, gm.rooms)]
            paintHutWall(gm, hut, t, f.look)
            gm.change = True
        return position
    if stage == "chests":
        return buildChests(gm, i, b, f, hut, ctx)
    # the spawner, in the middle: every builder on the hut helps
    c = hut["center"]
    if gm.grid[c][0] == 8:  # a plant grew there: pull it up
        gm.grid[c] = [0, gm.grid[c][1]]
    if gm.grid[c][0] not in (0, 5):  # something else landed there: give up on this hut's spawner
        hut["done"] = True
        finishTask(b)
        return i
    if gm.grid[c][0] == 5:  # someone standing in the middle: shoo them if it's one of ours, else wait
        if c in gm.neighbors(i):
            return makeWay(gm, ctx, i, c, f, b)
        return goNextTo(gm, i, b, c, f, ctx)[0]
    position, there = goNextTo(gm, i, b, c, f, ctx)
    if there and work(hut, ("spawner", c), SPAWNER_TURNS):
        if hut.get("kind") == "farm":  # its chest
            gm.grid[c] = [3, gm.grid[c][1], CampChest(f.id, f.look, slots=FARM_CHEST_SLOTS)]
            hut["built"] = True
            gm.change = True
        else:
            place(gm, c, Structure("spawner", f.id, hut=c))
        hut["done"] = True
        finishTask(b)
    return position


# ---------------------------------------------------------------- the farmer
# A farmer only farms in a farming hut ("farm", see layOutHut). A builder pairs up with a farmer that carries seeds but
# has no farming hut and builds it one, laying its whole floor in the floor type that suits most of that farmer's
# seeds (farmFloor); the farmer comes and helps lay it, and the builder waits for it to be there (FARM_PAIR_REACH).
# Inside, a cross of paths runs from the 4 doors to a chest in the middle, with beds in the 4 corners. Nothing wild
# sprouts in a farming hut (plants.step, noBirth).
#
# The farmer plants seeds in the beds (planted plants never wither, grow in stages and give more: plants.Plant,
# loot.CROP_LOOT) and picks them when they're ripe. Picking uses a plant up, so it picks each in the stage it wants:
# gone to seed while it's short of seeds (fewer than it needs to sow all its beds again plus FARMER_SEEDS_KEPT, on
# it and in its hut's chest: crops can wither, plants.step), else ready to harvest. A plant in its other first stage is left to move on to its second; one in its
# second (last) stage is picked whatever it gives. It pulls up anything else growing in its hut, and never picks
# any plant it didn't sow. What it doesn't keep goes into its hut's chest (only farmers store there; builders take
# food from it for the spawners), or a war chest when that's full. A farmer with no seeds fetches some from the war
# chests. Farmers walk through any plant (canEnter), even ones that block the way.

FARM_KINDS = [k for k, info in plants.PLANTS.items() if info.get("wild", True) and not info.get("conway")]
BASE_FARMERS = SPLIT_FARMERS  # a faction has at most this many farmers (enough for a schism, whatever its size)...
HUTS_PER_FARMER = 4         # ...plus 1 for every this many finished huts
FARM_DISTANCE = (3, 14)     # the war band's farmer brings seeds of a plant growing this near where it turns up
PLANT_TURNS = 1             # a farmer's turns to plant a seed
FARMER_SEEDS_KEPT = 3       # seeds it keeps on it beyond what its empty beds need
FARMER_START_SEEDS = 7      # seeds the war band's farmer brings (and a farmer with none fetches)
FARMER_HAUL = 6             # it puts its harvest away once it carries this much more than it keeps
FARM_PAIR_REACH = 8         # a builder works on a farming hut only while its farmer is this close


def farmerCount(gm, f):
    return sum(1 for p in gm.EnemyPositions if gm.grid[p][0] == 5 and len(gm.grid[p]) > 2
               and gm.grid[p][2].name == "Goblin Farmer" and factionOf(gm.grid[p][2]) == f.id)


def farms(f):
    """f's farming huts."""
    return [h for h in f.huts if h.get("kind") == "farm"]


def farmTiles(f):
    return {t for h in farms(f) for t in h["floor"]}


def allFarmTiles(gm):
    return {t for f in camp(gm)["factions"].values() for t in farmTiles(f)}


def seedOf(kind):
    return plants.PLANTS[kind]["seed"]


def kindsFor(floor):
    """The plants a farmer can grow on this floor type."""
    return [k for k in FARM_KINDS if floor in plants.PLANTS[k]["floors"]]


def carriedSeeds(u, kinds=FARM_KINDS):
    return sum(u.materials.get(seedOf(k), 0) for k in kinds)


def farmFloor(u):
    """The floor type that suits most of the seeds farmer u carries (a farming hut built with it gets this floor)."""
    floors = {}
    for k in FARM_KINDS:
        for floor in plants.PLANTS[k]["floors"]:
            floors[floor] = floors.get(floor, 0) + u.materials.get(seedOf(k), 0)
    return max(floors, key=lambda fl: (floors[fl], fl == "Stone"))


def farmerGone(f, farmer):
    return farmer is None or farmer.hp <= 0 or factionOf(farmer) != f.id


def farmHutOf(f, u):
    """Farmer u's farming hut: its own, or one whose farmer is gone (it takes it over), or None. One still waiting
    for its hut to be built moves into a finished one whose farmer is gone instead (the builder finishes the other
    one for the next farmer)."""
    mine = next((h for h in farms(f) if h.get("farmer") is u), None)
    if mine is not None and not mine["done"] and not mine.get("built"):
        free = next((h for h in farms(f) if h["done"] and farmerGone(f, h.get("farmer"))), None)
        if free is not None:
            mine["farmer"], free["farmer"] = None, u
            return free
    if mine is None:
        mine = next((h for h in farms(f) if farmerGone(f, h.get("farmer"))), None)
        if mine is not None:
            mine["farmer"] = u
    return mine


def unhousedFarmer(gm, f):
    """A farmer of f carrying seeds that has no farming hut (and none left over for it to take on), or None."""
    if any(farmerGone(f, h.get("farmer")) for h in farms(f)):
        return None  # a farming hut without a farmer: one will take it on
    housed = {id(h.get("farmer")) for h in farms(f)}
    return next((u for _, u in factionUnits(gm, f) if u.name == "Goblin Farmer" and id(u) not in housed
                 and carriedSeeds(u) > 0), None)


def ourCrop(f, tile):
    return tile[0] == 8 and getattr(tile[2], "planted", False) and getattr(tile[2], "faction", None) == f.id


def farmChest(gm, hut):
    """The farming hut's chest, if it's standing."""
    c = hut.get("chest")
    return c if c is not None and isinstance(chestAt(gm, c), CampChest) else None


def farmChests(gm, f):
    return [c for h in farms(f) if h["done"] for c in [farmChest(gm, h)] if c is not None]


def chestStock(gm, f):
    """{material id: amount} across the faction's war chests."""
    stock = {}
    for c in chests(gm, f):
        for it in chestAt(gm, c):
            if isinstance(it, resources.MaterialStack):
                stock[it.materialId] = stock.get(it.materialId, 0) + it.amount
    return stock


def stockIn(gm, chest):
    """{material id: amount} in one chest."""
    stock = {}
    for it in chestAt(gm, chest) if chest is not None else ():
        if isinstance(it, resources.MaterialStack):
            stock[it.materialId] = stock.get(it.materialId, 0) + it.amount
    return stock


def chestWith(gm, f, materialId, position):
    """The nearest of the faction's war chests holding some of materialId, or None."""
    have = [c for c in chests(gm, f) if any(isinstance(it, resources.MaterialStack) and it.materialId == materialId
                                           and it.amount > 0 for it in chestAt(gm, c))]
    return min(have, key=lambda c: dist(gm, c, position)) if have else None


def withdraw(gm, chest, unit, materialId, amount):
    """unit takes up to amount of materialId out of the chest."""
    items = chestAt(gm, chest)
    stack = next((it for it in items if isinstance(it, resources.MaterialStack) and it.materialId == materialId), None)
    if stack is None:
        return
    took = min(amount, stack.amount)
    stack.amount -= took
    if stack.amount <= 0:
        items.remove(stack)
    unit.materials[materialId] = unit.materials.get(materialId, 0) + took
    gm.change = True


def spare(u, keep):
    """{material id: amount} the farmer carries beyond the seeds it keeps."""
    return {m: a - keep.get(m, 0) for m, a in u.materials.items() if a > keep.get(m, 0)}


def putAway(gm, chest, u, keep):
    """Everything but the seeds it keeps goes in the chest."""
    kept = {m: min(a, keep[m]) for m, a in u.materials.items() if m in keep}
    u.materials = {m: a - kept.get(m, 0) for m, a in u.materials.items() if a - kept.get(m, 0) > 0}
    stash(gm, chest, u)
    for m, a in kept.items():
        if a > 0:
            u.materials[m] = u.materials.get(m, 0) + a


def farmJob(gm, i, u, f, hut):
    """What the farmer does next in its (finished) farming hut: ("weed", tile), ("pick", tile), ("plant", tile, kind),
    ("fetch", chest, seed, amount), ("stash", chest, seeds kept), or None for nothing."""
    nearest = lambda ts: min(ts, key=lambda t: dist(gm, t, i))
    aside = setAside(gm, u)  # what it couldn't get to lately
    beds, kinds, chest = set(hut["beds"]), kindsFor(hut.get("floorType", "Stone")), farmChest(gm, hut)
    # 1. pull up whatever else grows in its hut
    weeds = [t for t in hut["inside"] if t not in aside and gm.grid[t][0] == 8
             and not (t in beds and ourCrop(f, gm.grid[t])) and not organizers.isDemise(gm.grid[t])]
    if weeds:
        return ("weed", nearest(weeds))
    empty = [t for t in hut["beds"] if t not in aside and gm.grid[t][0] == 0
             and plants.floorOf(t, gm.rooms) == hut.get("floorType", "Stone")]
    stored = stockIn(gm, chest)
    seedsHave = carriedSeeds(u, kinds) + sum(stored.get(seedOf(k), 0) for k in kinds)
    short = seedsHave < len(hut["beds"]) + FARMER_SEEDS_KEPT  # (enough to sow every bed again: crops can wither)
    # 2. pick what's ripe and sow the empty beds, whichever is nearest (less walking). Picking uses a plant up, so a
    #    plant is only picked in the stage it wants (gone to seed while it's short of seeds, else ready to harvest),
    #    or in its last stage (it won't change any more). A plant in its other first stage is left to ripen on.
    want = "seed" if short else "harvest"
    ripe = [t for t in hut["beds"] if t not in aside and ourCrop(f, gm.grid[t]) and gm.grid[t][2].ready
            and (gm.grid[t][2].stage == want or gm.grid[t][2].lastStage)]
    best = max(kinds, key=lambda k: u.materials.get(seedOf(k), 0)) if kinds else None
    sow = empty if best is not None and u.materials.get(seedOf(best), 0) > 0 else []
    seeding = [t for t in ripe if gm.grid[t][2].stage == "seed"]
    if short and seeding:
        return ("pick", nearest(seeding))
    if ripe or sow:
        t = nearest(ripe + sow)
        return ("pick", t) if t in ripe else ("plant", t, best)
    keep = {seedOf(k): len(empty) + FARMER_SEEDS_KEPT for k in kinds}
    extra = spare(u, keep)
    store = chest if chest is not None and chest not in aside and roomIn(gm, chest, u) else \
        next((c for c in sorted(chests(gm, f), key=lambda c: dist(gm, c, i)) if c not in aside and roomIn(gm, c, u)), None)
    if store is not None and sum(extra.values()) >= FARMER_HAUL:
        return ("stash", store, keep)
    # 3. no seeds for its empty beds: fetch some (from its hut's chest, else the war chests)
    if empty:
        for k in sorted(kinds, key=lambda k: -stored.get(seedOf(k), 0)):
            seed = seedOf(k)
            if stored.get(seed, 0) > 0 and chest not in aside:
                return ("fetch", chest, seed, len(empty) + FARMER_SEEDS_KEPT)
            other = seedChest(gm, f, seed, i, aside)
            if other is not None:  # another farming hut's chest
                return ("fetch", other, seed, len(empty) + FARMER_SEEDS_KEPT)
            war = chestWith(gm, f, seed, i)
            if war is not None and war not in aside:
                return ("fetch", war, seed, len(empty) + FARMER_SEEDS_KEPT)
    if store is not None and extra:
        return ("stash", store, keep)
    return None


def seedChest(gm, f, seed, position, aside=()):
    """The nearest of f's farming huts' chests holding seed, or None."""
    have = [c for c in farmChests(gm, f) if c not in aside and stockIn(gm, c).get(seed, 0) > 0]
    return min(have, key=lambda c: dist(gm, c, position)) if have else None


def seedsJob(gm, i, u, f):
    """A farmer with no seeds: fetch some (of the kind f has most of, from a farming hut's chest or a war chest)."""
    stock = chestStock(gm, f)
    for c in farmChests(gm, f):
        for m, a in stockIn(gm, c).items():
            stock[m] = stock.get(m, 0) + a
    aside = setAside(gm, u)
    for k in sorted((k for k in FARM_KINDS if stock.get(seedOf(k), 0) > 0), key=lambda k: -stock[seedOf(k)]):
        c = seedChest(gm, f, seedOf(k), i, aside) or chestWith(gm, f, seedOf(k), i)
        if c is not None and c not in aside:
            return ("fetch", c, seedOf(k), FARMER_START_SEEDS)
    return None


def helpBuild(gm, i, u, f, hut, ctx):
    """The farmer's farming hut is going up: it helps lay the floor, then waits there for the builders."""
    if hutStage(gm, hut) == "floor":
        todo = [t for t in hut["floor"] if not floored(gm, hut, t) and gm.grid[t][0] != 2]
        if todo:
            t = min(todo, key=lambda t: dist(gm, t, i))
            position, there = goNextTo(gm, i, u, t, f, ctx, standOn=True)
            if there and work(hut, ("floor", t), FLOOR_TURNS):
                layFloor(gm, hut, t)
            return position
    if dist(gm, i, hut["center"]) > 4:
        return goNextTo(gm, i, u, hut["center"], f, ctx)[0]
    return i


def farmerTurn(gm, i, u, ctx):
    f = faction(gm, u)
    home = homeBonfire(gm, f, i) if f is not None else None
    if home is None:
        if f is not None and migrating(f) is not None and dist(gm, i, f.migrating) > 3:
            return migrateTurn(gm, i, u, f, ctx)
        return organizers.wander(gm, i)
    hut = farmHutOf(f, u)
    if hut is not None and not hut["done"] and not hut.get("built"):
        return helpBuild(gm, i, u, f, hut, ctx)  # (once it's been finished, it keeps farming while it's repaired)
    if getattr(u, "rest", 0) > 0:
        u.rest -= 1
        return organizers.wander(gm, i)
    if hut is None:  # waiting for a builder to build it a farming hut (it needs seeds for one)
        job = seedsJob(gm, i, u, f) if carriedSeeds(u) == 0 else None
        if job is None:
            if dist(gm, i, home) > BONFIRE_REACH:
                return step(gm, i, u, home, f.walls(), ctx)
            u.rest = rand.randint(4, 10)
            return organizers.wander(gm, i)
    else:
        job = farmJob(gm, i, u, f, hut)
    if job is None:
        u.rest = rand.randint(3, 6)
        return i
    position, there = goNextTo(gm, i, u, job[1], f, ctx)
    if not there:
        tooLong(gm, u, job[1], FARM_GIVE_UP)  # (it can't get there: set aside, it does something else next turn)
        return position
    u.headingFor = None
    action, t = job[0], job[1]
    if action == "weed":
        gm.grid[t] = [0, gm.grid[t][1]]  # pulled up: nothing kept
        gm.change = True
    elif action == "pick":
        plant = gm.grid[t][2]
        stage = plant.pick()  # (it's used up, whatever it gives)
        for materialId, amount in loot.rollPick(plant, stage) if stage else ():
            u.materials[materialId] = u.materials.get(materialId, 0) + amount
        gm.grid[t] = [0, gm.grid[t][1]]
        gm.change = True
    elif action == "plant" and work(u, ("plant", t), PLANT_TURNS):
        seed = seedOf(job[2])
        u.materials[seed] -= 1
        if u.materials[seed] <= 0:
            del u.materials[seed]
        gm.grid[t] = [8, gm.grid[t][1], plants.Plant(job[2], planted=True, faction=f.id)]
        gm.change = True
    elif action == "fetch":
        withdraw(gm, t, u, job[2], min(job[3], fitAmount(u, job[2])))
    elif action == "stash":
        putAway(gm, t, u, job[2])
    return i


# ---------------------------------------------------------------- storage huts

def buildChests(gm, i, b, f, hut, ctx):
    """A storage hut's last stage: a war chest on each of its chest spots (CHEST_TURNS each)."""
    todo = []
    for t in hut["chests"]:
        kind = gm.grid[t][0]
        if kind == 3 or t in hut["skip"]:
            continue
        if kind == 8:  # a plant grew there: pull it up
            gm.grid[t] = [0, gm.grid[t][1]]
            kind = 0
        if kind in (2, 4, 6, 7, 9, CAMP):  # something there now: leave it out
            hut["skip"].add(t)
            continue
        if not any(organizers.passable(gm.grid[n], demise=False) or gm.grid[n][0] in (1, 5) for n in gm.neighbors(t)):
            hut["skip"].add(t)  # chests all round it: nowhere left to stand to build it, so it's left out
            continue
        if t != i:
            todo.append(t)
    if not todo:
        if all(gm.grid[t][0] == 3 or t in hut["skip"] for t in hut["chests"]):
            hut["done"] = True
            finishTask(b)
            return i
        return organizers.wander(gm, i)  # standing on the last spot: step off it
    t = pick(gm, hut, b, todo, i)
    position, there = goNextTo(gm, i, b, t, f, ctx)
    if there and gm.grid[t][0] != 0:  # one of its own goblins standing there: shoo it
        return makeWay(gm, ctx, i, t, f, b)
    if there and wouldTrap(gm, t) is not None:  # it would shut someone (maybe itself) in: let them out first
        return leaveNook(gm, ctx, i, b, t, f)
    if there and work(hut, ("chest", t), CHEST_TURNS):
        gm.grid[t] = [3, gm.grid[t][1], CampChest(f.id, f.look)]
        chests(gm, f).add(t)
        gm.change = True
    return position


def otherWayOut(gm, n, t):
    """Has tile n a way out besides t? Goblins beside it count, since they move (or swap places)."""
    return any(m != t and (organizers.passable(gm.grid[m], demise=False) or gm.grid[m][0] == 5)
               for m in gm.neighbors(n))


def wouldTrap(gm, t):
    """Would filling tile t box in a goblin standing beside it (no way out but t: walls, chests and camp pieces all
    round)? Returns where that goblin stands, or None."""
    for n in gm.neighbors(t):
        if gm.grid[n][0] == 5 and not otherWayOut(gm, n, t):
            return n
    return None


def leaveNook(gm, ctx, i, b, t, f):
    """Builder b at i is about to fill tile t, but that would box somebody in. If it's someone else, b steps away so
    they can get out; if it's b itself (standing in a nook only t leads out of), it goes round to a spot beside t
    that has another way out, and works from there."""
    if wouldTrap(gm, t) != i:
        return organizers.wander(gm, i)
    spots = [n for n in gm.neighbors(t) if n != i and organizers.passable(gm.grid[n], demise=False)
             and otherWayOut(gm, n, t)]
    if not spots:
        return organizers.wander(gm, i)
    return goNextTo(gm, i, b, min(spots, key=lambda n: dist(gm, n, i)), f, ctx, standOn=True)[0]


def storageChests(gm, f):
    """The war chests standing in f's storage huts."""
    mine = chests(gm, f)
    return [t for h in f.huts if h.get("kind") == "storage" for t in h["chests"] if t in mine]


def storageNeeded(gm, f):
    """Should f's builders build a storage hut now? Once it has FIRST_STORAGE_HUTS huts, whenever none of its storage
    chests has room (or it has none)."""
    if finishedHuts(f) < FIRST_STORAGE_HUTS:
        return False
    return not any(len(chestAt(gm, c)) < chestSlots(chestAt(gm, c)) for c in storageChests(gm, f))


def stashChest(gm, f, unit, i, home):
    """Where unit stashes what it carries: the nearest storage chest with room for it, else the nearest chest with
    room by its bonfire, or None."""
    store = [c for c in storageChests(gm, f) if roomIn(gm, c, unit)]
    if not store:
        store = [c for c in chests(gm, f) if dist(gm, c, home) <= CHEST_SPOT[1] + 2 and roomIn(gm, c, unit)]
    return min(store, key=lambda c: dist(gm, c, i)) if store else None


# ---------------------------------------------------------------- food

def carriedFood(unit):
    return sum(unit.materials.get(m, 0) for m in FOOD)


def foodChest(gm, f, position):
    """The nearest of f's war chests or farming huts' chests with food in it, or None."""
    have = [c for c in list(chests(gm, f)) + farmChests(gm, f) if any(isinstance(it, resources.MaterialStack) and it.materialId in FOOD
                                           and it.amount > 0 for it in chestAt(gm, c))]
    return min(have, key=lambda c: dist(gm, c, position)) if have else None


def spawnersOf(gm, f):
    """(position, spawner) for f's spawners."""
    out = []
    for t in camp(gm)["structures"]:
        tile = gm.grid.get(t)
        if tile and tile[0] == CAMP and tile[2].kind == "spawner" and tile[2].faction == f.id:
            out.append((t, tile[2]))
    return out


def feedTask(gm, i, b, f):
    """A spawner of f with less than HUNGRY_AT food that no other builder is feeding, if there's food to bring it."""
    hungry = []
    for t, s in spawnersOf(gm, f):
        feeder = getattr(s, "feeder", None)
        busy = feeder is not None and feeder is not b and feeder.hp > 0 and factionOf(feeder) == f.id \
            and gm.turnCount - getattr(s, "fedAt", 0) <= 3  # (its feeder worked on it lately)
        if s.__dict__.setdefault("food", SPAWNER_START_FOOD) < HUNGRY_AT and not busy:
            hungry.append(t)
    if not hungry or (carriedFood(b) == 0 and foodChest(gm, f, i) is None):
        return None
    t = min(hungry, key=lambda t: dist(gm, t, i))
    gm.grid[t][2].feeder, gm.grid[t][2].fedAt = b, gm.turnCount
    return {"kind": "feed", "at": t}


def feedTurn(gm, i, b, f, task, ctx):
    """Food from a war chest to a hungry spawner: to the chest for it (unless it carries some already), then to the
    spawner, which takes as much as it holds."""
    t = task["at"]
    tile = gm.grid[t]
    if tile[0] != CAMP or tile[2].kind != "spawner" or tile[2].faction != f.id:
        b.task = None  # it's gone
        return i
    s = tile[2]
    s.feeder, s.fedAt = b, gm.turnCount
    room = SPAWNER_FOOD_MAX - s.food
    if room <= 0:
        s.feeder, b.task = None, None
        return i
    if carriedFood(b) == 0:
        chest = foodChest(gm, f, i)
        if chest is None:
            s.feeder, b.task = None, None
            return i
        position, there = goNextTo(gm, i, b, chest, f, ctx)
        if there:
            stock = {it.materialId: it.amount for it in chestAt(gm, chest)
                     if isinstance(it, resources.MaterialStack) and it.materialId in FOOD}
            for m in sorted(stock, key=lambda m: -stock[m]):
                want = min(room - carriedFood(b), fitAmount(b, m))
                if want <= 0:
                    break
                withdraw(gm, chest, b, m, want)
        return position
    position, there = goNextTo(gm, i, b, t, f, ctx)
    if there:
        for m in FOOD:
            give = min(b.materials.get(m, 0), SPAWNER_FOOD_MAX - s.food)
            if give > 0:
                s.food += give
                b.materials[m] -= give
                if b.materials[m] <= 0:
                    del b.materials[m]
        s.feeder, b.task = None, None
        gm.change = True
    return position


# ---------------------------------------------------------------- schisms

PEACE = set()  # frozensets of two faction ids at peace this turn (see updatePeace)


def updatePeace(gm):
    """Factions at peace: a schism's new half and the faction it left, until the new half's first bonfire is lit
    (or SCHISM_PEACE runs out)."""
    PEACE.clear()
    for f in camp(gm)["factions"].values():
        other = getattr(f, "peaceWith", None)
        if other is None:
            continue
        if gm.turnCount > getattr(f, "peaceUntil", 0):
            f.peaceWith = None
            continue
        PEACE.add(frozenset((f.id, other)))


def atPeace(a, b):
    return frozenset((a, b)) in PEACE


def factionUnits(gm, f):
    """(position, unit) for f's goblins on the map."""
    out = []
    for p in gm.EnemyPositions:
        tile = gm.grid.get(p)
        if tile and tile[0] == 5 and len(tile) > 2 and factionOf(tile[2]) == f.id:
            out.append((p, tile[2]))
    return out


def schism(gm, f, units):
    """Half of f breaks away: half its squads (whole squads), half its builders and half its farmers become a new
    faction in new colors. If there's somewhere far enough from every camp (farAway), they march there to set up a
    camp, at peace with f until its first bonfire is lit; huts and chests all stay with f. If the floor is too
    crowded for that, they rise up where they are instead (takeOver): at war with f at once, they take half its huts."""
    squads = [s for s in f.squads if any(m.hp > 0 for m in s.members)]
    rand.shuffle(squads)
    leaving = squads[:len(squads) // 2]
    builders = [u for _, u in units if u.name == "Goblin Builder"]
    farmers = [u for _, u in units if u.name == "Goblin Farmer"]
    rand.shuffle(builders)
    rand.shuffle(farmers)
    goers = [m for s in leaving for m in s.members if m.hp > 0] + builders[:max(1, len(builders) // 2)] + \
        farmers[:max(1, len(farmers) // 2)]
    where = {id(u): p for p, u in units}
    start = next((where[id(u)] for u in goers if id(u) in where), None)
    if start is None:
        return False
    new = newFaction(gm, pickLook(gm))
    goal = farAway(gm, start, farthest=isNeutral(new))
    if goal is not None:
        new.peaceWith, new.peaceUntil, new.migrating = f.id, gm.turnCount + SCHISM_PEACE, goal
    for s in leaving:
        f.squads.remove(s)
        new.squads.append(s)
        s.raid, s.hauling, s.goal, s.target, s.mission = None, False, None, None, None
    for u in goers:
        setFaction(u, new)
        if hasattr(u, "task"):
            u.task = None
    for p in farms(f):
        if p.get("farmer") in goers:
            p["farmer"] = None
    if goal is None:
        takeOver(gm, f, new)
    else:
        packUp(gm, f, goers)
    gm.change = True
    return True


def takeOver(gm, f, new):
    """A schism with nowhere to go: new takes half of f's huts where they stand, the half furthest from f's first
    bonfire, with their spawners, chests and farming huts' chests, their walls repainted in its colors. Any of f's
    bonfires and war chests nearer the huts it takes than the ones f keeps go with it (f always keeps its first
    bonfire). There's no peace between them."""
    if not f.huts:
        return
    heart = f.first if f.first in f.bonfires else (f.bonfires[0] if f.bonfires else f.huts[0]["center"])
    huts = sorted(f.huts, key=lambda h: -dist(gm, h["center"], heart))
    taken = huts[:max(1, len(huts) // 2)]
    for h in taken:
        giveHut(gm, f, new, h)
    near = lambda t, hs: min((dist(gm, t, h["center"]) for h in hs), default=1e9)
    for b in list(f.bonfires):
        if b != heart and near(b, taken) < near(b, f.huts):
            f.bonfires.remove(b)
            new.bonfires.append(b)
            if gm.grid[b][0] == CAMP:
                gm.grid[b][2].faction = new.id
    new.first = new.bonfires[0] if new.bonfires else None
    for c in list(chests(gm, f)):  # the war chests by its bonfires
        if near(c, taken) < near(c, f.huts):
            box = chestAt(gm, c)
            box.faction, box.look = new.id, new.look
            chests(gm, f).discard(c)
            chests(gm, new).add(c)


def giveHut(gm, f, new, h):
    """Hut h goes from f to new: its spawner, its chests and its walls, repainted in new's colors."""
    f.huts.remove(h)
    new.huts.append(h)
    h["builder"] = None
    if h.get("kind") == "farm" and factionOf(h.get("farmer")) != new.id:
        h["farmer"] = None
    for t in h["walls"]:
        if gm.grid[t][0] == 2 and getattr(gm.grid[t][2], "paint", None):
            paintHutWall(gm, h, t, new.look)
    c = h["center"]
    if gm.grid[c][0] == CAMP:
        gm.grid[c][2].faction = new.id  # its spawner
    for t in h.get("chests", []) + ([c] if h.get("kind") == "farm" else []):
        box = chestAt(gm, t)
        if isinstance(box, CampChest):
            box.faction, box.look = new.id, new.look
            chests(gm, f).discard(t)
            if h.get("kind") != "farm":
                chests(gm, new).add(t)
    gm.change = True


# ---------------------------------------------------------------- seizing a spawner

def spawnerHut(gm, g, center):
    """g's hut at center, if it's still g's and its spawner is standing."""
    if g is None:
        return None
    tile = gm.grid.get(center)
    if not tile or tile[0] != CAMP or tile[2].kind != "spawner":
        return None
    return next((h for h in g.huts if h["center"] == center), None)


def seizeTarget(gm, f, units):
    """The nearest spawner of any other faction to f's group (its chief, or any of it): (faction, hut), or None."""
    at = next((p for p, u in units if u.name == "Goblin Chieftan"), units[0][0])
    best = None
    for g in camp(gm)["factions"].values():
        if g is f:
            continue
        for h in g.huts:
            if spawnerHut(gm, g, h["center"]) is None:
                continue
            d = dist(gm, at, h["center"])
            if best is None or d < best[0]:
                best = (d, g, h)
    return best[1:] if best else None


def dyingOut(gm, f):
    """Has f died out: no goblins left, and no spawner with the food to make one? (Its camp, if it has one, turns
    neutral: abandoned.)"""
    if factionUnits(gm, f):
        return False
    return (f.huts or f.bonfires or chests(gm, f)) and \
        not any(s.__dict__.get("food", 0) >= FOOD_PER_SPAWN for _, s in spawnersOf(gm, f))


def abandon(gm, f):
    """f has died out: its camp turns neutral, its hut walls and chests repainted in NEUTRAL_LOOK."""
    f.abandoned, f.seizing, f.migrating, f.peaceWith = True, None, None, None
    f.look = NEUTRAL_LOOK
    for h in f.huts:
        for t in h["walls"]:
            if gm.grid[t][0] == 2 and getattr(gm.grid[t][2], "paint", None):
                paintHutWall(gm, h, t, NEUTRAL_LOOK)
    for c in list(chests(gm, f)) + farmChests(gm, f) + [c for h in f.huts for c in h.get("chests", [])]:
        box = chestAt(gm, c)
        if isinstance(box, CampChest):
            box.look = NEUTRAL_LOOK
    gm.change = True


def claimZone(gm, f):
    """Where a goblin standing claims an abandoned camp: inside any of its huts, within 3 of a bonfire, or beside
    one of its war chests."""
    zone = {t for h in f.huts for t in h["inside"] if t is not None}
    for b in f.bonfires:
        zone |= {t for dy in range(-3, 4) for dx in range(-3, 4)
                 if (t := offsetTile(gm, b, dx, dy)) is not None and dist(gm, t, b) <= 3}
    for c in chests(gm, f):
        zone |= set(gm.neighbors(c))
    return zone


def claimStep(gm, f):
    """An abandoned camp (its faction died out) stands neutral until a goblin walks into it (claimZone): a faction's
    goblin claims all of it for its faction; a wild goblin claims it for a new faction in new colors, which it
    founds. Its huts, spawners (hungry: they spawn once fed), bonfires and chests all change hands."""
    zone = claimZone(gm, f)
    if not zone:
        camp(gm)["factions"].pop(f.id, None)  # nothing left of it
        return
    for t in zone:
        tile = gm.grid.get(t)
        if not tile or tile[0] != 5 or len(tile) < 3:
            continue
        u = tile[2]
        owner = faction(gm, u)
        if owner is not None and not getattr(owner, "abandoned", False):
            claimCamp(gm, f, owner)
            return
        if owner is None and u.name in GOBLIN_NAMES and u.hp > 0:
            new = newFaction(gm, pickLook(gm))
            setFaction(u, new)
            u.rally = u.foe = None
            if u.name not in WORKERS:
                joinSquad(gm, u, new)
            claimCamp(gm, f, new)
            return


def claimCamp(gm, f, new):
    """All of abandoned f's camp goes to new."""
    for h in list(f.huts):
        giveHut(gm, f, new, h)
    for b in list(f.bonfires):
        f.bonfires.remove(b)
        new.bonfires.append(b)
        if gm.grid[b][0] == CAMP:
            gm.grid[b][2].faction = new.id
    if new.first is None or new.first not in new.bonfires:
        new.first = new.bonfires[0] if new.bonfires else None
    for c in list(chests(gm, f)):
        box = chestAt(gm, c)
        if isinstance(box, CampChest):
            box.faction, box.look = new.id, new.look
            chests(gm, new).add(c)
        chests(gm, f).discard(c)
    if migrating(new) is not None and new.bonfires:  # (a group on its way to a new camp has one now)
        new.migrating = new.peaceWith = None
    camp(gm)["factions"].pop(f.id, None)
    gm.change = True


def seizeStep(gm, f):
    """A group that has lost all its builders before it lit a bonfire (so it can't start a camp) goes to take a
    spawner from the nearest other faction instead: peace or not, it marches on it, fights whatever it meets near
    it, and once one of its goblins is inside the hut with none of the owners left in it, the hut is its. Its
    goblins put the food they carry in the spawner, which makes it a builder next (once it has the food), and the builder
    lights the new camp's bonfire beside the hut. If there's no spawner to take, it carries on where it was going."""
    units = factionUnits(gm, f)
    if not units:
        f.seizing = None
        return
    seizing = getattr(f, "seizing", None)
    if seizing is not None and (f.huts or f.bonfires):  # it got a camp some other way (claimed an abandoned one)
        f.seizing = f.migrating = None
        return
    if seizing is None:
        if f.bonfires or f.huts or any(u.name == "Goblin Builder" for _, u in units):
            return
        hut = None
    else:
        owner = camp(gm)["factions"].get(seizing[0])
        hut = spawnerHut(gm, owner, seizing[1])
    if hut is None:  # (still) needs a spawner to go for
        target = seizeTarget(gm, f, units)
        if target is None:
            if seizing is not None:
                f.seizing, f.migrating = None, f.__dict__.get("settleAt")
            return
        owner, hut = target
        if seizing is None:
            f.settleAt = f.migrating  # (where it was going, in case there's nothing left to take)
        f.seizing, f.migrating, f.peaceWith = (owner.id, hut["center"]), hut["center"], None
    inHut = set(hut["inside"])
    ours = [u for p, u in units if p in inHut]
    theirs = [p for p, u in factionUnits(gm, owner) if p in hut["floor"]]
    if not ours or theirs:
        return
    giveHut(gm, owner, f, hut)
    f.seizing = f.migrating = f.peaceWith = None
    s = gm.grid[hut["center"]][2]
    s.__dict__.setdefault("food", 0)
    for _, u in units:
        if not hasattr(u, "materials"):
            continue
        for m in FOOD:
            give = min(u.materials.get(m, 0), SPAWNER_FOOD_MAX - s.food)
            if give > 0:
                s.food += give
                u.materials[m] -= give
                if u.materials[m] <= 0:
                    del u.materials[m]
    s.timer = min(s.timer, 3)


def packUp(gm, f, goers):
    """Before a schism's half leaves, it takes half of f's stored food (up to SCHISM_FOOD), shared out among its
    pockets, and each of its farmers tops up its seeds of one kind (up to FARMER_START_SEEDS) from f's war chests."""
    stock = chestStock(gm, f)
    left = min(SCHISM_FOOD, sum(stock.get(m, 0) for m in FOOD) // 2)
    for c in list(chests(gm, f)):
        for it in list(chestAt(gm, c)):
            if left <= 0:
                break
            if not isinstance(it, resources.MaterialStack) or it.materialId not in FOOD:
                continue
            for u in goers:
                n = min(left, it.amount, fitAmount(u, it.materialId))
                if n > 0:
                    withdraw(gm, c, u, it.materialId, n)
                    left -= n
                if left <= 0 or it.amount <= 0:
                    break
    for u in goers:
        if u.name != "Goblin Farmer":
            continue
        stock = chestStock(gm, f)
        seeds = [seedOf(k) for k in FARM_KINDS]
        mine = max(seeds, key=lambda s: u.materials.get(s, 0) * 1000 + stock.get(s, 0))  # what it has most of
        want = FARMER_START_SEEDS - u.materials.get(mine, 0)
        for c in list(chests(gm, f)):
            if want <= 0:
                break
            have = sum(it.amount for it in chestAt(gm, c) if isinstance(it, resources.MaterialStack) and it.materialId == mine)
            if have:
                n = min(want, have, fitAmount(u, mine))
                withdraw(gm, c, u, mine, n)
                want -= n


def campsAround(gm, ignore=None):
    """Where every faction (but ignore) is: its bonfires, its huts, its war chests and, for a group on its way to a
    new camp, where it's going."""
    factions = [g for g in camp(gm)["factions"].values() if g is not ignore]
    return [b for g in factions for b in g.bonfires] + [h["center"] for g in factions for h in g.huts] + \
        [c for g in factions for c in chests(gm, g)] + [migrating(g) for g in factions if migrating(g) is not None]


def othersAround(gm):
    """Everything else a new camp keeps SCHISM_CLEAR from: you, every enemy outside the factions (monsters,
    Organizers, wild goblins) and every crafting station."""
    out = [gm.playerPositionFlat]
    for p in gm.EnemyPositions:
        tile = gm.grid.get(p)
        if tile and tile[0] == 5 and len(tile) > 2 and factionOf(tile[2]) is None:
            out.append(p)
    return out + [t for t, tile in gm.grid.items() if tile[0] == 7]


def distanceFromCamps(gm, spot, camps):
    """How far spot is from the nearest of camps (positions); infinitely far when there are none."""
    return min((dist(gm, spot, campSpot) for campSpot in camps), default=math.inf)


def farAway(gm, start, ignore=None, farthest=False):
    """Where a schism's leaving half goes to set up camp: an open floor tile anywhere on the floor (goblins dig their
    way there) at least SCHISM_DISTANCE from every faction's bonfires, huts and war chests and every other leaving
    group's destination (campsAround) and SCHISM_CLEAR from you, any other enemy and any station (othersAround).
    It doesn't need room for a hut yet: once the bonfire's lit, builders dig the camp out around it. The roomiest
    of those, or None only if there's no such spot on the whole floor. With farthest (a neutral faction), the one
    of FAR_SPOTS_WEIGHED such spots that's farthest from every other camp instead."""
    fires, others = campsAround(gm, ignore), othersAround(gm)
    spots = [t for t, tile in gm.grid.items() if tile[0] == 0]
    rand.shuffle(spots)
    found = []
    for t in spots:
        if any(dist(gm, t, b) < SCHISM_DISTANCE for b in fires) or any(dist(gm, t, p) < SCHISM_CLEAR for p in others):
            continue
        found.append(t)
        if len(found) >= (FAR_SPOTS_WEIGHED if farthest else 60):
            break
    roomy = lambda t: sum(1 for dy in range(-4, 5) for dx in range(-4, 5)
                          if (n := offsetTile(gm, t, dx, dy)) is not None and gm.grid[n][0] == 0)
    if not found:
        return None
    if farthest:
        return max(found, key=lambda spot: (distanceFromCamps(gm, spot, fires), roomy(spot)))
    return max(found, key=roomy)


def migrating(f):
    return getattr(f, "migrating", None)


MIGRATE_RECHECK = 25        # a leaving group checks this often that nobody has camped near where it's going


def migrateTurn(gm, i, unit, f, ctx):
    """A step toward where its faction is going to set up camp (a floor-wide path map, like a bonfire's). Now and
    then it checks nobody has settled within SCHISM_DISTANCE of it meanwhile, and if so, picks somewhere else."""
    if getattr(f, "seizing", None) is None and \
            gm.turnCount - f.__dict__.setdefault("migrateChecked", gm.turnCount) >= MIGRATE_RECHECK:
        f.migrateChecked = gm.turnCount
        if any(dist(gm, f.migrating, t) < SCHISM_DISTANCE for t in campsAround(gm, ignore=f)):
            goal = farAway(gm, i, ignore=f, farthest=isNeutral(f))
            if goal is not None:
                f.migrating = goal
    return step(gm, i, unit, f.migrating, f.walls(), ctx, bonfireField(gm, f.migrating))


# ---------------------------------------------------------------- wild goblins and everyone else

def otherTurn(gm, i, enemy, ctx):
    """A turn for an enemy outside every faction. Returns its new position, or None for its usual turn (chasing you).
    It fights back against whatever hit it (enemy.foe). Wild goblins also attack faction goblins they see, and
    march to a bonfire when one draws them in (enemy.rally)."""
    foe = getattr(enemy, "foe", None)
    wild = enemy.name in GOBLIN_NAMES
    if wild and foe is None and camp(gm)["factions"] and i not in gm.smoke:
        seen = [(dist(gm, i, p), e, p) for p, e in near(gm, ctx, i, WILD_SIGHT)
                if factionOf(e) is not None and e.hp > 0 and p not in gm.smoke]
        seen = [s for s in sorted(seen, key=lambda s: s[0]) if gm.lineOfSight(i, s[2])]
        if seen:
            foe = enemy.foe = seen[0][1]
    if foe is not None:
        at = find(gm, ctx, foe)
        if at is None or foe.hp <= 0 or dist(gm, i, at) > CHASE_LIMIT:
            enemy.foe = None
        elif at in gm.neighbors(i):
            attack(gm, i, enemy, foe, at)
            return i
        else:
            position = step(gm, i, enemy, at, set(), ctx)
            moved(ctx, enemy, position)
            return position
    rally = getattr(enemy, "rally", None)
    if rally is not None:
        if gm.playerPositionFlat in gm.neighbors(i) or gm.grid[rally][0] != CAMP or dist(gm, i, rally) <= 3:
            enemy.rally = None
            return None
        position = step(gm, i, enemy, rally, set(), ctx, bonfireField(gm, rally))
        moved(ctx, enemy, position)
        return position
    return None


# ---------------------------------------------------------------- the camp each turn

def stepCamp(gm):
    """Spawners spawn, bonfires draw wild goblins in, wanderers arrive, and big factions split."""
    state = camp(gm)
    if not state["factions"]:
        return
    calmDown(gm)
    for f in state["factions"].values():  # pieces that fell off the list (saves from before you couldn't stand on them)
        for t in f.bonfires + [h["center"] for h in f.huts]:
            tile = gm.grid.get(t)
            if tile and tile[0] == CAMP:
                state["structures"].add(t)
    for t in list(state["structures"]):
        tile = gm.grid.get(t)
        if tile and tile[0] == 1 and t == gm.playerPositionFlat and gm.currentLocation[0] == CAMP:
            continue  # you're standing on it (you got put there somehow): it's still there under you
        if not tile or tile[0] != CAMP:
            state["structures"].discard(t)
            continue
        s = tile[2]
        if s.kind == "spawner":
            stepSpawner(gm, t, s)
    bonfires = [b for f in state["factions"].values() for b in f.bonfires]
    if bonfires and gm.turnCount % RALLY_TURNS == 0:
        for p in list(gm.EnemyPositions):
            tile = gm.grid.get(p)
            if not tile or tile[0] != 5 or len(tile) < 3:
                continue
            e = tile[2]
            if e.name in GOBLIN_NAMES and factionOf(e) is None and getattr(e, "rally", None) is None \
                    and getattr(e, "foe", None) is None and e.lastPlayerPosition is None:
                nearest = min(bonfires, key=lambda b: dist(gm, b, p))
                if dist(gm, nearest, p) <= RALLY_REACH and rand.random() < RALLY_CHANCE:
                    e.rally = nearest
    if bonfires and gm.turnCount % WANDERER_TURNS == 0:
        wanderIn(gm, bonfires)
    for f in list(state["factions"].values()):
        if getattr(f, "abandoned", False):
            claimStep(gm, f)
        elif dyingOut(gm, f):
            abandon(gm, f)
    for f in list(state["factions"].values()):
        if not f.bonfires and not getattr(f, "abandoned", False):
            seizeStep(gm, f)
    for f in list(state["factions"].values()):
        if migrating(f) is not None or not f.bonfires:
            continue
        units = factionUnits(gm, f)
        f.food = foodCount(gm, f)
        if not f.__dict__.setdefault("canSchism", True):
            continue
        if len(units) < SPLIT_UNITS or sum(u.name == "Goblin Builder" for _, u in units) < SPLIT_BUILDERS \
                or sum(u.name == "Goblin Farmer" for _, u in units) < SPLIT_FARMERS:
            continue  # (its chance stays where it is until it meets them again)
        chance = f.__dict__.setdefault("schismChance", SCHISM_CHANCE)
        if rand.random() < chance and schism(gm, f, units):
            f.schismChance = SCHISM_CHANCE
        else:
            f.schismChance = chance + schismStep(gm, f, units)


def foodCount(gm, f):
    """All the food f has: in its war chests and farming huts' chests, and stocked in its spawners."""
    chestsHave = list(chests(gm, f)) + farmChests(gm, f)
    stored = sum(it.amount for c in chestsHave for it in chestAt(gm, c)
                 if isinstance(it, resources.MaterialStack) and it.materialId in FOOD)
    return stored + sum(s.__dict__.get("food", 0) for _, s in spawnersOf(gm, f))


def schismStep(gm, f, units):
    """How much f's chance of a schism grows this turn: SCHISM_CHANCE_STEP, up to (1 + SCHISM_HUNGER) times that
    while its food (f.food) is short of what its spawners and goblins need."""
    need = FOOD_NEED_SPAWNER * len(spawnersOf(gm, f)) + FOOD_NEED_UNIT * len(units)
    short = max(0.0, 1 - f.food / need) if need else 0.0
    return SCHISM_CHANCE_STEP * (1 + SCHISM_HUNGER * short)


def stepSpawner(gm, t, s):
    s.timer -= 1
    if s.timer > 0:
        return
    f = camp(gm)["factions"].get(s.faction)
    hut = next((h for h in f.huts if h["center"] == s.hut), None) if f else None
    inside = hut["inside"] if hut else [n for n in gm.eightAround(t)]
    free = [x for x in inside if x is not None and gm.grid[x][0] == 0]
    needBuilder = f is not None and not f.bonfires and not any(u.name == "Goblin Builder" for u in builders(gm)
                                                               if factionOf(u) == f.id)
    if not free or f is None or getattr(f, "abandoned", False) \
            or s.__dict__.setdefault("food", SPAWNER_START_FOOD) < FOOD_PER_SPAWN:
        s.timer = 1  # full, or out of food (it never spawns without food): try again next turn
        return
    s.timer = rand.randint(*SPAWN_TURNS)
    s.food -= FOOD_PER_SPAWN
    roll, kind = rand.random() * 100, SPAWN_ODDS[-1][0]
    for name, chance in SPAWN_ODDS:
        if roll < chance:
            kind = name
            break
        roll -= chance
    if needBuilder:
        kind = "Goblin Builder"  # a seized hut with no camp yet: a builder to light its bonfire
    elif kind == "Goblin Farmer" and farmerCount(gm, f) >= BASE_FARMERS + finishedHuts(f) // HUTS_PER_FARMER:
        kind = "Goblin"  # enough farmers for a camp this size
    if hut is not None:
        hut["spawned"] = hut.get("spawned", 0) + 1  # (kept on the hut, so a rebuilt spawner doesn't start over)
    spawn(gm, rand.choice(free), kind, f)


def spawn(gm, t, kind, f):
    unit = UNIT_CLASSES[kind]()
    if f is not None:
        setFaction(unit, f)
    gm.grid[t] = [5, gm.grid[t][1], unit]
    gm.EnemyPositions.add(t)
    gm.change = True
    if f is not None and kind not in WORKERS:
        joinSquad(gm, unit, f)
    return unit


def outOfSightSpots(gm, minimum):
    return [t for t, tile in gm.grid.items() if tile[0] == 0 and tile[1] != 1 and dist(gm, t, gm.playerPositionFlat) >= minimum]


def wanderIn(gm, bonfires):
    spots = outOfSightSpots(gm, 15)
    if spots:
        t = rand.choice(spots)
        goblin = spawn(gm, t, "Goblin", None)
        goblin.rally = min(bonfires, key=lambda b: dist(gm, b, t))


def spawnWarband(gm):
    """The event's war band (WARBAND): free tiles together for all of it, at least 10 from you and out of sight.
    True if it arrived. The chief and goblins make a squad that guards the camp (it stays by the bonfire) until a
    third goblin joins it from a spawner and it marches out on patrol."""
    size = len(WARBAND)
    neutral = rand.random() < NEUTRAL_CHANCE
    spots = outOfSightSpots(gm, 10)
    rand.shuffle(spots)
    if neutral:  # it arrives as far from the other factions as it can (with none yet, anywhere)
        otherCamps = campsAround(gm)
        spots.sort(key=lambda spot: -distanceFromCamps(gm, spot, otherCamps))
    for start in spots[:200]:
        group, frontier = [start], [start]
        while frontier and len(group) < size:
            nxt = []
            for p in frontier:
                for n in gm.neighbors(p):
                    if n not in group and gm.grid[n][0] == 0 and gm.grid[n][1] != 1 and len(group) < size:
                        group.append(n)
                        nxt.append(n)
            frontier = nxt
        if len(group) < size:
            continue
        f = newFaction(gm, rand.choice(FIRST_LOOKS), neutral=neutral)
        squad = Squad(marching=False)
        f.squads.append(squad)
        for t, kind in zip(group, WARBAND):
            unit = UNIT_CLASSES[kind]()
            setFaction(unit, f)
            gm.grid[t] = [5, gm.grid[t][1], unit]
            gm.EnemyPositions.add(t)
            if kind not in WORKERS:
                squad.members.append(unit)
                unit.squad = squad
            if kind == "Goblin Farmer":
                unit.materials[seedOf(startingCrop(gm, start))] = FARMER_START_SEEDS
        gm.change = True
        return True
    return False


def startingCrop(gm, start):
    """A random plant that grows on the floor most common round start (where the camp will be)."""
    floors = {}
    for dy in range(-FARM_DISTANCE[1], FARM_DISTANCE[1] + 1):
        for dx in range(-FARM_DISTANCE[1], FARM_DISTANCE[1] + 1):
            t = offsetTile(gm, start, dx, dy)
            if t is not None and gm.grid[t][0] == 0:
                floor = plants.floorOf(t, gm.rooms)
                floors[floor] = floors.get(floor, 0) + 1
    for floor in sorted(floors, key=lambda k: -floors[k]):
        kinds = [k for k in FARM_KINDS if floor in plants.PLANTS[k]["floors"]]
        if kinds:
            return rand.choice(kinds)
    return rand.choice(FARM_KINDS)


def newFaction(gm, look, neutral=None):
    """A new faction on this floor. neutral: whether it's neutral to you; None rolls NEUTRAL_CHANCE."""
    state = camp(gm)
    f = Faction(state["next"], look)
    f.neutral = rand.random() < NEUTRAL_CHANCE if neutral is None else neutral
    f.canSchism = rand.random() >= NO_SCHISM_CHANCE  # (a few factions never split)
    f.schismChance, f.food = SCHISM_CHANCE, 0
    state["next"] += 1
    state["factions"][f.id] = f
    return f


# ---------------------------------------------------------------- splits

def livingLooks(gm):
    """How many living factions on this floor use each look."""
    state, counts = camp(gm), {}
    alive = {factionOf(gm.grid[p][2]) for p in gm.EnemyPositions if gm.grid[p][0] == 5 and len(gm.grid[p]) > 2}
    alive |= {gm.grid[t][2].faction for t in state["structures"] if gm.grid[t][0] == CAMP}
    for f in state["factions"].values():
        if f.id in alive:
            counts[f.look] = counts.get(f.look, 0) + 1
    return counts


def pickLook(gm):
    counts = livingLooks(gm)
    unused = [look for look in LOOKS if look not in counts]
    return rand.choice(unused) if unused else min(LOOKS, key=lambda look: counts[look])


# ---------------------------------------------------------------- you and the camp

def crack(gm, piece, damage):
    """A spawner or warcamp chest took damage: it cracks like a wall (wall.Wall.takeDamage), more of its picture
    chipped the bigger the share of its HP the hit took (renderer.crackedPicture draws them)."""
    maxHp = getattr(piece, "maxHp", None) or CHEST_HP
    ts = gm.tileSize
    share = int(min(damage, max(piece.hp, 0) + damage) / maxHp * ts * ts)
    points = piece.__dict__.setdefault("brokenPoints", set())
    points |= wall.getRandomPoints((1, ts - 1), (1, ts - 1), share)


def hitStructure(gm, t):
    """You hit a spawner (it takes your wall damage, and cracks like a wall) or a bonfire (BONFIRE_HITS hits put it
    out)."""
    s = gm.grid[t][2]
    damage = gm.player.getWallDamage() if s.kind == "spawner" else 1
    s.hp -= damage
    gm.change = True
    if s.kind == "spawner":
        crack(gm, s, damage)
    if s.hp > 0:
        return
    if s.kind == "spawner":
        provoke(gm, camp(gm)["factions"].get(s.faction), t)
        breakSpawner(gm, t)
        return
    gm.grid[t] = [0, gm.grid[t][1]]
    camp(gm)["structures"].discard(t)
    f = camp(gm)["factions"].get(s.faction)
    if f and t in f.bonfires:
        f.bonfires.remove(t)


def breakSpawner(gm, t, unit=None):
    """A spawner is smashed: its drops go to you, or to the goblin that broke it (what it can't carry is left on
    the floor). Its faction's builders build it back (damaged)."""
    s = gm.grid[t][2]
    gm.grid[t] = [0, gm.grid[t][1]]
    camp(gm)["structures"].discard(t)
    gm.change = True
    if unit is None:
        gm.collectDrops(SPAWNER_DROPS, s.name, t)
        return
    left, gold = take(unit, [resources.MaterialStack(m, n) for m, n in SPAWNER_DROPS])
    if left or gold:
        gm.placeItems(t, left, gold)


# ---------------------------------------------------------------- neutral factions and you

def isNeutral(f):
    """Is f a neutral faction (see "Neutral factions")? Factions from saves made before there were any aren't."""
    return f is not None and getattr(f, "neutral", False)


def leavesPlayerAlone(gm, unit):
    """Does this goblin leave you alone? Yes if its faction is neutral and you haven't provoked it lately."""
    f = faction(gm, unit)
    return isNeutral(f) and getattr(f, "grudge", 0) <= 0


def huntsPlayer(gm, unit):
    """Will this goblin fight you? Not in peaceful mode, and not while its faction leaves you alone."""
    return not gm.peaceful and not leavesPlayerAlone(gm, unit)


def nearCamp(gm, f, position):
    """Is position within GUARD_REACH of one of f's bonfires or huts (what a neutral faction defends)?"""
    campSpots = f.bonfires + [hut["center"] for hut in f.huts]
    return any(dist(gm, position, campSpot) <= GUARD_REACH for campSpot in campSpots)


def provoke(gm, f, where):
    """You did something to a neutral faction (hurt one of its goblins, broke one of its hut walls or spawners, took
    from one of its chests): it's hostile to you for GRUDGE_TURNS turns from now."""
    if not isNeutral(f):
        return
    if getattr(f, "grudge", 0) <= 0:
        gm.addPopup("The goblins turn on you!", where)
    f.grudge = GRUDGE_TURNS


def calmDown(gm):
    """A turn passes: each neutral faction's grudge against you wears off a little. Once it's gone, its goblins
    stop chasing you."""
    for f in camp(gm)["factions"].values():
        if not isNeutral(f) or getattr(f, "grudge", 0) <= 0:
            continue
        f.grudge -= 1
        if f.grudge == 0:
            for squad in f.squads:
                if squad.target == "player":
                    squad.target = None
            gm.addPopup("The goblins calm down", gm.playerPositionFlat)


def playerHurt(gm, unit, position):
    """You damaged unit: if it belongs to a neutral faction, the faction turns on you."""
    provoke(gm, faction(gm, unit), position)


def playerBrokeWall(gm, position):
    """You broke the wall at position: if it's one of a neutral faction's hut walls, the faction turns on you."""
    for f in camp(gm)["factions"].values():
        if position in f.walls():
            provoke(gm, f, position)


def playerTookFrom(gm, chest, position):
    """You took something out of chest: if it's a neutral faction's (a war chest or a farming hut's), the faction
    turns on you."""
    if isinstance(chest, CampChest):
        provoke(gm, camp(gm)["factions"].get(chest.faction), position)


def attitudeLabel(gm, unit):
    """How a goblin of a neutral faction feels about you, for its name when you look at it: "neutral", or "hostile"
    while its faction holds a grudge. None for every other enemy."""
    f = faction(gm, unit) if factionOf(unit) is not None else None
    if not isNeutral(f):
        return None
    return "hostile" if getattr(f, "grudge", 0) > 0 else "neutral"


def bonfires(gm):
    """Every bonfire on this floor (they give off light)."""
    state = camp(gm)
    return [t for t in state["structures"] if gm.grid[t][0] == CAMP and gm.grid[t][2].kind == "bonfire"]
