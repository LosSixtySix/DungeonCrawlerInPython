import random

"""
Plants: herbs that grow on the floor and are used in alchemy. Each kind grows on at most two floor types
(the room's floor: Stone, Wood, Sand or Gold). Wild patches appear on new floors; harvesting one (E, like
a wall) gives its herb and sometimes a seed, and a seed can be planted on the tile you face (By Hand tab).

Growth works like Conway's Game of Life, with some randomness. Every GROW_TURNS turns, for each kind:
  - Birth: an empty floor tile it can grow on, with exactly 3 neighbors of that kind (of the 8 around it),
    sprouts one with BIRTH_CHANCE[3]; with 2 neighbors, BIRTH_CHANCE[2] (so a planted pair can spread).
  - Death: a wild plant with fewer than 2 or more than 3 neighbors of its kind withers with DEATH_CHANCE.
    Plants you planted yourself are tended, so they never wither.
  - Takeover: some kinds take over others (TAKES_OVER). A wild plant with at least TAKEOVER_NEIGHBORS of a
    kind that takes it over around it is replaced by that kind with TAKEOVER_CHANCE, if the invader can grow
    on that floor. Tended plants hold their ground. The takeovers make loops (on Stone: Glowcap beats
    Bloodcap, Bloodcap beats Shadowfern, Shadowfern beats Glowcap), so no plant wins a floor for good.
Kinds marked "conway" follow Conway's rules exactly instead: born with exactly 3 neighbors, a wild one dies
with fewer than 2 or more than 3. Kinds marked "wild": False never appear in wild patches.
A plant tile is [8, visibility, Plant]. Each kind says whether it can be walked through ("walkable", by
you and by enemies) and whether it blocks sight ("blocksSight"). Standing inside a plant that is both
walkable and blocks sight hides you: enemies only notice you if they're right next to you.
"""

# id -> name, the two floors it grows on, its herb and seed (material ids), and its sprite colors
PLANTS = {
    "bloodcap": {"name": "Bloodcap", "floors": ("Stone", "Wood"), "herb": "bloodcap", "seed": "bloodcap_spores",
                 "walkable": False, "blocksSight": False,
                 "colors": {"c": (176, 36, 44), "C": (226, 84, 84), "w": (240, 226, 206)}},
    "hearthmoss": {"name": "Hearthmoss", "floors": ("Wood", "Sand"), "herb": "hearthmoss", "seed": "hearthmoss_spores",
                   "walkable": True, "blocksSight": False,
                   "colors": {"c": (70, 132, 58), "C": (132, 196, 92), "s": (52, 96, 44)}},
    "glowcap": {"name": "Glowcap", "floors": ("Stone", "Gold"), "herb": "glowcap", "seed": "glowcap_spores",
                "walkable": True, "blocksSight": False,
                "colors": {"c": (214, 200, 96), "C": (255, 246, 176), "s": (150, 140, 110)}},
    "emberroot": {"name": "Emberroot", "floors": ("Sand", "Gold"), "herb": "emberroot", "seed": "emberroot_seed",
                  "walkable": False, "blocksSight": True,
                  "colors": {"c": (214, 96, 30), "C": (255, 170, 70), "s": (120, 70, 40)}},
    "shadowfern": {"name": "Shadowfern", "floors": ("Stone", "Wood"), "herb": "shadowfern", "seed": "shadowfern_spores",
                   "walkable": True, "blocksSight": True,
                   "colors": {"c": (62, 116, 76), "C": (112, 170, 112), "s": (34, 58, 40)}},
    # Sown by Plant Organizers as Game of Life gliders (organizers.py). It follows Conway's rules exactly
    # ("conway"), so a glider really crawls across the wood. It never grows wild ("wild": False), any
    # Organizer that touches it becomes a Plant Organizer, and it deals magic damage every turn to
    # anything else standing in it (gameManager.stepDemise).
    "organizers_demise": {"name": "Organizer's Demise", "floors": ("Wood",), "herb": "organizers_demise",
                          "seed": "organizers_demise_seed", "walkable": True, "blocksSight": False,
                          "conway": True, "wild": False,
                          "note": "Deals magic damage to anything standing in it, except Organizers",
                          "colors": {"c": (122, 58, 132), "C": (196, 112, 200), "s": (62, 30, 70)}},
}

GROW_TURNS = 10                    # a growth step happens this often
BIRTH_CHANCE = {3: 0.6, 2: 0.12}   # by number of neighbors of the same kind
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
MAX_PLANTS = 160                   # a floor stops growing new plants past this many
SEED_CHANCE = 35                   # percent chance a harvest also gives a seed
WILD_PATCHES = 4                   # wild patches on a new floor (per 10,000 tiles), 3-6 plants each
MIN_PATCHES = 3                    # every floor gets at least this many
MIN_PLANTS = 6                     # a floor that drops below this many plants gets a new wild patch


class Plant():
    def __init__(self, kind, planted=False):
        self.kind = kind
        self.planted = planted      # sown by the player: tended, never withers

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
    for room in ("Stone", "Wood", "Gold"):
        if i in rooms[room]:
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


def step(grid, rooms, rowLength, birth=1.0, death=DEATH_CHANCE, maxPlants=MAX_PLANTS, **_):
    """One growth step for the whole floor. Returns True if anything changed. A floor event can make births
    more likely (birth), withering less likely (death) and raise the cap (maxPlants); see events.py."""
    plantsHere = {i: tile[2] for i, tile in grid.items() if tile[0] == 8}
    counts = {}  # (tile, kind) -> neighbors of that kind
    for i, plant in plantsHere.items():
        for j in around(i, rowLength, grid):
            counts[(j, plant.kind)] = counts.get((j, plant.kind), 0) + 1
    births, deaths = {}, []
    room = maxPlants - len(plantsHere)
    for (j, kind), n in counts.items():
        if j in births or room <= 0 or not canGrow(kind, j, grid, rooms):
            continue
        if isConway(kind) and n == 3 or not isConway(kind) and random.random() < BIRTH_CHANCE.get(n, 0) * birth:
            births[j] = kind
            room -= 1
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
        if i not in takeovers and not plant.planted and (n < 2 or n > 3) and (isConway(plant.kind) or random.random() < death):
            deaths.append(i)
    for j, kind in list(births.items()) + list(takeovers.items()):
        grid[j] = [8, grid[j][1], Plant(kind)]
    for i in deaths:
        grid[i] = [0, grid[i][1]]
    return bool(births or deaths or takeovers)


def growPatch(grid, rooms, rowLength, start, kind, avoid=()):
    """A wild patch of 3-6 plants spreading out from start. Returns how many were placed."""
    spot, placed, size = start, 0, random.randint(3, 6)
    for _ in range(12):
        if placed >= size:
            break
        if canGrow(kind, spot, grid, rooms) and spot not in avoid:
            grid[spot] = [8, grid[spot][1], Plant(kind)]
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
    return text + (f". {takesOver(kind)}" if takesOver(kind) else "")
