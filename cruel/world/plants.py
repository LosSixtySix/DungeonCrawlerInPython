import random

"""
Plants: herbs that grow on the floor and are used in alchemy. Each kind grows on at most two floor types
(the room's floor: Stone, Wood, Sand or Gold). Wild patches appear on new floors; harvesting one (E, like
a wall) gives its herb and sometimes a seed, and a seed can be planted on the tile you face (By Hand tab).

Growth works like Conway's Game of Life, with some randomness. Every GROW_TURNS turns, for each kind:
  - Birth: plants spread from the ones in their seed stage. An empty floor tile it can grow on, beside at least
    one plant of that kind that's gone to seed, sprouts one with BIRTH_CHANCE by how many of that kind are
    around it (of the 8): 3 is likeliest, 2 less so, and a lone seeding plant can still spread (1).
  - Death: a plant with fewer than 2 or more than 3 neighbors of its kind withers with DEATH_CHANCE, but only
    once it has seeded (reached its seed stage): sprouts, growing plants and ones in a harvest stage before their
    seed stage never wither. Planted ones too.
  - Takeover: some kinds take over others (TAKES_OVER). A wild plant with at least TAKEOVER_NEIGHBORS of a
    kind that takes it over around it is replaced by that kind with TAKEOVER_CHANCE, if the invader can grow
    on that floor. Planted ones hold their ground. The takeovers make loops (on Stone: Glowcap beats
    Bloodcap, Bloodcap beats Shadowfern, Shadowfern beats Glowcap), so no plant wins a floor for good.
Corrupted walls (Overgrowth, see events.py): a wall with at least CORRUPT_NEIGHBORS of one kind around it
(plants, or walls that kind already corrupted) can be corrupted by it, CORRUPT_CHANCE each growth step. A
corrupted wall still blocks the way and sight, but it counts as a plant of its kind: plants sprout beside it and
the corruption creeps on through the rock, so walls spread a plant instead of stopping it. Breaking one gives its
herb too. Conway kinds (Organizer's Demise) never corrupt walls.
Every plant, wild or planted, grows in stages: a sprout ("planted", STAGE_STEPS growth steps), then "growing",
then two ripe stages in the order its kind lists ("stages"): "harvest" (picking it gives its herb) and "seed"
(picking it gives seeds). The first ripe stage lasts STAGE_STEPS["ripe"] steps, then it moves on to the second,
which lasts until it's picked. Picking a plant always uses it up, whatever its stage: picked in one ripe stage,
the other is missed (so whoever wants seeds waits for its seed stage), and picked before it's ripe, it gives
nothing (loot.PLANT_LOOT). Planted plants (yours, and Expansion goblin farmers', see expansion.py) give more
(loot.CROP_LOOT). A new floor's wild patches start at stages all through the cycle (Plant.grown); everything
that sprouts after starts as a sprout.
Kinds marked "conway" follow Conway's rules exactly instead, whatever their stage: born with exactly 3 neighbors,
one dies with fewer than 2 or more than 3 (so Plant Organizers' gliders still crawl). Kinds marked "wild": False never appear in wild patches.
A plant tile is [8, visibility, Plant]. Each kind says whether it can be walked through ("walkable", by
you and by enemies) and whether it blocks sight ("blocksSight"). Standing inside a plant that is both
walkable and blocks sight hides you: enemies only notice you if they're right next to you.
"""

