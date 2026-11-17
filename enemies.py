import items
import random as rand

class Enemy():
    def __init__(self,hp,ac,speed,wallDamage,damage,name,goldWorth):
        self.hp = hp
        self.ac = ac
        self.speed = speed
        self.name = name
        self.wallDamage = wallDamage
        self.damage = damage
        self.dig = self.CanDig()
        self.move = True
        self.lastPlayerPosition = None
        self.visionRange = 5
        self.burrow = False
        self.tremorSense = False
        self.allSight = False
        self.gold = goldWorth
        self.maxHp = hp  # for bleeding at low health
        self.materials = {}  # materials pocketed from walls it broke: {material id: amount}. You get some back by killing it

    def CanDig(self):
        if self.wallDamage > 0:
            return True
        
class Goblin(Enemy):
    def __init__(self):
        super().__init__(5, 10, 1, 1,1,"Goblin",5)
        self.inventory = [items.goblinEquipmentList[rand.randint(0,len(items.goblinEquipmentList)-1)]]
class GoblinChief(Enemy):
    def __init__(self):
        super().__init__(10,12,2,2,3,"Goblin Chieftan",15)
class DireRat(Enemy):
    def __init__(self):
        super().__init__(3,2,2,0,2,"Dire Rat",5)
        self.visionRange = 7
class DireMole(Enemy):
    def __init__(self):
        super().__init__(3,2,1,0,2,"Dire Mole",10)
        self.burrow = True
        self.tremorSense = True
        self.visionRange = 3
class Unsealed(Enemy):
    def __init__(self):
        super().__init__(10, 3, 2, 3, 3, "Unsealed", 25)
        self.allSight = True
        self.fireResistPercent = 0.8  # fire barely touches it

class Organizer(Enemy):
    """Breaks walls to make room, then builds a pattern of new walls there (see organizers.py, which runs
    its turns). pattern says which: "spiral", "circle", "square" or "plant"."""
    pattern = None

    def __init__(self, name):
        super().__init__(8, 8, 1, 2, 2, name, 12)
        self.plan = None          # the pattern it's working on (organizers.layOut), or None while resting
        self.built = set()        # walls of the patterns it has finished (organizers leave these alone)
        self.rest = rand.randint(0, 8)
        self.workOn = None        # what it's partway through: ("wall" / "wood" / "sow", tile)
        self.progress = 0
        self.stuck = 0
        self.didSomething = False

class SpiralOrganizer(Organizer):
    pattern = "spiral"
    def __init__(self):
        super().__init__("Spiral Organizer")
class CircleOrganizer(Organizer):
    pattern = "circle"
    def __init__(self):
        super().__init__("Circle Organizer")
class SquareOrganizer(Organizer):
    pattern = "square"
    def __init__(self):
        super().__init__("Square Organizer")
class PlantOrganizer(Organizer):
    pattern = "plant"
    def __init__(self):
        super().__init__("Plant Organizer")

lowerFloorEnemies = [Goblin,GoblinChief,DireRat,DireMole]
organizers = [SpiralOrganizer, CircleOrganizer, SquareOrganizer, PlantOrganizer]
ORGANIZER_CHANCE = 0.2  # each enemy on a new floor is an Organizer (of a random kind) this often

if __name__ == "__main__":
    for i in range(0,5):
        print(lowerFloorEnemies[0]().inventory[0].name)