from cruel.inventory import items
from cruel.inventory import relics
import random as rand

CLEAN_DODGE_BASE = 0.05  # (the player's starts the same; see playerClass.CLEAN_DODGE_BASE)
FAST = 1.25  # speed of the quick ones: Dire Rats, Goblin Chieftains and the Unsealed
PITCH_RESIST_UNSEALED = 0.5  # share of Pitch damage the Unsealed shrug off


class Enemy():
    unitSize = "medium"  # how much of a space it takes: "small", "medium" or "large" (occupancy.py)

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
        self.faction = None  # the Expansion faction it fights for (expansion.py), or None: wild
        self.look = None     # its faction's colors (sprites.EXPANSION_LOOKS)
        self.foe = None      # an enemy that hit it: it fights back (expansion.otherTurn)
        self.rally = None    # a bonfire it's marching to (wild goblins, expansion.stepCamp)
        # speed: actions each turn; a fraction builds up, so 1.25 acts twice every fourth turn (gameManager.enemyActions)
        self.actionPool = 0.0
        self.evasion = 0.0     # chance an attack on it is evaded (see gameManager.dodge)
        self.cleanDodge = CLEAN_DODGE_BASE  # chance an evaded attack misses entirely instead of doing half damage

    def CanDig(self):
        if self.wallDamage > 0:
            return True
        
class Goblin(Enemy):
    unitSize = "small"
    def __init__(self):
        super().__init__(5, 10, 1, 1,1,"Goblin",5)
        self.inventory = [items.goblinEquipmentList[rand.randint(0,len(items.goblinEquipmentList)-1)]]
class GoblinChief(Enemy):
    def __init__(self):
        super().__init__(10,12,FAST,2,3,"Goblin Chieftan",15)
class DireRat(Enemy):
    unitSize = "small"
    def __init__(self):
        super().__init__(3,2,FAST,0,2,"Dire Rat",5)
        self.evasion = 0.10  # quick and small: a little hard to hit
        self.visionRange = 7
class DireMole(Enemy):
    def __init__(self):
        super().__init__(3,2,1,0,2,"Dire Mole",10)
        self.burrow = True
        self.tremorSense = True
        self.visionRange = 3
class Unsealed(Enemy):
    def __init__(self):
        super().__init__(10, 3, FAST, 3, 3, "Unsealed", 25)
        self.allSight = True
        self.fireResistPercent = 0.8  # fire barely touches it
        self.pitchResistPercent = PITCH_RESIST_UNSEALED  # Pitch is the seal's own stuff: half of it sticks


class FireGiant(Enemy):
    unitSize = "large"
    """Scorched Depths. Fills a 2x2 block of tiles: its anchor (top-left, the one on gameManager.EnemyPositions)
    and three part tiles that hold this same object. Hits for normal damage plus fire, and fire can't hurt it."""
    def __init__(self):
        super().__init__(30, 14, 0.75, 0, 6, "Fire Giant", 60)
        self.size = 2              # tiles across (and down)
        self.reach = 3             # hits you up to this many tiles from its body (1 = right beside it, +2 extra)
        self.anchor = None         # its top-left tile, kept up to date as it moves
        self.home = None           # the tile it guards (the Molten Blade's chest): it wanders near it
        self.fireDamage = 3        # fire damage added to every hit that lands
        self.igniteChance = 0.5    # chance that hit sets you burning
        self.visionRange = 6
        self.fireResistPercent = 1.0  # fire can't hurt it (Molten floor included)

class GrayPeddler(Enemy):
    """The Gray Peddler (see peddler.py): a trader who waits in his room on a floor. While he's calm he never moves
    and you trade with him. Hurt him and he's hostile for good: from then on he fights like any other enemy."""
    def __init__(self):
        super().__init__(40, 13, 1, 0, 5, "The Gray Peddler", 200)
        self.visionRange = 8
        self.merchant = True   # a trader: goblins, Organizers and other enemies leave him alone
        self.hostile = False   # set the first time you hurt him (peddler.provoke)
        self.wares = []        # his stock: peddler.Ware objects

    @property
    def loot(self):
        """What he drops when he dies: every item still in his stock (stations and the pouch upgrade aren't
        things you carry, so they're lost with him)."""
        return [ware.item for ware in self.wares if ware.item is not None]