# id -> name, the two floors it grows on, its herb and seed (material ids), and its sprite colors
PLANTS = {
    "bloodcap": {"name": "Bloodcap", "floors": ("Stone", "Wood"), "herb": "bloodcap", "seed": "bloodcap_spores",
                 "stages": ("harvest", "seed"),
                 "walkable": False, "blocksSight": False,
                 "colors": {"c": (176, 36, 44), "C": (226, 84, 84), "w": (240, 226, 206)}},
    "hearthmoss": {"name": "Hearthmoss", "floors": ("Wood", "Sand"), "herb": "hearthmoss", "seed": "hearthmoss_spores",
                   "stages": ("seed", "harvest"),
                   "walkable": True, "blocksSight": False,
                   "colors": {"c": (70, 132, 58), "C": (132, 196, 92), "s": (52, 96, 44)}},
    "glowcap": {"name": "Glowcap", "floors": ("Stone", "Gold"), "herb": "glowcap", "seed": "glowcap_spores",
                "stages": ("harvest", "seed"),
                "walkable": True, "blocksSight": False,
                "colors": {"c": (214, 200, 96), "C": (255, 246, 176), "s": (150, 140, 110)}},
    "emberroot": {"name": "Emberroot", "floors": ("Sand", "Gold"), "herb": "emberroot", "seed": "emberroot_seed",
                  "stages": ("seed", "harvest"),
                  "walkable": False, "blocksSight": True,
                  "colors": {"c": (214, 96, 30), "C": (255, 170, 70), "s": (120, 70, 40)}},
    "shadowfern": {"name": "Shadowfern", "floors": ("Stone", "Wood"), "herb": "shadowfern", "seed": "shadowfern_spores",
                   "stages": ("harvest", "seed"),
                   "walkable": True, "blocksSight": True,
                   "colors": {"c": (62, 116, 76), "C": (112, 170, 112), "s": (34, 58, 40)}},
    # Sown by Plant Organizers as Game of Life gliders (organizers.py). It follows Conway's rules exactly
    # ("conway"), so a glider really crawls across the wood. It never grows wild ("wild": False), any
    # Organizer that touches it becomes a Plant Organizer, and it deals magic damage every turn to
    # anything else standing in it (gameManager.stepDemise).
    "organizers_demise": {"name": "Organizer's Demise", "floors": ("Wood",), "herb": "organizers_demise",
                          "seed": "organizers_demise_seed", "walkable": True, "blocksSight": False,
                          "stages": ("seed", "harvest"),
                          "conway": True, "wild": False,
                          "note": "Deals magic damage to anything standing in it, except Organizers",
                          "colors": {"c": (122, 58, 132), "C": (196, 112, 200), "s": (62, 30, 70)}},
}

GROW_TURNS = 10                    # a growth step happens this often
BIRTH_CHANCE = {3: 0.6, 2: 0.12, 1: 0.04}  # by number of neighbors of the same kind (one of them gone to seed)
DEATH_CHANCE = 0.3                 # a lonely or crowded wild plant withers
TAKES_OVER = {                     # kind -> the kinds it takes over
    "shadowfern": ["hearthmoss", "glowcap"],   # shades them out
    "bloodcap": ["shadowfern"],                # rots the fern
    "hearthmoss": ["bloodcap"],                # smothers the caps
    "glowcap": ["bloodcap", "emberroot"],      # its light starves them
    "emberroot": ["hearthmoss"],               # dries the moss out
}
TAKEOVER_NEIGHBORS = 2             # invaders needed around a plant to take it over
TAKEOVER_CHANCE = 0.35
CORRUPT_NEIGHBORS = 2              # plants (or corrupted walls) of a kind around a wall for it to corrupt it
CORRUPT_CHANCE = 0.15              # each growth step, while corruption is on (Overgrowth)
WILD_PATCHES = 4                   # wild patches on a new floor (per 10,000 tiles), 3-6 plants each
MIN_PATCHES = 3                    # every floor gets at least this many
MIN_PLANTS = 6                     # a floor that drops below this many plants gets a new wild patch
STAGE_STEPS = {"planted": 2, "growing": 3, "ripe": 3}  # growth steps a planted plant spends: as a sprout, growing,
                                                       # and in its first ripe stage (the second lasts until picked)
STAGE_NAMES = {"planted": "sprout", "growing": "growing", "harvest": "ready to harvest", "seed": "gone to seed"}


class Plant():
    def __init__(self, kind, planted=False, faction=None):
        self.kind = kind
        self.planted = planted      # sown by the player (or a goblin farmer): never taken over, and gives more
        self.faction = faction      # the Expansion faction whose farmer sowed it (None: you, or wild)
        self.stage = "planted"      # it starts as a sprout
        self.timer = STAGE_STEPS["planted"]   # growth steps left in this stage (0: it stays until picked)
        self.seeded = False         # it has reached its seed stage: from then on it can wither

    @classmethod
    def grown(cls, kind):
        """A wild plant of a new floor's patches: somewhere in its cycle already, mostly grown."""
        p = cls(kind)
        first, second = PLANTS[kind]["stages"]
        p.stage = random.choices(["planted", "growing", first, second], weights=[1, 2, 3, 3])[0]
        p.timer = {"planted": random.randint(1, STAGE_STEPS["planted"]), "growing": random.randint(1, STAGE_STEPS["growing"]),
                   first: random.randint(1, STAGE_STEPS["ripe"]), second: 0}[p.stage]
        p.seeded = p.stage == "seed" or (p.stage == second and first == "seed")
        return p

    @property
    def seeding(self):
        """In its seed stage: plants of its kind sprout around it."""
        return not self.staged or self.stage == "seed"

    @property
    def canWither(self):
        """Only once it has seeded."""
        return not self.staged or getattr(self, "seeded", True)

    @property
    def staged(self):
        return getattr(self, "stage", None) is not None  # (plants from older saves have none: full grown)

    @property
    def ready(self):
        """True in a ripe stage ("harvest" or "seed"): picking it now gives something."""
        return not self.staged or self.stage in ("harvest", "seed")

    @property
    def lastStage(self):
        """True in its second ripe stage: it stays like this until it's picked."""
        return self.staged and self.stage == PLANTS[self.kind]["stages"][1]

    def stageLabel(self):
        return STAGE_NAMES[self.stage] if self.staged else ""

    def grow(self):
        """One growth step. True if it moved on to a new stage (it looks different)."""
        if not self.staged or self.timer <= 0:
            return False
        self.timer -= 1
        if self.timer > 0:
            return False
        first, second = PLANTS[self.kind]["stages"]
        if self.stage == "planted":
            self.stage, self.timer = "growing", STAGE_STEPS["growing"]
        elif self.stage == "growing":
            self.stage, self.timer = first, STAGE_STEPS["ripe"]
        elif self.stage == first:
            self.stage, self.timer = second, 0  # (until picked)
        if self.stage == "seed":
            self.seeded = True
        return True

    def pick(self):
        """Picks it (which always uses it up). Returns the ripe stage it was picked in, or None if it wasn't ripe."""
        if not self.staged:
            return "harvest"  # (from an older save)
        return self.stage if self.ready else None

    @property
    def name(self):
        return PLANTS[self.kind]["name"]

    @property
    def walkable(self):
        return PLANTS[self.kind]["walkable"]

    @property
    def blocksSight(self):
        return PLANTS[self.kind]["blocksSight"]

    @property
    def hides(self):
        return self.walkable and self.blocksSight


