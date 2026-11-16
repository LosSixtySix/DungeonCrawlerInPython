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
        proportion = int(total/self.hp * (tilesize**2))
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
