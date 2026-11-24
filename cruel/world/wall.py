import random as rand

def getRandomPoints(width,height,amount):
    points = set()
    for i in range(0,amount):
        x = rand.randint(width[0],width[1]-1)
        y = rand.randint(height[0],height[1]-1)
        points.add((x,y))
    return points




class Wall():
    def __init__(self):
        self.name = "Wall"
        self.hp = 0
        self.hardness = 0
        self.brokenPoints = set()

    def takeDamage(self,damage,tilesize):
        # hardness is the most damage a single hit can do, so a better pick helps up to that limit
        total = min(damage, self.hardness)
        # a Dire Mole burrowing through can wear a wall down to 0 HP without breaking it: the next hit breaks it
        proportion = int(total/self.hp * (tilesize**2)) if self.hp > 0 else tilesize ** 2
        self.brokenPoints = self.brokenPoints.union(getRandomPoints((1,tilesize-1),(1,tilesize-1),proportion))
        self.hp -= total


class StoneWall(Wall):
    def __init__(self):
        super().__init__()
        self.name = "Stone Wall"
        self.hp = 40
        self.hardness = 5
        self.soft = False

class WoodWall(Wall):
    def __init__(self):
        super().__init__()
        self.name = "Wood Wall"
        self.hp = 15
        self.hardness = 15
        self.soft = True

class SandWall(Wall):
    def __init__(self):
        super().__init__()
        self.name = "Sand Wall"
        self.hp = 10
        self.hardness = 10
        self.soft = True

class GoldWall(Wall):
    def __init__(self):
        super().__init__()
        self.name = "Gold Wall"
        self.hp = 7
        self.hardness = 2
        self.soft = False

class MoltenWall(Wall):
    """Scorched Depths: rock running with lava. Breaking one burns you (gameManager.breakWall)."""
    def __init__(self):
        super().__init__()
        self.name = "Molten Wall"
        self.hp = 30
        self.hardness = 5
        self.soft = False


class PeddlerWall(Wall):
    """The walls of the Gray Peddler's room (peddler.py): a lot of HP, and no swing takes off more than its hardness,
    so even a great pick needs about 150 swings. A Bomb still takes its usual damage off (it ignores hardness)."""
    NAME = "Peddler's Stone"

    def __init__(self):
        super().__init__()
        self.name = self.NAME
        self.hp = 300
        self.hardness = 2
        self.soft = False


class CityBuildingWall(Wall):
    """A wall of a Metropolis building (metropolis.py). Each kind is named after the room it closes in (the renderer
    colors a wall by the first word of its name), and is ordinary stone to dig. Breaking one where a Dweller can see
    is a hostile act."""
    ROOM = "House"

    def __init__(self):
        super().__init__()
        self.name = f"{self.ROOM} Wall"
        self.hp = 40
        self.hardness = 5
        self.soft = False


class HouseWall(CityBuildingWall):
    ROOM = "House"


class ShopWall(CityBuildingWall):
    ROOM = "Shop"


class NobleWall(CityBuildingWall):
    ROOM = "Noble"


class FarmhouseWall(CityBuildingWall):
    """The wall of a Dwellers' farmhouse on a city's farm floor (farmhouses.py, drawn in wood colors)."""
    ROOM = "Farmhouse"

    def __init__(self):
        super().__init__()
        self.name = "Farmhouse Wall"


class PenFence(CityBuildingWall):
    """A fence round a pen of Dew Grubs on a city's farm floor (drawn in wood colors). Easier to break than a
    building's wall, but it's still the city's."""
    ROOM = "Pen"

    def __init__(self):
        super().__init__()
        self.name = "Pen Fence"
        self.hp = 15
        self.hardness = 15
        self.soft = True


class CityWall(CityBuildingWall):
    """The wall round the whole city: twice as thick as a building's."""
    ROOM = "City"

    def __init__(self):
        super().__init__()
        self.hp = 80


# ---------------------------------------------------------------- ore veins
# Veins are walls with ore in them. They're drawn in the room's own wall color with flecks of a fixed ore
# color. Any pick can mine any vein; harder veins just take more swings (hardness caps damage per hit).

class OreVein(Wall):
    def __init__(self, name, hp, hardness, ore, oreColor, oreHighlight):
        super().__init__()
        self.name = name
        self.hp = hp
        self.hardness = hardness
        self.soft = False
        self.ore = ore                      # material id it gives (see loot.WALL_AMOUNTS for amounts)
        self.oreColor = oreColor
        self.oreHighlight = oreHighlight


class CoalVein(OreVein):
    def __init__(self):
        super().__init__("Coal Vein", 20, 3, "coal", (30, 28, 28), (70, 64, 64))

class CopperVein(OreVein):
    def __init__(self):
        super().__init__("Copper Vein", 30, 4, "copper_ore", (200, 122, 58), (232, 160, 96))

class IronVein(OreVein):
    def __init__(self):
        super().__init__("Iron Vein", 45, 6, "iron_ore", (154, 90, 58), (192, 128, 96))

class SilverVein(OreVein):
    def __init__(self):
        super().__init__("Silver Vein", 60, 8, "silver_ore", (216, 221, 228), (255, 255, 255))

class GemVein(OreVein):
    """The five gems share this base; each one has its own color, floors and use at the Jeweler's Kit."""

class JadeVein(GemVein):
    def __init__(self):
        super().__init__("Jade Vein", 50, 7, "rough_jade", (46, 150, 84), (140, 220, 160))

class PeridotVein(GemVein):
    def __init__(self):
        super().__init__("Peridot Vein", 50, 7, "rough_peridot", (164, 206, 40), (230, 255, 140))

class RoseQuartzVein(GemVein):
    def __init__(self):
        super().__init__("Rose Quartz Vein", 55, 8, "rough_rose_quartz", (238, 140, 176), (255, 214, 228))