def floorOf(i, rooms):
    """The floor type of a tile (the same rule the renderer uses to color floors)."""
    for room in ("Stone", "Wood", "Gold", "Molten"):
        if i in rooms.get(room, ()):
            return room
    return "Sand"


def isConway(kind):
    return PLANTS[kind].get("conway", False)


def wildKinds(floor=None):
    """The kinds that grow in wild patches (on this floor type, if given)."""
    return [k for k, info in PLANTS.items() if info.get("wild", True) and (floor is None or floor in info["floors"])]


def canGrow(kind, i, grid, rooms):
    return i in grid and grid[i][0] == 0 and floorOf(i, rooms) in PLANTS[kind]["floors"]


def around(i, rowLength, grid):
    """The up to 8 tiles around a tile, without wrapping across the map's left and right edges."""
    x = i % rowLength
    out = []
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            if (dx or dy) and 0 <= x + dx < rowLength:
                j = i + dx + dy * rowLength
                if j in grid:
                    out.append(j)
    return out


def corruptedBy(tile):
    """The plant kind a wall tile is corrupted by, or None."""
    return getattr(tile[2], "corruptedBy", None) if tile[0] == 2 and len(tile) > 2 else None


def step(grid, rooms, rowLength, birth=1.0, death=DEATH_CHANCE, corrupt=False, noBirth=(), **_):
    """One growth step for the whole floor. Returns True if anything changed. A floor event can make births
    more likely (birth), withering less likely (death) and let plants corrupt walls
    (corrupt); see events.py. Walls already corrupted count as plants of their kind either way. Nothing sprouts on
    the tiles in noBirth (farming huts). Planted plants move on through their stages."""
    plantsHere = {i: tile[2] for i, tile in grid.items() if tile[0] == 8}
    staged = False
    for plant in plantsHere.values():
        if plant.staged and plant.grow():
            staged = True
    corrupted = {i: corruptedBy(tile) for i, tile in grid.items() if corruptedBy(tile)}
    counts = {}   # (tile, kind) -> neighbors of that kind
    seeders = {}  # (tile, kind) -> those of them gone to seed (corrupted walls count: they spread their plant)
    for i, kind, seeding in [(i, p.kind, p.seeding) for i, p in plantsHere.items()] + \
            [(i, kind, True) for i, kind in corrupted.items()]:
        for j in around(i, rowLength, grid):
            counts[(j, kind)] = counts.get((j, kind), 0) + 1
            if seeding:
                seeders[(j, kind)] = seeders.get((j, kind), 0) + 1
    newlyCorrupted = {}
    if corrupt:
        for (j, kind), n in counts.items():
            if n >= CORRUPT_NEIGHBORS and not isConway(kind) and grid[j][0] == 2 and j not in corrupted \
                    and j not in newlyCorrupted and random.random() < CORRUPT_CHANCE:
                newlyCorrupted[j] = kind
        for j, kind in newlyCorrupted.items():
            grid[j][2].corruptedBy = kind
    births, deaths = {}, []
    for (j, kind), n in counts.items():
        if j in births or j in noBirth or not canGrow(kind, j, grid, rooms):
            continue
        if isConway(kind) and n == 3 or not isConway(kind) and seeders.get((j, kind)) \
                and random.random() < BIRTH_CHANCE.get(n, 0) * birth:
            births[j] = kind
    takeovers = {}
    for i, plant in plantsHere.items():
        if plant.planted:
            continue
        invaders = [k for k in TAKES_OVER if plant.kind in TAKES_OVER[k] and counts.get((i, k), 0) >= TAKEOVER_NEIGHBORS
                    and floorOf(i, rooms) in PLANTS[k]["floors"]]
        random.shuffle(invaders)
        for k in invaders:
            if random.random() < TAKEOVER_CHANCE:
                takeovers[i] = k
                break
    for i, plant in plantsHere.items():
        n = counts.get((i, plant.kind), 0)
        if i not in takeovers and (n < 2 or n > 3) and (isConway(plant.kind) or plant.canWither and random.random() < death):
            deaths.append(i)
    for j, kind in list(births.items()) + list(takeovers.items()):
        grid[j] = [8, grid[j][1], Plant(kind)]
    for i in deaths:
        grid[i] = [0, grid[i][1]]
    return bool(births or deaths or takeovers or newlyCorrupted or staged)