class Dweller(Enemy):
    unitSize = "small"
    """A Dweller of the Metropolis (metropolis.py): an insectoid city-dweller. dwellers.py runs its turns. It's calm
    until it sees you do something hostile (dwellers.hostileAct); then citizens, nobles and merchants run to a guard
    to tell it, and guards hunt you. None of them dig."""
    role = None

    def __init__(self, hp, ac, speed, damage, vision, gold, name):
        super().__init__(hp, ac, speed, 0, damage, name, gold)
        self.visionRange = vision
        self.dweller = True
        self.hostile = False
        self.home = None          # where it belongs: a citizen's house, a noble's mansion, a guard's post, a shop counter
        self.goal = None          # where it's walking to while calm
        self.toldGuard = False    # a citizen, noble or merchant that has told a guard (it goes home and hides)
        self.lastSawYou = 0       # the turn it last saw you (a hostile one calms down FORGIVE_TURNS after)
        self.sawYouAt = None      # where it last saw you (what it tells a guard)
        self.enemyAt = None       # where it saw an enemy of the city: a guard heads there, anyone else tells a guard
        self.work = None          # a citizen on a works floor: "mine" or "farm" (mineshafts.py, dwellerwork.py); "dew": a Dew carrier (queen.py)
        self.target = None        # a worker: the wall it's mining (or what it's working on)
        self.materials = {}       # a worker: what it's carrying to the storehouse
        self.job = None           # a worker: "build" while it's putting up a building (dwellerbuilding.py)
        self.movingGrub = None    # a farmer: the Dew Grub it's moving to another pen (dewgrubs.py)...
        self.heldGrub = None      # ...once it has picked it up


class DwellerCitizen(Dweller):
    role = "citizen"

    def __init__(self):
        super().__init__(6, 8, 1, 1, 6, 6, "Dweller Citizen")


class DwellerNoble(Dweller):
    role = "noble"

    def __init__(self):
        super().__init__(8, 9, 1, 1, 6, 40, "Dweller Noble")


class DwellerGuard(Dweller):
    """The only Dweller that hunts you once it's hostile."""
    role = "guard"

    def __init__(self):
        super().__init__(18, 14, FAST, 4, 7, 15, "Dweller Guard")


class DwellerMerchant(Dweller):
    """Keeps a shop (cityshops.py): face it and press interact to trade."""
    role = "merchant"

    def __init__(self):
        super().__init__(10, 10, 1, 1, 6, 30, "Dweller Merchant")
        self.shopKind = None   # metropolis.SHOP_KIND_IDS
        self.wares = []        # its stock: peddler.Ware objects

    @property
    def loot(self):
        """Nothing extra drops where it dies: its stock stays in the shop (cityshops.merchantFell)."""
        return []


class DewGrub(Dweller):
    """The Dwellers' livestock (dwellerwork.py, dewgrubs.py): a fat grub kept in a pen on a city's farm floor. It
    never fights and only leaves its pen when a farmer leads it to another. Fed plants by the farmers, a grown one
    makes Dew and now and then gives birth to a young one, which makes no Dew until it's grown. It belongs to the
    city: hurting one is hostile."""
    role = "grub"
    YOUNG_NAME = "Young Dew Grub"
    GROWN_NAME = "Dew Grub"
    YOUNG_HP = 6
    GROWN_HP = 14

    def __init__(self, grown=True):
        super().__init__(self.GROWN_HP, 6, 1, 0, 3, 0, self.GROWN_NAME)
        self.pen = frozenset()    # the tiles inside its pen: it only ever moves among them
        self.feedings = 0         # plants eaten since its last Dew
        self.dewReady = False     # it has made Dew, waiting for a farmer to collect it (it eats no more until then)
        self.grown = True         # a young one makes no Dew and has no young of its own
        self.growth = 0           # a young one: plants eaten so far (dewgrubs.FEEDINGS_TO_GROW and it's grown)
        self.headedTo = None      # the pen (its inside tiles) a farmer is moving it to
        self.hunger = 0           # turns since it was last fed (dwellerfarming.STARVE_TURNS and it starves)
        if not grown:
            self.grown = False
            self.name = self.YOUNG_NAME
            self.hp = self.maxHp = self.YOUNG_HP

    @property
    def unitSize(self):
        """A young grub is small; a grown one takes a whole space."""
        return "medium" if getattr(self, "grown", True) else "small"

    def growUp(self):
        self.grown = True
        self.name = self.GROWN_NAME
        self.hp += self.GROWN_HP - self.maxHp
        self.maxHp = self.GROWN_HP