class RubyVein(GemVein):
    def __init__(self):
        super().__init__("Ruby Vein", 60, 8, "rough_ruby", (214, 32, 60), (255, 140, 152))

class AmethystVein(GemVein):
    def __init__(self):
        super().__init__("Amethyst Vein", 60, 8, "rough_amethyst", (146, 70, 206), (218, 170, 255))


# Where veins appear. Each entry: (vein class, first floor it can appear on, {floor type: clusters per
# 10,000 tiles}). A cluster is 2-5 vein tiles grown through neighboring walls. Floor types not listed get none.
VEIN_SPAWNS = [
    (CoalVein, 0, {"Mostly Wood": 8, "Mostly Stone": 5, "Mostly Sand": 4, "Mixed": 5, "All Gold": 2}),
    (CopperVein, 0, {"Mostly Stone": 4, "Mixed": 3, "Mostly Wood": 1, "Mostly Sand": 1}),
    (IronVein, 2, {"Mostly Stone": 3, "Mixed": 1.5, "Mostly Wood": 0.5}),
    (SilverVein, 4, {"Mostly Stone": 1.5, "All Gold": 2, "Mixed": 0.5}),
    # each floor type has a gem of its own; All Gold has the two rarest
    (JadeVein, 3, {"Mostly Wood": 0.8, "Mixed": 0.3}),
    (PeridotVein, 3, {"Mostly Sand": 0.8, "Mixed": 0.3}),
    (RoseQuartzVein, 4, {"Mostly Stone": 0.6, "Mixed": 0.3}),
    (RubyVein, 5, {"All Gold": 1.0, "Mostly Stone": 0.3, "Mixed": 0.2}),
    (AmethystVein, 5, {"All Gold": 1.0, "Mixed": 0.2}),
]

# The first floor each vein can appear on (from VEIN_SPAWNS). Ore floors respect these too.
VEIN_FIRST_FLOOR = {veinClass: firstFloor for veinClass, firstFloor, _ in VEIN_SPAWNS}


# ---------------------------------------------------------------- ore floors
# Rare floor types thick with one ore or gem (or a mix). They replace the normal floor type, have their own
# themes (themes.py) and room mix, and skip VEIN_SPAWNS: gamemanager.placeOreFloorVeins fills them instead.
#
#   first   first floor it can appear on (the depth gate of its ore; a Mixed floor's earliest ore)
#   weight  how likely it is, against the other ore floors unlocked at that depth
#   ores    {vein class: weight}. Each vein picks one; ores still locked at this depth are left out
#   coal    True: COAL_SHARE of the ore is coal (smelting takes 2 ore + 1 coal)
#   rooms   room mix, as weights for each room type (like createRooms' floor types)
ORE_FLOOR_CHANCE = 0.06            # chance a new floor (from floor 1) is an ore floor
ORE_FLOOR_DENSITY = (0.15, 0.35)   # share of the floor's walls turned to ore, random in this range
MOTHERLODE_CHANCE = 0.02           # chance an ore floor is a Motherlode instead (about 1 floor in 800)
MOTHERLODE_DENSITY = (0.50, 0.70)
COAL_SHARE = 1 / 3
MAX_VEIN_SIZE = 512                # veins are 2 to 2^depth tiles, never more than this

ORE_FLOORS = {
    "Copper Lode": {"first": 1, "weight": 3, "ores": {CopperVein: 1}, "coal": True,
                    "rooms": {"Stone": 20, "Sand": 5, "Wood": 2, "Gold": 1}},
    "Iron Lode": {"first": 2, "weight": 3, "ores": {IronVein: 1}, "coal": True,
                  "rooms": {"Stone": 20, "Wood": 4, "Sand": 2, "Gold": 1}},
    "Silver Lode": {"first": 4, "weight": 2, "ores": {SilverVein: 1}, "coal": True,
                    "rooms": {"Stone": 14, "Gold": 5, "Sand": 2, "Wood": 1}},
    "Mixed Lode": {"first": 2, "weight": 2, "ores": {CopperVein: 4, IronVein: 3, SilverVein: 1.5}, "coal": True,
                   "rooms": {"Stone": 18, "Sand": 4, "Wood": 3, "Gold": 2}},
    "Jade Grotto": {"first": 3, "weight": 1, "ores": {JadeVein: 1}, "coal": False,
                    "rooms": {"Wood": 18, "Stone": 4, "Sand": 2, "Gold": 1}},
    "Peridot Grotto": {"first": 3, "weight": 1, "ores": {PeridotVein: 1}, "coal": False,
                       "rooms": {"Sand": 22, "Stone": 3, "Wood": 2, "Gold": 1}},
    "Rose Quartz Grotto": {"first": 4, "weight": 1, "ores": {RoseQuartzVein: 1}, "coal": False,
                           "rooms": {"Stone": 20, "Sand": 3, "Wood": 2, "Gold": 1}},
    "Ruby Grotto": {"first": 5, "weight": 1, "ores": {RubyVein: 1}, "coal": False,
                    "rooms": {"Stone": 12, "Gold": 6, "Sand": 2, "Wood": 1}},
    "Amethyst Grotto": {"first": 5, "weight": 1, "ores": {AmethystVein: 1}, "coal": False,
                        "rooms": {"Stone": 12, "Gold": 6, "Sand": 2, "Wood": 1}},
    "Geode": {"first": 3, "weight": 1.5, "coal": False,
              "ores": {JadeVein: 4, PeridotVein: 4, RoseQuartzVein: 3, RubyVein: 2, AmethystVein: 2},
              "rooms": {"Stone": 1, "Wood": 1, "Sand": 1, "Gold": 1}},
}
