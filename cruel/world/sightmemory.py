from cruel.world import sight

"""
Remembering sight and light between redraws (gameManager.setPositionsVisible), so the same work isn't done again.

What you see and what each light lights (sight.fieldOfView) depend only on which tiles block sight: those that
gameManager.seeThroughForPlayer says no to (walls, chests, units, tall plants...), and of those, which are units (a
unit doesn't show its whole face). Each time it's asked (refresh), the floor's blockers are found again in one pass
over the grid and compared with last time's:

  Lights   each light (a fire, a lamp post, a wall lamp, a Glowrock) is kept, with what it lights, until one of
           the tiles sight.fieldOfView looked at to work it out changes (nothing else can change it). A city's lamps
           don't move, so most are only worked out again when someone walks through their light.
  Views    anything else worked out from the blockers (your own sight, Darkvision, what you see of the light far
           off) is kept under a key until any blocker on the floor changes. Opening a menu, scrolling or anything
           else that only redraws the screen uses them again.

A different grid (another floor) starts it all again.
"""

UNIT = 5
PLANT = 8


class SightMemory:
    def __init__(self, grid, rowLength):
        self.grid = grid
        self.rowLength = rowLength
        self.rowCount = len(grid) // rowLength
        self.blockers = set()
        self.units = set()
        self.lights = {}      # (source, radius): the tiles it lights
        self.lightsNear = {}  # tile: the lights (keys of lights) that looked at it
        self.views = {}       # key: anything worked out from the blockers

    def blocks(self, spot):
        return spot in self.blockers

    def lightFrom(self, source, radius):
        """The tiles a light at source lights out to radius (gameManager.lightAround), kept until a tile within
        its reach changes."""
        key = (source, radius)
        lit = self.lights.get(key)
        if lit is None:
            looked = set()
            lit = self.lights[key] = sight.fieldOfView(source, radius, self.rowLength, self.rowCount,
                                                         self.blockers.__contains__, looked=looked)
            for spot in looked:
                self.lightsNear.setdefault(spot, set()).add(key)
        return lit

    def remember(self, key, workOut):
        """What workOut() gives, kept under key until a blocker changes."""
        if key not in self.views:
            self.views[key] = workOut()
        return self.views[key]

    def update(self, blockers, units):
        """The floor's blockers now: forget what they change."""
        changed = (self.blockers ^ blockers) | (self.units ^ units)
        if changed:
            self.views.clear()
            for spot in changed:
                for key in self.lightsNear.pop(spot, ()):
                    self.lights.pop(key, None)
        self.blockers, self.units = blockers, units


def blockersOf(grid, rowLength, openKinds):
    """(blockers, units): the tiles that block your sight and light (any kind not in openKinds, and plants that
    block sight), and of those, the units. A tile missing from the map blocks too."""
    blockers, units = set(), set()
    for spot, tile in grid.items():
        kind = tile[0]
        if kind in openKinds or (kind == PLANT and not tile[2].blocksSight):
            continue
        blockers.add(spot)
        if kind == UNIT:
            units.add(spot)
    rowCount = len(grid) // rowLength
    if len(grid) != rowLength * rowCount:
        blockers |= set(range(rowLength * rowCount)) - set(grid)
    return blockers, units


def refresh(game, openKinds):
    """The floor's sight memory (game.sightMemory), brought up to date with its blockers now."""
    memory = game.__dict__.get("sightMemory")
    if memory is None or memory.grid is not game.grid or memory.rowLength != game.rowLength:
        memory = game.sightMemory = SightMemory(game.grid, game.rowLength)
    memory.update(*blockersOf(game.grid, game.rowLength, openKinds))
    return memory
