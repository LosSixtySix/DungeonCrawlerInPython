import math
import random as rand

import enemies
import loot
import organizers
import plants
import resources
import wall

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
  Goblin Farmer   grows Game of Life still lifes of plants near its bonfires (see "the farmer" below), picks what
                  sprouts round them and keeps them alive, with seeds from the war chests; the rest of its harvest
                  goes back in them.
  Spawner         every SPAWN_TURNS makes a Goblin, Goblin Chief, Goblin Builder or Goblin Farmer (SPAWN_ODDS) on a free tile
                  inside its hut. It waits while the hut is full.
  Bonfire         lights the camp (BONFIRE_LIGHT_RADIUS, through the firelight system) and draws wild goblins in
                  to fight the faction.
  Squads          3 Goblins and a Chief. New goblins wait at the bonfire until they make a squad; a squad short of
                  members takes them first. Squads hunt anything that isn't their faction (you, wild goblins, other
                  factions, any other enemy). With nothing to fight they go on gathering missions: the chief leads
                  them to a random spot anywhere on the floor (at least MISSION_MIN from home) and back, and they
                  gather whatever they pass, there and back. Back home they stash what they brought.
  Schisms         a faction with SPLIT_UNITS goblins (and SPLIT_BUILDERS builders) splits: half its squads,
                  builders and farmers become a new faction in new colors and march off to set up a camp at least
                  SCHISM_DISTANCE from every bonfire. Huts, chests and plots stay. The two are at peace until the
                  new camp's first bonfire is lit (SCHISM_PEACE turns at most), then at war. A faction has no
                  schism within SCHISM_COOLDOWN turns of its last one, or of being made.