class DwellerQueen(Dweller):
    """The Queen of a Metropolis (queen.py): one to a city, in the middle of the Queen's Chamber
    (metropolis.placeCourt). A large unit like the Fire Giant (size 2: her anchor, the top-left tile on
    gameManager.EnemyPositions, and three part tiles holding this same object), but she never moves: she hits
    whatever comes within reach of her body."""
    role = "queen"
    unitSize = "large"

    def __init__(self):
        super().__init__(120, 16, 1, 8, 8, 150, "Dweller Queen")
        self.size = 2              # tiles across (and down)
        self.reach = 2             # she hits up to this many tiles from her body (1 = right beside it)
        self.anchor = None         # her top-left tile
        self.chamber = frozenset() # the inside of her chamber
        self.royalPosts = []       # where her Royal Guards stand
        self.dew = 0               # Dew her carriers have fed her (queen.py)
        self.carriersAway = {}     # her carriers down on the farm now: {carrier: the turn it went}
        self.court = {}            # what her eggs need to hatch (metropolis.placeCourt): nests, posts, homes, wanted

    @property
    def loot(self):
        """She always drops the Pheromone Crown, whoever kills her (followers.py)."""
        return [relics.make("pheromone_crown")]


class RoyalGuard(DwellerGuard):
    """One of the Queen's Royal Guards: a Dweller Guard in royal colors, stronger, that never goes more than leash
    tiles from its post beside her (dwellers.py). Never hatched: a guard pupates into one (queen.py)."""
    royal = True

    def __init__(self):
        Dweller.__init__(self, 30, 17, FAST, 7, 8, 15, "Royal Guard")
        self.leash = 8             # it won't go further than this from its post, even hunting


class DwellerEgg(Dweller):
    """An egg the Queen laid (queen.py). It never moves or fights: citizens carry it to a nest in a hatchery
    (nest), and hatchIn turns after it's put there it hatches into whatever the city needs most. court: what it
    needs to know to hatch (the Queen's, kept even if she dies)."""
    role = "egg"

    def __init__(self, court=None):
        super().__init__(4, 4, 1, 0, 0, 0, "Dweller Egg")
        self.court = court if court is not None else {}
        self.nest = None           # the nest it's in, once it's been carried there...
        self.hatchIn = None        # ...and the turns until it hatches
        self.carrier = None        # the citizen coming to carry it, and the turn it said so
        self.claimedAt = None
        self.nestTarget = None     # while it's carried: the nest it's going to


class RoyalPupa(Dweller):
    """A Dweller Guard turning into a Royal Guard (queen.py): it can't move or fight, and turnsLeft turns on it
    comes out a Royal Guard, which goes to post (by the Queen)."""
    role = "pupa"

    def __init__(self, turnsLeft=40, post=None):
        super().__init__(20, 10, 1, 0, 0, 0, "Royal Pupa")
        self.turnsLeft = turnsLeft
        self.post = post


class GoblinBuilder(Enemy):
    unitSize = "small"
    """Builds an Expansion camp: bonfires, huts and spawners (see expansion.py, which runs its turns)."""
    def __init__(self):
        super().__init__(8, 8, 1, 2, 1, "Goblin Builder", 8)
        self.task = None   # what it's building (expansion.planTask)
        self.rest = 0

class GoblinFarmer(Enemy):
    unitSize = "small"
    """Grows Game of Life plots of plants for an Expansion camp and keeps them alive (see expansion.py)."""
    def __init__(self):
        super().__init__(7, 8, 1, 1, 1, "Goblin Farmer", 6)
        self.rest = 0

class Organizer(Enemy):
    """Breaks walls to make room, then builds a pattern of new walls there (see organizers.py, which runs
    its turns). pattern says which: "spiral", "circle", "square" or "plant"."""
    pattern = None

    def __init__(self, name):
        super().__init__(8, 8, 1, 2, 2, name, 12)
        self.plan = None          # the pattern it's working on (organizers.layOut), or None while resting
        self.built = set()        # walls of the patterns it has finished (its own team leaves these alone)
        self.placed = set()       # walls it built itself and that are still standing (see organizers.wallBroken)
        self.aggro = None         # what broke one of its walls: "player" or that enemy. It hunts it down
        self.aggroTurns = 0
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
GIANT_COUNT = (2, 3)  # Fire Giants on each Scorched Depths floor
GIANT_SPAWN = (4, 10)  # they start this many tiles from the center chest...
GIANT_GUARD = 8        # ...and, when they aren't after you, wander to spots this close to it
ORGANIZER_CHANCE = 0.2  # each enemy on a new floor is an Organizer (of a random kind) this often

if __name__ == "__main__":
    for i in range(0,5):
        print(lowerFloorEnemies[0]().inventory[0].name)