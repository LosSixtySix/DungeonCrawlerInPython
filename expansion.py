import math
import random as rand

import enemies
import organizers

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
                  out. It only fights things right beside it.
  Spawner         every SPAWN_TURNS makes a Goblin, Goblin Chief or Goblin Builder (SPAWN_ODDS) on a free tile
                  inside its hut. It waits while the hut is full.
  Bonfire         lights the camp (BONFIRE_LIGHT_RADIUS, through the firelight system) and draws wild goblins in
                  to fight the faction.
  Squads          3 Goblins and a Chief. New goblins wait at the bonfire until they make a squad; a squad short of
                  members takes them first. Squads hunt anything that isn't their faction (you, wild goblins, other
                  factions, any other enemy), and patrol around their bonfires when there's nothing to fight.
  Splits          a faction with SPLIT_HUTS huts and two or more bonfires splits in two: the half around its
                  furthest bonfire becomes a new faction in new colors, and the two go to war ("Schism").

No two units ever share a tile: every move, spawn and build checks the tile is free.
The camp's state for each floor lives in gameManager.camps[floor] (saved with the game); the pieces on the map are
grid tiles of type CAMP holding a Structure.
"""

CAMP = 10                   # grid tile type for camp structures (spawners and bonfires)

SPAWN_TURNS = (30, 50)      # turns between a spawner's goblins
SPAWN_ODDS = [("Goblin", 70), ("Goblin Chieftan", 22), ("Goblin Builder", 8)]
SPAWNER_HP = 30
SPAWNER_DROPS = [("stone", 2), ("scrap", 1)]
BONFIRE_HITS = 3            # hits to put a bonfire out
BONFIRE_LIGHT_RADIUS = 5

BONFIRE_TURNS = 4           # a builder's turns to light a bonfire
FLOOR_TURNS = 1             # ...to floor one tile with Stone
WALL_TURNS = 2              # ...to build one hut wall
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
FOLLOW_DISTANCE = 2

TOGETHER_HUTS = 2           # until a faction has this many finished huts, all its builders work on the same hut
# who the event brings: a chief and 2 goblins (one squad, guarding the camp) and 3 builders
WARBAND = ["Goblin Chieftan", "Goblin", "Goblin", "Goblin Builder", "Goblin Builder", "Goblin Builder"]

SPLIT_HUTS = 12
SPLIT_CHECK_TURNS = 10

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

# The hut: offsets from its center. A 7x7 square with the corners left out, 1 or 2 entrances in the middle of its
# sides, a 5x5 room inside and the spawner in the middle. The Stone floor covers it and a 1-tile border.
HUT_SIDES = [(0, -3), (0, 3), (-3, 0), (3, 0)]
HUT_FLOOR = [(dx, dy) for dy in range(-4, 5) for dx in range(-4, 5)]
HUT_INSIDE = [(dx, dy) for dy in range(-2, 3) for dx in range(-2, 3) if (dx, dy) != (0, 0)]


def hutWalls(doors):
    return [(dx, dy) for dy in range(-3, 4) for dx in range(-3, 4)
            if max(abs(dx), abs(dy)) == 3 and not (abs(dx) == 3 and abs(dy) == 3) and (dx, dy) not in doors]


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
    """Would this faction unit fight other? Everything outside its own faction."""
    return factionOf(other) != factionOf(unit)


def setFaction(unit, faction):
    unit.faction, unit.look = faction.id, faction.look


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
    free = [n for n in gm.neighbors(t) if gm.grid[n][0] == 0]
    if not free:
        return False
    n, unit = rand.choice(free), tile[2]
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
    """{tile: steps to goal} for tiles up to reach steps away, walking over open floor and anyone standing on it."""
    out, frontier = {goal: 0}, [goal]
    table, grid = neighborTable(gm), gm.grid
    for d in range(1, reach + 1):
        if not frontier:
            break
        nxt = []
        for p in frontier:
            for n in table[p]:
                if n not in out and grid[n][0] in (0, 1, 5):
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
            better = [j for j in closer if gm.grid[j][0] == 0]
            if not better and unit.name == "Goblin Builder" and ctx is not None:  # its own goblins in the way: shoo one
                f = camp(gm)["factions"].get(factionOf(unit))
                better = [j for j in closer if f is not None and nudge(gm, ctx, j, f)]
            if better:
                return organizers.moveTo(gm, i, min(better, key=lambda j: paths[j]))
            return i  # the way is blocked by someone for now: wait
    here = dist(gm, i, goal)
    options = sorted(gm.neighbors(i), key=lambda j: dist(gm, j, goal))
    for j in options:
        if dist(gm, j, goal) >= here:
            break
        tile = gm.grid[j]
        if tile[0] == 0:
            return organizers.moveTo(gm, i, j)
        if tile[0] == 2 and unit.wallDamage > 0 and j not in protected:
            digWall(gm, i, unit, j, BREAK_DAMAGE if unit.name == "Goblin Builder" else unit.wallDamage)
            return i
    sideways = [j for j in options if gm.grid[j][0] == 0 and dist(gm, j, goal) <= here + 0.5]
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
    else:
        position = soldierTurn(gm, i, unit, ctx)
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
                         if b.name == "Goblin Builder" and factionOf(b) == factionOf(leader)]
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
    leader = squadLeader(squad)
    leaderAt = i if leader is unit else (find(gm, ctx, leader) if leader is not None else None)
    if leader is unit or leaderAt is None:
        home = homeBonfire(gm, f, i)
        if home is None:
            return organizers.wander(gm, i)
        if not squad.marching:  # gathering: stay near the bonfire
            return step(gm, i, unit, home, protected, ctx) if dist(gm, i, home) > 3 else organizers.wander(gm, i)
        squad.goalTurns += 1
        if squad.goal is None or dist(gm, i, squad.goal) <= 1 or squad.goalTurns > 25:
            squad.goal, squad.goalTurns = patrolSpot(gm, home), 0
        return step(gm, i, unit, squad.goal, protected, ctx) if squad.goal is not None else i
    if dist(gm, i, leaderAt) > FOLLOW_DISTANCE:
        return step(gm, i, unit, leaderAt, protected, ctx)
    return i


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
    return claimed


def nearestEnemyBonfire(gm, f, position):
    others = [b for g in camp(gm)["factions"].values() if g is not f for b in g.bonfires]
    return min((dist(gm, b, position) for b in others), default=None)


def finishedHuts(f):
    return sum(1 for h in f.huts if h["done"])


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
            hut = layOutHut(gm, center, claimed)
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


def layOutHut(gm, center, claimed):
    doors = rand.sample(HUT_SIDES, rand.choice((1, 2)))
    floor = [offsetTile(gm, center, dx, dy) for dx, dy in HUT_FLOOR]
    if None in floor:
        return None
    floor = set(floor)
    if floor & claimed or gm.playerPositionFlat in floor:
        return None
    if any(gm.grid[t][0] in (3, 4, 6, 7, 9, CAMP) for t in floor):  # no chests, piles, doors, stations or camp pieces
        return None
    walls = [offsetTile(gm, center, dx, dy) for dx, dy in hutWalls(doors)]
    inside = [offsetTile(gm, center, dx, dy) for dx, dy in HUT_INSIDE]
    return {"center": center, "floor": floor, "walls": walls, "inside": inside, "skip": set(), "done": False, "builder": None}


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
    """True once tile t of the hut is Stone floor (or one of the hut's own walls, built on it)."""
    return t in gm.rooms["Stone"] and (gm.grid[t][0] != 2 or t in hut["walls"])


def hutStage(gm, hut):
    """What a hut needs next: every floor tile Stone first, then every wall, then the spawner."""
    if any(not floored(gm, hut, t) for t in hut["floor"]):
        return "floor"
    if any(gm.grid[t][0] != 2 and t not in hut["skip"] for t in hut["walls"]):
        return "walls"
    return "spawner"


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
            if kind == 2 or t in hut["skip"]:
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
        if there and gm.grid[t][0] != 0:  # one of its own goblins standing there: shoo it
            nudge(gm, ctx, t, f)
            return position
        if there and work(hut, ("wall", t), WALL_TURNS):
            gm.grid[t] = [2, gm.grid[t][1], gm.createWall(t, gm.rooms)]
            gm.change = True
        return position
    # the spawner, in the middle: every builder on the hut helps
    c = hut["center"]
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
            if sum(h["done"] for h in f.huts) >= SPLIT_HUTS and len(f.bonfires) >= 2:
                split(gm, f)


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
    spawn(gm, rand.choice(free), kind, f)


def spawn(gm, t, kind, f):
    unit = {"Goblin": enemies.Goblin, "Goblin Chieftan": enemies.GoblinChief, "Goblin Builder": enemies.GoblinBuilder}[kind]()
    if f is not None:
        setFaction(unit, f)
    gm.grid[t] = [5, gm.grid[t][1], unit]
    gm.EnemyPositions.add(t)
    gm.change = True
    if f is not None and kind != "Goblin Builder":
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
            unit = {"Goblin": enemies.Goblin, "Goblin Chieftan": enemies.GoblinChief, "Goblin Builder": enemies.GoblinBuilder}[kind]()
            setFaction(unit, f)
            gm.grid[t] = [5, gm.grid[t][1], unit]
            gm.EnemyPositions.add(t)
            if kind != "Goblin Builder":
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


def split(gm, f):
    """f splits in two around its furthest bonfire. The new half gets new colors, and the two are at war."""
    first = f.first if f.first in f.bonfires else f.bonfires[0]
    far = max(f.bonfires, key=lambda b: dist(gm, b, first))
    new = newFaction(gm, pickLook(gm))
    allFires = list(f.bonfires)
    toNew = lambda p: dist(gm, p, far) < dist(gm, p, first)
    side = lambda p: toNew(min(allFires, key=lambda b: dist(gm, b, p)))  # goes with its nearest bonfire
    new.bonfires = [b for b in allFires if toNew(b)]
    f.bonfires = [b for b in allFires if not toNew(b)]
    new.first = far
    new.huts = [h for h in f.huts if side(h["center"])]
    f.huts = [h for h in f.huts if not side(h["center"])]
    for t in camp(gm)["structures"]:
        s = gm.grid[t][2] if gm.grid[t][0] == CAMP else None
        if s is not None and s.faction == f.id and side(t):
            s.faction = new.id
    unitsAt = {}
    for p in set(gm.EnemyPositions) | getattr(gm, "movedEnemies", set()):
        tile = gm.grid.get(p)
        if tile and tile[0] == 5 and len(tile) > 2 and factionOf(tile[2]) == f.id:
            unitsAt[id(tile[2])] = (p, tile[2])
    for squad in list(f.squads):  # whole squads change sides together, by where their leader is
        leader = squadLeader(squad)
        if leader is not None and id(leader) in unitsAt and side(unitsAt[id(leader)][0]):
            f.squads.remove(squad)
            new.squads.append(squad)
            for m in squad.members:
                setFaction(m, new)
    for p, unit in unitsAt.values():  # builders, and anyone not in a squad
        if unit.name == "Goblin Builder" and side(p):
            setFaction(unit, new)
            unit.task = None
    seen = any(gm.grid[t][1] == 1 for t in camp(gm)["structures"]) or any(gm.grid[p][1] == 1 for p, _ in unitsAt.values())
    if seen:
        gm.messageBools["schismMessage"] = True
        gm.painter.fade = 255
    gm.change = True


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