Hauling: marching squads with nothing to fight empty floor chests and item piles near them (items, materials and
gold), mine ore veins and Gold Walls near their camp, keeping everything they dig out (and what they take from
enemies they kill), and pick plants near their camp (not the faction's farm plots). Every goblin carries
CARRY_SLOTS slots, stacked like your pouch but smaller: each material takes a slot per GOBLIN_STACK of it,
picked-up gold one slot, each item one. Once the squad is HAUL_AT full it heads home, still stopping for anything within HAUL_DETOUR
of it on the way until it's full, and puts everything in a war chest: a storage hut's first, else one by its
bonfire (it builds one there if needed). Then it heads out again. Items a goblin carries drop where it dies. Squads
at war raid the other faction's chests: they smash one open, take what fits and haul it home.

Storage huts: once a faction has FIRST_STORAGE_HUTS huts, builders build a storage hut (a bigger hut lined with
war chests, STORAGE_CHESTS). Whenever every storage chest is full, all its builders work on the next one.

No two units ever share a tile: every move, spawn and build checks the tile is free.
The camp's state for each floor lives in gameManager.camps[floor] (saved with the game); the pieces on the map are
grid tiles of type CAMP holding a Structure.
"""

CAMP = 10                   # grid tile type for camp structures (spawners and bonfires)

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
HOME_REACH = 30             # a builder further than this from all its faction's bonfires lights one where it is
HUT_DISTANCE = (4, 12)
NEW_BONFIRE_DISTANCE = (13, 18)

SQUAD_GOBLINS = 3           # plus a chief
SIGHT = 6                   # how far a squad member spots a target
CHASE_LIMIT = 15            # a squad drops a target this far from its leader
PATROL_RADIUS = 15
MISSION_MIN = 25            # a gathering mission goes at least this far (walking) from home...
MISSION_TURNS = 400         # ...and a leg of it (there, or back) that takes longer than this is cut short
FOLLOW_DISTANCE = 2

TOGETHER_HUTS = 2           # until a faction has this many finished huts, all its builders work on the same hut
# who the event brings: a chief and 2 goblins (one squad, guarding the camp) and 3 builders
WARBAND = ["Goblin Chieftan", "Goblin", "Goblin", "Goblin Builder", "Goblin Builder", "Goblin Builder"]

CARRY_SLOTS = 15            # what a goblin can carry (see "Hauling" above)
GOBLIN_STACK = 10           # how much of one material fits in one of its slots (a goblin's pouch is small)
HAUL_AT = 0.7               # a squad this full heads home to stash what it carries...
HAUL_DETOUR = 4             # ...stopping for things this close to it on the way, until it's full
MINE_REACH = 6              # squad members mine ore veins and Gold Walls this close to their leader...
MINE_RANGE = PATROL_RADIUS + 5  # ...within this far of their bonfire
CHEST_TURNS = 3             # turns to build a warcamp chest
CAMP_CHEST_SLOTS = 20       # a warcamp chest's room: each material takes one slot however much of it, each item one
                            # (20 rows is what the Items Here window fits on a 768-pixel-tall screen)
CHEST_HP = 12               # hits (of a goblin's damage) to smash one open
CHEST_SPOT = (2, 4)         # a warcamp chest goes this many tiles from its bonfire
RAID_REACH = 60             # squads raid another faction's chests this close to their own bonfire

SPLIT_UNITS = 40            # a faction with this many goblins (builders and farmers too)...
SPLIT_BUILDERS = 2          # ...and at least this many builders (so both halves can build) has a schism
SPLIT_CHECK_TURNS = 10
SCHISM_DISTANCE = 45        # the half that leaves makes its camp at least this far from every faction's bonfires
SCHISM_PEACE = 400          # the two are at peace until its first bonfire is lit, or for this many turns at most
SCHISM_COOLDOWN = 150       # a faction has no schism within this many turns of its last one (or of being made)
ARRIVE_REACH = 5            # its builders light that bonfire this close to where they were going

# Storage huts: walls STORAGE_RADIUS from the middle (a 9x9 square with the corners left out), an entrance in the
# middle of each side, and a war chest on each of these spots inside, along the walls
STORAGE_RADIUS = 4
STORAGE_CHESTS = [(dx, dy) for d in (-2, -1, 1, 2) for dx, dy in ((d, -3), (d, 3), (-3, d), (3, d))]
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
    of the hut and alternate from one wall tile to the next, like laid stone. It keeps its paint when its faction
    dies out, so an abandoned camp still shows whose it was."""
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
        self.farms = []           # farm plots (see "the farmer")

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

    def __init__(self, faction, look, items=()):
        super().__init__(items)
        self.faction, self.look, self.hp = faction, look, CHEST_HP


def camp(gm):
    """This floor's camp state."""
    camps = gm.__dict__.setdefault("camps", {})
    if gm.level not in camps:
        camps[gm.level] = {"factions": {}, "next": 0, "structures": set()}
    return camps[gm.level]


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


def nudge(gm, ctx, t, f):
    """Moves a goblin of faction f off tile t onto a free tile beside it (a builder needs t). True if t is clear."""
    tile = gm.grid[t]
    if tile[0] != 5 or len(tile) < 3 or factionOf(tile[2]) != f.id:
        return tile[0] == 0
    free = [n for n in gm.neighbors(t) if organizers.passable(gm.grid[n], demise=False)]
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


def field(gm, ctx, goal, start):
    """Walking distance to goal over open floor (tiles someone stands on count as open, since they move), reaching
    far enough for a trip from start (up to PATH_REACH). Worked out once a turn per goal and shared by everyone
    heading there; redone further out if someone further away needs it."""
    fields = ctx.setdefault("fields", {})
    reach = min(PATH_REACH, int(dist(gm, start, goal) * 2) + 8)
    if goal not in fields or (fields[goal][0] < reach and start not in fields[goal][1]):
        fields[goal] = (reach, walkingDistances(gm, goal, reach))
    if start not in fields[goal][1] and fields[goal][0] < PATH_REACH:  # the way round is longer: look further
        fields[goal] = (PATH_REACH, walkingDistances(gm, goal, PATH_REACH))
    return fields[goal][1]


def neighborTable(gm):
    """Each tile's neighbors, worked out once per map (gameManager.neighbors is called a lot)."""
    key = (gm.rowLength, gm.numberOfSpots)
    cache = gm.__dict__.get("neighborCache")
    if cache is None or cache[0] != key:
        cache = (key, [tuple(gm.neighbors(t)) if t in gm.grid else () for t in range(gm.numberOfSpots)])
        gm.neighborCache = cache
    return cache[1]


def walkingDistances(gm, goal, reach):
    """{tile: steps to goal} for tiles up to reach steps away, walking over open floor, item piles and walkable
    plants (not Organizer's Demise) and anyone standing on them."""
    out, frontier = {goal: 0}, [goal]
    table, grid = neighborTable(gm), gm.grid
    for d in range(1, reach + 1):
        if not frontier:
            break
        nxt = []
        for p in frontier:
            for n in table[p]:
                if n not in out and (grid[n][0] in (1, 5) or organizers.passable(grid[n], demise=False)):
                    out[n] = d
                    nxt.append(n)
        frontier = nxt
    return out


def step(gm, i, unit, goal, protected, ctx=None, paths=None):
    """One step toward goal. With a path to it (see field), along the path onto a free tile. Without one, straight
    at it: onto free floor that gets closer, or (for a unit that digs) through a wall in the way that isn't
    protected, sliding sideways round small obstacles. Returns where it is now."""
    if ctx is not None or paths is not None:
        paths = paths if paths is not None else field(gm, ctx, goal, i)
        if i in paths:
            closer = [j for j in gm.neighbors(i) if paths.get(j, 1e9) < paths[i]]
            better = [j for j in closer if organizers.passable(gm.grid[j], demise=False)]
            if not better and unit.name == "Goblin Builder" and ctx is not None:  # its own goblins in the way: shoo one
                f = camp(gm)["factions"].get(factionOf(unit))
                better = [j for j in closer if f is not None and nudge(gm, ctx, j, f)]
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
            aside = [j for j in gm.neighbors(i) if organizers.passable(gm.grid[j], demise=False) and j in paths]
            if aside and rand.random() < 0.3:
                return organizers.moveTo(gm, i, rand.choice(aside))
            return i
    here = dist(gm, i, goal)
    options = sorted(gm.neighbors(i), key=lambda j: dist(gm, j, goal))
    for j in options:
        if dist(gm, j, goal) >= here:
            break
        tile = gm.grid[j]
        if organizers.passable(tile, demise=False):
            return organizers.moveTo(gm, i, j)
        if tile[0] == 2 and unit.wallDamage > 0 and j not in protected:
            digWall(gm, i, unit, j, BREAK_DAMAGE if unit.name == "Goblin Builder" else unit.wallDamage)
            return i
    sideways = [j for j in options if organizers.passable(gm.grid[j], demise=False) and dist(gm, j, goal) <= here + 0.5]
    if sideways and rand.random() < 0.5:
        return organizers.moveTo(gm, i, rand.choice(sideways))
    return i


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
    target.hp -= unit.damage
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


def adjacentFoe(gm, i, unit):
    """(target, position) of something hostile right beside unit, or None."""
    if not gm.peaceful and gm.playerPositionFlat in gm.neighbors(i):
        return "player", gm.playerPositionFlat
    for j in gm.neighbors(i):
        tile = gm.grid[j]
        if tile[0] == 5 and len(tile) > 2 and hostile(unit, tile[2]):
            return tile[2], j
    return None


# ---------------------------------------------------------------- the faction's turn

def takeTurn(gm, i, unit, ctx):
    """A faction unit's turn. Returns where it is now."""
    foe = adjacentFoe(gm, i, unit)
    if foe:
        attack(gm, i, unit, *foe)
        return i
    if unit.name == "Goblin Builder":
        position = builderTurn(gm, i, unit, ctx)
    elif unit.name == "Goblin Farmer":
        position = farmerTurn(gm, i, unit, ctx)
    else:
        position = soldierTurn(gm, i, unit, ctx)
    if slotsUsed(unit) > CARRY_SLOTS:
        dropExtra(gm, unit, position)
    moved(ctx, unit, position)
    return position


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
    if squad.target is not None and leaderAt is not None:  # keep after the same target while it's close
        at = gm.playerPositionFlat if squad.target == "player" and not gm.peaceful else \
            (find(gm, ctx, squad.target) if squad.target != "player" else None)
        if at is not None and dist(gm, at, leaderAt) <= CHASE_LIMIT:
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
            if not gm.peaceful and gm.playerPositionFlat not in gm.smoke and dist(gm, at, gm.playerPositionFlat) <= SIGHT \
                    and gm.lineOfSight(at, gm.playerPositionFlat):
                d = dist(gm, at, gm.playerPositionFlat)
                if best is None or d < best[0]:
                    best = (d, "player", gm.playerPositionFlat)
            for p, e in near(gm, ctx, at, SIGHT):
                if hostile(m, e) and e.hp > 0 and p not in gm.smoke and gm.lineOfSight(at, p):
                    d = dist(gm, at, p)
                    if best is None or d < best[0]:
                        best = (d, e, p)
        if best:
            squad.target = best[1]
            result = (best[1], best[2])
        elif getattr(gm, "torchLight", None):  # nobody to fight, but your torchlight in sight: into the light
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
    target = squadTarget(gm, squad, ctx, unit, i)
    if target:
        return step(gm, i, unit, target[1], protected, ctx)
    if migrating(f) is not None:  # leaving after a schism: the leader heads for the new camp, the rest follow it
        leader = squadLeader(squad)
        leaderAt = None if leader is unit else find(gm, ctx, leader)
        if leaderAt is None:
            return migrateTurn(gm, i, unit, f, ctx) if dist(gm, i, f.migrating) > 3 else organizers.wander(gm, i)
        return step(gm, i, unit, leaderAt, protected, ctx) if dist(gm, i, leaderAt) > FOLLOW_DISTANCE else i
    if squad.marching:
        home = homeBonfire(gm, f, i)
        if home is not None:
            if not squad.hauling and squadLoad(squad) >= HAUL_AT:
                squad.hauling, squad.mission = True, None  # full enough: straight home
            if squad.hauling:
                return haulTurn(gm, i, unit, squad, f, home, ctx)
            if squad.raid is None:
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
    leader = squadLeader(squad)
    leaderAt = i if leader is unit else (find(gm, ctx, leader) if leader is not None else None)
    if leader is unit or leaderAt is None:
        home = homeBonfire(gm, f, i)
        if home is None:
            return organizers.wander(gm, i)
        if not squad.marching:  # gathering: stay near the bonfire
            return step(gm, i, unit, home, protected, ctx) if dist(gm, i, home) > 3 else organizers.wander(gm, i)
        position = missionTurn(gm, i, unit, squad, f, home, ctx)
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


def roomIn(gm, chest, unit=None):
    """True if the chest has a free slot (or, for unit, already holds a stack of something it carries)."""
    items = chestAt(gm, chest)
    if len(items) < CAMP_CHEST_SLOTS:
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
        elif len(items) < CAMP_CHEST_SLOTS:
            items.append(resources.MaterialStack(materialId, amount))
        else:
            kept[materialId] = amount
    unit.gold = base + kept.pop("gold", 0)
    unit.materials = kept
    loot = getattr(unit, "loot", [])
    room = max(0, CAMP_CHEST_SLOTS - len(items))
    items.extend(loot[:room])
    unit.loot = loot[room:]
    gm.change = True


def raidTarget(gm, f, home):
    """The nearest chest of another faction (one it isn't at peace with) within RAID_REACH of home, or None."""
    theirs = [c for g in camp(gm)["factions"].values() if g is not f and not atPeace(f.id, g.id) for c in chests(gm, g)]
    near_ = [c for c in theirs if dist(gm, c, home) <= RAID_REACH]
    return min(near_, key=lambda c: dist(gm, c, home)) if near_ else None


def raidTurn(gm, i, unit, squad, f, ctx):
    """To the other faction's chest; smash it open, take what's in it, then haul it home."""
    target = squad.raid
    tile = gm.grid[target]
    if tile[0] != 3 or not isinstance(tile[2], CampChest) or tile[2].faction == f.id:
        squad.raid = None  # someone else got it first
        return i
    if target not in gm.neighbors(i):  # chests don't move: the floor-wide path map, like a bonfire's
        return step(gm, i, unit, target, f.walls(), ctx, bonfireField(gm, target))
    chest = tile[2]
    chest.hp -= unit.damage
    gm.change = True
    if chest.hp > 0:
        return i
    left, gold = take(unit, list(chest))  # the loot goes to whoever broke it open, what fits of it
    gm.grid[target] = [0, tile[1]]
    if left or gold:
        gm.placeItems(target, left, gold)
    if tile[1] == 1:
        gm.addPopup("Raided!", target)
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
    if tile[1] == 1:
        gm.addPopup("Looted", t)
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
    """Is there a plant at t a goblin can pick (not Organizer's Demise: its thorns), outside every farm plot?"""
    tile = gm.grid[t]
    if tile[0] != 8 or organizers.isDemise(tile) or (kind is not None and tile[2].kind != kind):
        return False
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
    """unit picks the plant at t: its herb, and sometimes a seed, go in its pockets (like yours, loot.PLANT_LOOT)."""
    tile = gm.grid[t]
    for materialId, amount in loot.roll(loot.PLANT_LOOT, tile[2].name):
        unit.materials[materialId] = unit.materials.get(materialId, 0) + amount
    gm.grid[t] = [0, tile[1]]
    if tile[1] == 1:
        gm.addPopup("Picked", t)
    gm.change = True


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
        spot = bonfireSpot(gm, i, i, 0, 3)
        return {"kind": "bonfire", "at": spot} if spot is not None else None
    for hut in f.huts:
        if hut["done"] and damaged(gm, hut):
            hut["done"] = False  # it lost walls, its spawner or a chest: it's built back up before any new hut
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
            hut = layOutHut(gm, center, claimed, "storage" if needStorage else "hut")
            if hut is None:
                continue
            enemyBonfire = nearestEnemyBonfire(gm, f, center)
            if enemyBonfire is not None and enemyBonfire < dist(gm, center, bonfire):
                continue  # the other faction's ground
            sites.append((dist(gm, center, bonfire) + rand.random() * 3, hut))
        if sites:
            break
    if sites:
        hut = min(sites, key=lambda s: s[0])[1]
        hut["builder"] = b
        f.huts.append(hut)
        return {"kind": "hut", "hut": hut}
    # no room around any bonfire: light a new one further out (one builder at a time, where a hut will fit)
    if any(getattr(other, "task", None) and other.task["kind"] == "bonfire" and other is not b and other.hp > 0
           and factionOf(other) == f.id for other in builders(gm)):
        return None
    spot = bonfireSpot(gm, home, i, *NEW_BONFIRE_DISTANCE, avoid=f, needRoom=claimed)
    return {"kind": "bonfire", "at": spot} if spot is not None else None

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
            if enemyBonfire is not None and enemyBonfire < dist(gm, t, center):
                continue
        candidates.add(t)
    for t in sorted(candidates, key=lambda t: dist(gm, t, near_))[:8]:
        if needRoom is None or roomForHut(gm, t, needRoom):
            return t
    return None


def layOutHut(gm, center, claimed, kind="hut"):
    """A hut ("hut": a spawner in the middle) or storage hut ("storage": war chests along its walls) centered at
    center, with an entrance in the middle of each side, or None if it doesn't fit."""
    store = kind == "storage"
    r = STORAGE_RADIUS if store else 3
    doors = [(0, -r), (0, r), (-r, 0), (r, 0)]  # an entrance in the middle of every side
    floor = [offsetTile(gm, center, dx, dy) for dy in range(-r - 1, r + 2) for dx in range(-r - 1, r + 2)]
    if None in floor:
        return None
    floor = set(floor)
    if floor & claimed or gm.playerPositionFlat in floor:
        return None
    if any(gm.grid[t][0] in (3, 4, 6, 7, 9, CAMP) for t in floor):  # no chests, piles, doors, stations or camp pieces
        return None
    walls = [offsetTile(gm, center, dx, dy) for dx, dy in hutWalls(doors, r)]
    spots = [offsetTile(gm, center, dx, dy) for dx, dy in STORAGE_CHESTS] if store else []
    inside = [offsetTile(gm, center, dx, dy) for dy in range(1 - r, r) for dx in range(1 - r, r)
              if (store or (dx, dy) != (0, 0))]
    hut = {"center": center, "floor": floor, "walls": walls, "inside": [t for t in inside if t not in spots],
           "skip": set(), "done": False, "builder": None, "kind": kind, "radius": r}
    if store:
        hut["chests"] = spots
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
    return t in gm.rooms["Stone"] and tile[0] != 2


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
    """What a hut needs next: every floor tile Stone first, then every wall, then the spawner."""
    if any(not floored(gm, hut, t) for t in hut["floor"]):
        return "floor"
    if any(needsWall(gm, hut, t) for t in hut["walls"]):
        return "walls"
    return "chests" if hut.get("kind") == "storage" else "spawner"


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
            for room in gm.rooms.values():
                room.discard(t)
            gm.rooms["Stone"].add(t)
            gm.change = True
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
            if kind in (3, 4, 6, 7, 9, CAMP):  # something there now: leave a gap
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
            nudge(gm, ctx, t, f)
            return position
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
            nudge(gm, ctx, c, f)
        return i
    position, there = goNextTo(gm, i, b, c, f, ctx)
    if there and work(hut, ("spawner", c), SPAWNER_TURNS):
        place(gm, c, Structure("spawner", f.id, hut=c))
        hut["done"] = True
        finishTask(b)
    return position


# ---------------------------------------------------------------- the farmer
# A farm plot is a Game of Life still life of one plant kind. Every plant in it has 2 or 3 neighbors of its kind, so
# none withers, and no empty tile beside it has 3, so it never grows into the shape. The empty tiles beside it with
# exactly 2 neighbors sprout now and then (plants.BIRTH_CHANCE[2]): that's the crop. A sprout gives the plants next
# to it a 4th neighbor (and they could wither), so the farmer picks sprouts as they come, pulls up any other plant
# within FARM_EDGE tiles (it could take the plot over, plants.TAKES_OVER), and replants any plant the plot loses. So
# the plot stays as it is and keeps cropping. Its plants follow the usual rules (they aren't tended like yours): a
# plot nobody looks after soon falls apart.
#
# A farmer looks after up to FARM_PLOTS plots. It starts one when there are seeds for it (its own and in the
# faction's war chests), picking the shape with the best crop per seed that fits (PLOT_SHAPES). Seeds come from the
# war chests; when there are none, it picks wild plants of that kind for seeds. Herbs and spare seeds go back in the
# chests (it keeps FARMER_SEEDS_KEPT of each kind it farms on it).

STILL_LIFES = {
    "block": [(0, 0), (1, 0), (0, 1), (1, 1)],
    "tub": [(1, 0), (0, 1), (2, 1), (1, 2)],
    "boat": [(0, 0), (1, 0), (0, 1), (2, 1), (1, 2)],
    "beehive": [(1, 0), (2, 0), (0, 1), (3, 1), (1, 2), (2, 2)],
    "loaf": [(1, 0), (2, 0), (0, 1), (3, 1), (1, 2), (3, 2), (2, 3)],
}
FARM_PLOTS = 2              # plots one farmer looks after
HUTS_PER_FARMER = 4         # a faction has at most 1 farmer, plus 1 for every this many finished huts
FARM_DISTANCE = (3, 14)     # a plot goes this far from one of its faction's bonfires
FARM_EDGE = 2               # it weeds this many tiles round the plot (the crop is on the first ring)
PLANT_TURNS = 1             # a farmer's turns to plant a seed
FARMER_SEEDS_KEPT = 3       # seeds of each kind it farms that it keeps on it
FARMER_HAUL = 6             # it takes its harvest to a war chest once it carries this much to put away
FARM_PLAN_WAIT = 25         # a farmer that finds nowhere for a plot looks again after this many turns
FORAGE_RANGE = MINE_RANGE   # how far from its bonfire a farmer looks for wild plants...
FORAGE_FAR = 35             # ...or this far, when it has nothing else to do
FARM_ABANDON = 150          # a plot with no plants left that nobody has planted in for this long is given up
FARM_KINDS = [k for k, info in plants.PLANTS.items() if info.get("wild", True) and not info.get("conway")]


def stillLifeCrops(cells):
    """([offsets beside the shape with exactly 2 neighbors in it: they crop], True if the shape is really still)."""
    cellSet, counts = set(cells), {}
    for x, y in cells:
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                if dx or dy:
                    counts[(x + dx, y + dy)] = counts.get((x + dx, y + dy), 0) + 1
    still = all(2 <= counts.get(c, 0) <= 3 for c in cells) and all(n != 3 for c, n in counts.items() if c not in cellSet)
    return [c for c, n in counts.items() if n == 2 and c not in cellSet], still


assert all(stillLifeCrops(cells)[1] for cells in STILL_LIFES.values())
# the shapes, best crop per seed first
PLOT_SHAPES = sorted(STILL_LIFES.items(), key=lambda s: -len(stillLifeCrops(s[1])[0]) / len(s[1]))


def farmerCount(gm, f):
    return sum(1 for p in gm.EnemyPositions if gm.grid[p][0] == 5 and len(gm.grid[p]) > 2
               and gm.grid[p][2].name == "Goblin Farmer" and factionOf(gm.grid[p][2]) == f.id)


def farms(f):
    return f.__dict__.setdefault("farms", [])  # (factions from saves made before farmers)


def farmTiles(f):
    return {t for p in farms(f) for t in p["cells"] + p["edge"]}


def allFarmTiles(gm):
    return {t for f in camp(gm)["factions"].values() for t in farmTiles(f)}


def myPlots(f, u):
    """The plots farmer u looks after: its own, then any whose farmer is gone (up to FARM_PLOTS)."""
    mine = [p for p in farms(f) if p.get("farmer") is u]
    for p in farms(f):
        if len(mine) >= FARM_PLOTS:
            break
        owner = p.get("farmer")
        if owner is not u and (owner is None or owner.hp <= 0 or factionOf(owner) != f.id):
            p["farmer"] = u
            mine.append(p)
    return mine


def seedOf(kind):
    return plants.PLANTS[kind]["seed"]


def chestStock(gm, f):
    """{material id: amount} across the faction's war chests."""
    stock = {}
    for c in chests(gm, f):
        for it in chestAt(gm, c):
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


def keepSeeds(plots):
    return {seedOf(p["kind"]): FARMER_SEEDS_KEPT for p in plots}


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


def planPlot(gm, f, u, i):
    """A new plot near one of the faction's bonfires, of a kind there are seeds for (not counting seeds the faction's
    other plots still need), or None."""
    have = chestStock(gm, f)
    for m, a in u.materials.items():
        have[m] = have.get(m, 0) + a
    for p in farms(f):
        seed = seedOf(p["kind"])
        have[seed] = have.get(seed, 0) - sum(1 for t in p["cells"] if gm.grid[t][0] != 8)
    kinds = sorted((k for k in FARM_KINDS if have.get(seedOf(k), 0) > 0), key=lambda k: -have[seedOf(k)])
    if not kinds:
        return None
    claimed = claimedTiles(gm)
    low, high = FARM_DISTANCE
    for bonfire in sorted(f.bonfires, key=lambda b: dist(gm, b, i)):
        anchors = [(dx, dy) for dy in range(-high, high + 1) for dx in range(-high, high + 1)]
        rand.shuffle(anchors)
        for dx, dy in anchors[:200]:
            anchor = offsetTile(gm, bonfire, dx, dy)
            if anchor is None or not low <= dist(gm, anchor, bonfire) <= high:
                continue
            enemyBonfire = nearestEnemyBonfire(gm, f, anchor)
            if enemyBonfire is not None and enemyBonfire < dist(gm, anchor, bonfire):
                continue  # the other faction's ground
            for name, shape in PLOT_SHAPES:
                plot = layOutPlot(gm, anchor, shape, claimed)
                if plot is None:
                    continue
                for kind in kinds:
                    if have[seedOf(kind)] >= len(shape) and \
                            all(plants.canGrow(kind, t, gm.grid, gm.rooms) for t in plot["cells"]):
                        plot.update(kind=kind, shape=name, farmer=u, tended=gm.turnCount)
                        return plot
    return None


def layOutPlot(gm, anchor, shape, claimed):
    """The plot's tiles for this shape at anchor: {"cells": its plants, "edge": the tiles round it it weeds}, or
    None if it doesn't fit (off the map, on claimed ground, or something in the way)."""
    cells = [offsetTile(gm, anchor, dx, dy) for dx, dy in shape]
    if None in cells or any(gm.grid[t][0] != 0 or t in claimed for t in cells):
        return None
    shapeSet = set(shape)
    around_ = {(x + dx, y + dy) for x, y in shape for dx in range(-FARM_EDGE, FARM_EDGE + 1)
               for dy in range(-FARM_EDGE, FARM_EDGE + 1)} - shapeSet
    edge = [t for t in (offsetTile(gm, anchor, dx, dy) for dx, dy in around_) if t is not None]
    if any(t in claimed or gm.grid[t][0] in (3, 4, 6, 7, 9, CAMP) for t in edge):
        return None  # no chests, doors, stations, piles or camp pieces in it
    return {"cells": cells, "edge": edge}


def farmJob(gm, i, u, f, plots, home):
    """What the farmer does next: ("harvest", plant), ("plant", tile, kind), ("fetch", chest, seed, amount),
    ("stash", chest, seeds kept), ("plot",) for a new plot it just laid out, or None for nothing."""
    nearest = lambda ts: min(ts, key=lambda t: dist(gm, t, i))
    aside = setAside(gm, u)  # what it couldn't get to lately
    # 1. pick the crop and weeds round its plots, and anything else growing in the shape
    todo = [t for p in plots for t in p["edge"] if gm.grid[t][0] == 8 and not organizers.isDemise(gm.grid[t])] + \
           [t for p in plots for t in p["cells"] if gm.grid[t][0] == 8 and gm.grid[t][2].kind != p["kind"]
            and not organizers.isDemise(gm.grid[t])]
    todo = [t for t in todo if t not in aside]
    if todo:
        return ("harvest", nearest(todo))
    keep = keepSeeds(plots)
    extra = spare(u, keep)
    own = [c for c in chests(gm, f) if roomIn(gm, c, u) and c not in aside]
    if own and sum(extra.values()) >= FARMER_HAUL:
        return ("stash", nearest(own), keep)
    # 2. replant what its plots have lost
    for p in list(plots):
        gaps = [t for t in p["cells"] if gm.grid[t][0] == 0]
        if gaps and all(t in aside for t in gaps) and \
                not any(gm.grid[t][0] == 8 and gm.grid[t][2].kind == p["kind"] for t in p["cells"]):
            farms(f).remove(p)  # it can't get to any of it: give the plot up
            continue
        gaps = [t for t in gaps if t not in aside]
        if not gaps:
            continue
        seed = seedOf(p["kind"])
        if u.materials.get(seed, 0) > 0:
            return ("plant", nearest(gaps), p["kind"])
        chest = chestWith(gm, f, seed, i)
        if chest is not None and chest not in aside:
            return ("fetch", chest, seed, len(gaps) + FARMER_SEEDS_KEPT)
        wild = plantNear(gm, home, FORAGE_RANGE, home, FORAGE_RANGE, p["kind"], avoid=aside)
        if wild is not None:
            return ("harvest", wild)  # no seeds anywhere: pick wild ones for seeds
    # 3. a new plot
    if len(plots) < FARM_PLOTS and gm.turnCount >= getattr(u, "planAfter", 0):
        plot = planPlot(gm, f, u, i)
        if plot is not None:
            farms(f).append(plot)
            return ("plot",)
        u.planAfter = gm.turnCount + FARM_PLAN_WAIT
    # 4. pick wild plants near the camp (further out if it has no plots), for the chests
    reach = FORAGE_RANGE if plots else FORAGE_FAR
    wild = plantNear(gm, home, reach, home, reach, avoid=aside)
    if wild is not None:
        return ("harvest", wild)
    if own and extra:
        return ("stash", nearest(own), keep)
    return None


def farmerTurn(gm, i, u, ctx):
    f = faction(gm, u)
    home = homeBonfire(gm, f, i) if f is not None else None
    if home is None:
        if f is not None and migrating(f) is not None and dist(gm, i, f.migrating) > 3:
            return migrateTurn(gm, i, u, f, ctx)
        return organizers.wander(gm, i)
    if getattr(u, "rest", 0) > 0:
        u.rest -= 1
        return organizers.wander(gm, i)
    for p in list(farms(f)):  # plots that died out and nobody has replanted: given up
        if gm.turnCount - p.get("tended", 0) > FARM_ABANDON and \
                not any(gm.grid[t][0] == 8 and gm.grid[t][2].kind == p["kind"] for t in p["cells"]):
            farms(f).remove(p)
    job = farmJob(gm, i, u, f, myPlots(f, u), home)
    if job is None:
        u.rest = rand.randint(4, 10)
        return organizers.wander(gm, i)
    if job[0] == "plot":
        return i
    position, there = goNextTo(gm, i, u, job[1], f, ctx)
    if not there:
        tooLong(gm, u, job[1], FARM_GIVE_UP)  # (it can't get there: set aside, it does something else next turn)
        return position
    u.headingFor = None
    action = job[0]
    if action == "harvest":
        harvestBy(gm, u, job[1])
    elif action == "plant" and work(u, ("plant", job[1]), PLANT_TURNS):
        seed = seedOf(job[2])
        u.materials[seed] -= 1
        if u.materials[seed] <= 0:
            del u.materials[seed]
        gm.grid[job[1]] = [8, gm.grid[job[1]][1], plants.Plant(job[2])]
        for p in farms(f):
            if job[1] in p["cells"]:
                p["tended"] = gm.turnCount
        gm.change = True
    elif action == "fetch":
        withdraw(gm, job[1], u, job[2], job[3])
    elif action == "stash":
        putAway(gm, job[1], u, job[2])
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
        nudge(gm, ctx, t, f)
        return position
    if there and work(hut, ("chest", t), CHEST_TURNS):
        gm.grid[t] = [3, gm.grid[t][1], CampChest(f.id, f.look)]
        chests(gm, f).add(t)
        gm.change = True
    return position


def storageChests(gm, f):
    """The war chests standing in f's storage huts."""
    mine = chests(gm, f)
    return [t for h in f.huts if h.get("kind") == "storage" for t in h["chests"] if t in mine]


def storageNeeded(gm, f):
    """Should f's builders build a storage hut now? Once it has FIRST_STORAGE_HUTS huts, whenever none of its storage
    chests has room (or it has none)."""
    if finishedHuts(f) < FIRST_STORAGE_HUTS:
        return False
    return not any(len(chestAt(gm, c)) < CAMP_CHEST_SLOTS for c in storageChests(gm, f))


def stashChest(gm, f, unit, i, home):
    """Where unit stashes what it carries: the nearest storage chest with room for it, else the nearest chest with
    room by its bonfire, or None."""
    store = [c for c in storageChests(gm, f) if roomIn(gm, c, unit)]
    if not store:
        store = [c for c in chests(gm, f) if dist(gm, c, home) <= CHEST_SPOT[1] + 2 and roomIn(gm, c, unit)]
    return min(store, key=lambda c: dist(gm, c, i)) if store else None


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
    """Half of f leaves: half its squads (whole squads), half its builders and half its farmers. They become a new
    faction in new colors and march to a spot far from every bonfire (farAway) to set up a camp there. The two are
    at peace until the new camp's first bonfire is lit. Huts, chests and farm plots all stay with f."""
    squads = [s for s in f.squads if any(m.hp > 0 for m in s.members)]
    rand.shuffle(squads)
    leaving = squads[:len(squads) // 2]
    builders = [u for _, u in units if u.name == "Goblin Builder"]
    farmers = [u for _, u in units if u.name == "Goblin Farmer"]
    rand.shuffle(builders)
    rand.shuffle(farmers)
    goers = [m for s in leaving for m in s.members if m.hp > 0] + builders[:len(builders) // 2] + farmers[:len(farmers) // 2]
    where = {id(u): p for p, u in units}
    start = next((where[id(u)] for u in goers if id(u) in where), None)
    if start is None:
        return
    goal = farAway(gm, start)
    if goal is None:
        return
    new = newFaction(gm, pickLook(gm))
    new.peaceWith, new.peaceUntil, new.migrating = f.id, gm.turnCount + SCHISM_PEACE, goal
    f.lastSchism = new.lastSchism = gm.turnCount
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
    if gm.grid[start][1] == 1:
        gm.addPopup("Schism!", start)
    gm.change = True


def farAway(gm, start):
    """A roomy open tile reachable from start, at least SCHISM_DISTANCE from every faction's bonfires (or as far as
    there is), or None."""
    reach = walkingDistances(gm, start, gm.numberOfSpots)
    fires = [b for g in camp(gm)["factions"].values() for b in g.bonfires]
    clearance = lambda t: min((dist(gm, t, b) for b in fires), default=1e9)
    open_ = [t for t in reach if gm.grid[t][0] == 0]
    if not open_:
        return None
    pool = [t for t in open_ if clearance(t) >= SCHISM_DISTANCE] or sorted(open_, key=clearance, reverse=True)[:200]
    sample = rand.sample(pool, min(200, len(pool)))
    roomy = lambda t: sum(1 for dy in range(-4, 5) for dx in range(-4, 5)
                          if (n := offsetTile(gm, t, dx, dy)) is not None and gm.grid[n][0] == 0)
    return max(sample, key=roomy)


def migrating(f):
    return getattr(f, "migrating", None)


def migrateTurn(gm, i, unit, f, ctx):
    """A step toward where its faction is going to set up camp (a floor-wide path map, like a bonfire's)."""
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
    for t in list(state["structures"]):
        tile = gm.grid.get(t)
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
    if gm.turnCount % SPLIT_CHECK_TURNS == 0:
        for f in list(state["factions"].values()):
            if migrating(f) is not None or not f.bonfires:
                continue
            if gm.turnCount - f.__dict__.setdefault("lastSchism", gm.turnCount) < SCHISM_COOLDOWN:
                continue
            units = factionUnits(gm, f)
            if len(units) >= SPLIT_UNITS and sum(u.name == "Goblin Builder" for _, u in units) >= SPLIT_BUILDERS:
                schism(gm, f, units)


def stepSpawner(gm, t, s):
    s.timer -= 1
    if s.timer > 0:
        return
    f = camp(gm)["factions"].get(s.faction)
    hut = next((h for h in f.huts if h["center"] == s.hut), None) if f else None
    inside = hut["inside"] if hut else [n for n in gm.eightAround(t)]
    free = [x for x in inside if x is not None and gm.grid[x][0] == 0]
    if not free or f is None:
        s.timer = 1  # full: try again next turn
        return
    s.timer = rand.randint(*SPAWN_TURNS)
    roll, kind = rand.random() * 100, SPAWN_ODDS[-1][0]
    for name, chance in SPAWN_ODDS:
        if roll < chance:
            kind = name
            break
        roll -= chance
    if kind == "Goblin Farmer" and farmerCount(gm, f) >= 1 + finishedHuts(f) // HUTS_PER_FARMER:
        kind = "Goblin"  # enough farmers for a camp this size
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
    spots = outOfSightSpots(gm, 10)
    rand.shuffle(spots)
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
        f = newFaction(gm, rand.choice(FIRST_LOOKS))
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
        gm.change = True
        return True
    return False


def newFaction(gm, look):
    state = camp(gm)
    f = Faction(state["next"], look)
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

def hitStructure(gm, t):
    """You hit a spawner (it takes your wall damage) or a bonfire (BONFIRE_HITS hits put it out)."""
    s = gm.grid[t][2]
    s.hp -= gm.player.getWallDamage() if s.kind == "spawner" else 1
    gm.change = True
    if s.hp > 0:
        gm.addPopup(f"{s.name} {max(0, s.hp)}/{s.maxHp}" if s.kind == "spawner" else "The fire gutters", t)
        return
    gm.grid[t] = [0, gm.grid[t][1]]
    camp(gm)["structures"].discard(t)
    f = camp(gm)["factions"].get(s.faction)
    if s.kind == "bonfire":
        if f and t in f.bonfires:
            f.bonfires.remove(t)
        gm.addPopup("Put out", t)
    else:
        gm.collectDrops(SPAWNER_DROPS, s.name, t)


def bonfires(gm):
    """Every bonfire on this floor (they give off light)."""
    state = camp(gm)
    return [t for t in state["structures"] if gm.grid[t][0] == CAMP and gm.grid[t][2].kind == "bonfire"]