def growPatch(grid, rooms, rowLength, start, kind, avoid=()):
    """A wild patch of 3-6 plants spreading out from start. Returns how many were placed."""
    spot, placed, size = start, 0, random.randint(3, 6)
    for _ in range(12):
        if placed >= size:
            break
        if canGrow(kind, spot, grid, rooms) and spot not in avoid:
            grid[spot] = [8, grid[spot][1], Plant.grown(kind)]
            placed += 1
        nearby = [j for j in around(spot, rowLength, grid) if canGrow(kind, j, grid, rooms) and j not in avoid]
        if not nearby:
            break
        spot = random.choice(nearby)
    return placed


def addPatch(grid, rooms, rowLength, kind=None, avoid=()):
    """One wild patch somewhere it can grow (of this kind, or any kind). Returns how many were placed."""
    floors = [i for i, tile in grid.items() if tile[0] == 0 and i not in avoid
              and (kind is None or floorOf(i, rooms) in PLANTS[kind]["floors"])]
    for _ in range(6):  # a few tries, in case a spot has no room around it
        if not floors:
            return 0
        start = random.choice(floors)
        kinds = [kind] if kind else wildKinds(floorOf(start, rooms))
        if not kinds:
            continue
        k = random.choice(kinds)
        placed = growPatch(grid, rooms, rowLength, start, k, avoid)
        if placed >= 2:
            return placed
    return 0


def placeWild(grid, rooms, rowLength, numberOfSpots, avoid=(), everyKind=False):
    """Wild patches on a new floor (at least MIN_PATCHES). With everyKind, one patch of every plant that can
    grow on this floor comes first (the first floor, so every herb can be found from the start)."""
    if everyKind:
        for kind in wildKinds():
            addPatch(grid, rooms, rowLength, kind, avoid)
    expected = WILD_PATCHES * numberOfSpots / 10000
    patches = max(MIN_PATCHES, int(expected) + (1 if random.random() < expected % 1 else 0))
    for _ in range(patches):
        addPatch(grid, rooms, rowLength, None, avoid)


def keepAlive(grid, rooms, rowLength, avoid=()):
    """A floor whose plants have nearly all died gets a new wild patch, so every floor keeps growing."""
    if sum(1 for tile in grid.values() if tile[0] == 8) < MIN_PLANTS:
        return addPatch(grid, rooms, rowLength, None, avoid) > 0
    return False


def traits(kind):
    """A few words on how a plant behaves, e.g. "walk through it, hides you"."""
    info = PLANTS[kind]
    if info["walkable"] and info["blocksSight"]:
        return "walk into it to hide"
    return ("can be walked through" if info["walkable"] else "blocks the way") + \
           (", blocks sight" if info["blocksSight"] else "")


def takesOver(kind):
    """ "Takes over Hearthmoss and Glowcap", or "" """
    names = [PLANTS[k]["name"] for k in TAKES_OVER.get(kind, [])]
    return ("Takes over " + " and ".join(names)) if names else ""


def takenOverBy(kind):
    return [PLANTS[k]["name"] for k, victims in TAKES_OVER.items() if kind in victims]


def plantDescription(kind):
    info = PLANTS[kind]
    floors = " and ".join(info["floors"])
    text = f"Grows on {floors} floor{'s' if len(info['floors']) > 1 else ''}, {traits(kind)}"
    text += f". {info['note']}" if "note" in info else ""
    first, second = ("herbs" if s == "harvest" else "seeds" for s in info["stages"])
    text += f". Planted, it gives {first}, then {second}"
    return text + (f". {takesOver(kind)}" if takesOver(kind) else "")
