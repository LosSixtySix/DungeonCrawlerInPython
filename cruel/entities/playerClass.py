from cruel.inventory import items
from cruel.inventory import resources
from cruel.inventory import relics
import random
import math
import copy

BASE_INVENTORY = 10        # inventory slots with nothing on your back (a Backpack's Storage bonus adds to it)
EXTRA_HAND = "Third Hand"  # the hand slot a Discarded Vestigial Hand (the "extra_hand" effect) gives
# The order the Equipment window lists slots in. Back, Belt and Third Hand are also added to old saves (syncSlots).
SLOT_ORDER = ["Head", "Neck", "Back", "Chest", "Belt", "Gloves", "Right Hand", "Left Hand", EXTRA_HAND, "Legs", "Feet"]


def storageOf(item):
    """How many inventory slots an item adds while worn (a Backpack's Storage bonus)."""
    return item.bonus if item != "None" and item.Etype == "Storage" else 0


# Dexterity: speed (actions each turn) and evasion (the chance to evade an enemy's attack), both from the DEX
# attribute bonus, so they grow very slowly. Clean Dodge (how often an evaded attack misses entirely instead of
# doing half damage) doesn't come from DEX: only "CleanDodge" gear and the fed_footwork meal buff raise it.
SPEED_PER_DEX_BONUS = 0.01    # speed = 1 + this per point of DEX bonus (DEX 2: 1.04, DEX 8: 1.12, DEX 16: 1.16)
EVASION_PER_DEX_BONUS = 0.005  # evasion chance per point of DEX bonus (DEX 2: 2%, DEX 8: 6%, DEX 16: 8%); no cap
CLEAN_DODGE_BASE = 0.05
FOOTWORK_CLEAN_DODGE = 0.20   # Quickstep Skewers (fed_footwork)

POTION_STACK = "PotionStack"  # Etype of a Potion Belt: its bonus is how many of one potion share an inventory slot


def isPotion(item):
    """True for a potion, flask or bomb (a consumable that isn't a meal): what a Potion Belt can stack."""
    return item != "None" and item.Etype == "Consume" and item.effect != "Meal"


def countOf(item):
    """How many potions an inventory slot holds (1 for anything that isn't a stack)."""
    return getattr(item, "count", 1)


def sameStack(a, b):
    """True if two potions are alike enough to share a slot."""
    return isPotion(a) and isPotion(b) and (a.name, a.effect, a.bonus, a.attributeScaling) ==         (b.name, b.effect, b.bonus, b.attributeScaling)


def grants(item, tag):
    """True if a worn item would give this effect tag."""
    return item != "None" and (getattr(item, "relicPower", None) == tag or tag in getattr(item, "enchants", []))


class PlayerClass():
    def __init__(self):
        self.attributes = {"strength":1,"dexterity":1,"intelligence":1,"constitution":1,"wisdom":1}
        self.attributeBonuses = (
            {"strength":int(math.log2(self.attributes["strength"])*4),
             "dexterity":int(math.log2(self.attributes["dexterity"])*4),
             "intelligence":int(math.log2(self.attributes["intelligence"])*4),
             "constitution":int(math.log2(self.attributes["constitution"])*4),
             "wisdom":int(math.log2(self.attributes["wisdom"])*4)})
        self.damageTaken = 0
        self.itemIncrement = 0
        self.inventory = []
        self.inventoryLimit = BASE_INVENTORY
        self.visionRange = 2
        self.equipment = {slot: "None" for slot in SLOT_ORDER if slot != EXTRA_HAND}
        self.gold = 0
        self.burrow = False
        self.level = 0
        self.nextLevelGold = int((1**5 - 1**(4.99999999)) +10)
        self.actionMade = False
        self.InvalidMoveLocations = [2,3,5,None]
        self.seeDoor = False
        self.playerDirection = 0
        self.materials = {}      # the materials pouch: material id -> count (see resources.py)
        self.lootFound = set()   # what the Loot Table window has revealed (see loot.discoveryKey)
        self.stations = set()    # crafting stations the player has made, e.g. {"workbench"} (see recipes.py)
        self.stationPlaced = {}  # heavy stations that are set up: station id -> (floor, map position)
        self.followers = []  # Dwellers that follow you (followers.py: won with the Pheromone Crown)
        self.pouchLimit = resources.POUCH_LIMIT  # how many of each material fit (the Leather Pouch raises it)
        self.pouchFullShown = {}  # material id -> times "pouch full" has shown since it filled (gameManager.give)
        self.wardReady = True    # Warded Chainmail: the first hit on each floor does nothing
        self.burnTurns = 0       # turns of burning left (fire can set you alight; see gameManager.applyFire)
        self.buffs = {}          # effects from the meal you last ate: effect tag -> turns left (see eat and stepBuffs)
        self.potionEffects = {}  # effects from potions you drank: effect tag -> turns left (meals don't replace these)
        self.meal = None         # that meal's name, while any of its buffs last
        self.actionPool = 0.0    # leftover fraction of speed, carried into the next turn (see startRound)
        self.startRound()

    def levelUp(self,attribute):
        if self.gold >= self.nextLevelGold:
            self.attributes[attribute] += 1
            self.level += 1
            self.gold -= self.nextLevelGold
            self.nextLevelGold = int(((self.level**5 - self.level**(4.99999999))+10 +self.level) *2)
            self.attributeBonuses[attribute] = int(math.log2(self.attributes[attribute])*4)
            if self.damageTaken > 0:
                self.damageTaken = 0

    def getSpeed(self):
        """Actions each turn (a fraction builds up into an extra action now and then)."""
        return 1 + SPEED_PER_DEX_BONUS * self.attributeBonuses["dexterity"] + relics.LIGHTNING_SPEED * self.countEffect("lightning") \
            + relics.PHEROMONE_SPEED * self.countEffect("pheromones")

    def evasion(self):
        """Chance (0..1) to evade an enemy's attack."""
        return EVASION_PER_DEX_BONUS * self.attributeBonuses["dexterity"]

    def cleanDodge(self):
        """Chance (0..1) an evaded attack misses entirely; otherwise it does half damage."""
        return CLEAN_DODGE_BASE + self.getequipmentBonus("CleanDodge") / 100 + FOOTWORK_CLEAN_DODGE * self.countEffect("fed_footwork")

    def startRound(self):
        """A new turn: speed goes into the pool, and every whole action in it can be spent this turn."""
        pool = getattr(self, "actionPool", 0.0) + self.getSpeed()
        self.actionsAllowed = int(pool)
        self.actionPool = pool - self.actionsAllowed
        self.actionsSpent = 0

    def spendAction(self):
        """Uses one action. Returns True if that was the last one this turn (the world takes its turn then)."""
        if not hasattr(self, "actionsAllowed"):  # (saves from before speed)
            self.startRound()
        self.actionsSpent += 1
        if self.actionsSpent >= self.actionsAllowed:
            self.startRound()
            return True
        return False

    def getequipmentBonus(self,Etype,secondBonus = False):
        bonus = 0
        for key in self.equipment.keys():
            if self.equipment[key] != "None":
                if self.equipment[key].Etype == Etype:
                    if secondBonus:
                        bonus += self.equipment[key].b2
                    else:
                        bonus += self.equipment[key].bonus
        return bonus

    def useConsumable(self,inventorySlot):
        item = self.inventory[inventorySlot]
        if item.Etype == "Consume":
            match item.effect:
                case "Heal":  # can't heal past full health
                    self.damageTaken = max(0, self.damageTaken - (item.bonus + self.attributeBonuses[item.attributeScaling]))
                    self.takeOne(inventorySlot)
                    self.actionMade = True
                case "Meal":
                    self.takeOne(inventorySlot)
                    self.actionMade = True
                    self.eat(item)
                case "DoorLocate":
                    self.takeOne(inventorySlot)
                    self.actionMade = True
                    self.seeDoor = True
                case "Darkvision":  # (another one tops the turns back up, it doesn't add them)
                    self.takeOne(inventorySlot)
                    self.actionMade = True
                    self.drinkEffect("darkvision", item.bonus)
    
    def equipItem(self,inventoryIndex):
        item = self.inventory[inventoryIndex]
        if item.Etype == "Unique":
            if item.name == "Burrower's Amulet":
                self.burrow = True
                self.actionMade = True
        slot = self.freeSlotFor(item)
        if slot is not None:
            self.equipment[slot] = item
            self.inventory.pop(inventoryIndex)
            self.syncSlots()
        self.actionMade = True

    def slotsFor(self, item):
        """The equipment slots an item can go in."""
        if item.slot == "Hands":
            return [slot for slot in ("Right Hand", "Left Hand", EXTRA_HAND) if slot in self.equipment]
        return [item.slot] if item.slot in self.equipment else []

    def syncSlots(self):
        """Keeps the slots in step with what's worn: the Back and Belt slots (old saves didn't have them), the Third Hand
        while something gives "extra_hand", and the inventory's size from the Backpack's Storage."""
        equipment = dict(self.equipment)
        equipment.setdefault("Back", "None")
        equipment.setdefault("Belt", "None")
        if any(grants(item, "extra_hand") for item in equipment.values()):
            equipment.setdefault(EXTRA_HAND, "None")
        elif equipment.get(EXTRA_HAND, "None") == "None":  # a held one is left for overflow to spill
            equipment.pop(EXTRA_HAND, None)
        ordered = {slot: equipment[slot] for slot in SLOT_ORDER if slot in equipment}
        ordered.update({slot: item for slot, item in equipment.items() if slot not in ordered})
        self.equipment = ordered
        self.inventoryLimit = BASE_INVENTORY + sum(storageOf(item) for item in ordered.values())

    def sheds(self, item):
        """True if taking this item off takes room away with it: a Backpack (its row), the Vestigial Hand (its
        Third Hand) or a Potion Belt (its stacks). Whatever no longer fits spills onto the ground instead of
        stopping you."""
        return storageOf(item) > 0 or grants(item, "extra_hand") or (item != "None" and item.Etype == POTION_STACK)

    def overflow(self):
        """After a Backpack, Vestigial Hand or Potion Belt comes off: takes out whatever no longer has a slot and
        returns it for the ground. Items past the end of the smaller inventory spill; what the Third Hand held
        goes in the inventory if there's room, otherwise it spills too; potions past the stack limit are split
        into their own slots, and those that don't fit spill."""
        spilled = []
        if len(self.inventory) > self.inventoryLimit:
            spilled += self.inventory[self.inventoryLimit:]
            del self.inventory[self.inventoryLimit:]
        if EXTRA_HAND in self.equipment and not any(grants(item, "extra_hand") for item in self.equipment.values()):
            held = self.equipment.pop(EXTRA_HAND)
            if held != "None":
                if getattr(held, "name", None) == "Burrower's Amulet":
                    self.burrow = False
                if not self.addItemToInventory(held):
                    spilled.append(held)
        limit, extras = self.potionStackLimit(), []
        for held in self.inventory:  # a Potion Belt came off: stacks bigger than the new limit come apart
            while countOf(held) > limit:
                held.count -= 1
                one = copy.copy(held)
                one.count = 1
                extras.append(one)
        for one in extras:
            if not self.addItemToInventory(one):
                spilled.append(one)
        return spilled

    def freeSlotFor(self, item):
        return next((s for s in self.slotsFor(item) if self.equipment[s] == "None"), None)

    def swapEquip(self, inventoryIndex, slot):
        """Puts an inventory item on in place of what's in slot; the old item takes its spot in the inventory.
        Returns what has to go on the ground: if the old item was a Backpack or Vestigial Hand, what no longer
        fits spills, and then the old item itself if the inventory has no room left for it."""
        item, old = self.inventory.pop(inventoryIndex), self.equipment[slot]
        if getattr(old, "name", None) == "Burrower's Amulet":
            self.burrow = False
        if item.name == "Burrower's Amulet":
            self.burrow = True
        self.equipment[slot] = item
        self.syncSlots()
        spilled = self.overflow()
        if old != "None":
            if len(self.inventory) < self.inventoryLimit:
                self.inventory.insert(min(inventoryIndex, len(self.inventory)), old)
            else:
                spilled.append(old)
        self.actionMade = True
        return spilled

    def unEquipItem(self, slot):
        """Takes what's in slot off into the inventory. Returns (None, items for the ground) or (why it stays
        on, []). A full inventory keeps ordinary gear on, but a Backpack or Vestigial Hand always comes off:
        what it held is put away or spills (see overflow), and then it goes in the inventory if there's still
        room, otherwise on the ground."""
        item = self.equipment[slot]
        if item == "None":
            return "Nothing there", []
        if not self.sheds(item) and len(self.inventory) >= self.inventoryLimit:
            return "Inventory full", []
        spilled = self.takeOff(slot)[1]
        if not self.addItemToInventory(item):
            spilled.append(item)
        self.actionMade = True
        return None, spilled

    def takeOff(self, slot):
        """Empties slot and undoes anything the item did while worn. Returns (the item, what spilled because
        it came off; see overflow). Unequipping puts the item in the inventory, dropping puts it on the floor."""
        item = self.equipment[slot]
        if item.Etype == "Unique" and item.name == "Burrower's Amulet":
            self.burrow = False
        self.equipment[slot] = "None"
        self.syncSlots()
        return item, self.overflow()

    def addMaterial(self, materialId, amount):
        """Puts materials in the pouch, up to resources.POUCH_LIMIT of each. Returns how many fit."""
        have = self.materials.get(materialId, 0)
        added = max(0, min(amount, self.pouchLimit - have))
        if added:
            self.materials[materialId] = have + added
        return added

    def have(self, materialId):
        """How many of a material the player has ("gold" is their gold). Coal counts the Charcoal too: every
        CHARCOAL_PER_COAL of it is one more Coal (see spendMaterials)."""
        if materialId == "gold":
            return self.gold
        if materialId == "coal":
            return self.materials.get("coal", 0) + self.materials.get("charcoal", 0) // resources.CHARCOAL_PER_COAL
        return self.materials.get(materialId, 0)

    def hasMaterials(self, needs, times=1):
        """True if the pouch (and gold) holds everything in needs ({material id: count}), times over."""
        return all(self.have(materialId) >= count * times for materialId, count in needs.items())

    def spendMaterials(self, needs):
        for materialId, count in needs.items():
            if materialId == "gold":
                self.gold -= count
                continue
            if materialId == "coal":  # real Coal first, then Charcoal for whatever's short
                fromCoal = min(count, self.materials.get("coal", 0))
                short = count - fromCoal
                if short:
                    self.materials["charcoal"] -= short * resources.CHARCOAL_PER_COAL
                    if self.materials["charcoal"] <= 0:
                        del self.materials["charcoal"]
                count = fromCoal
                if not count:
                    continue
            self.materials[materialId] -= count
            if self.materials[materialId] <= 0:
                del self.materials[materialId]

    def eat(self, meal):
        """A meal heals a little, then its buffs last their turns. Only one meal counts at a time: eating
        another replaces the last one's bonuses with its own. Drawbacks (relics.DRAWBACKS) aren't replaced:
        they last their turns out whatever you eat after."""
        self.damageTaken = max(0, self.damageTaken - meal.bonus)
        kept = {tag: turns for tag, turns in getattr(self, "buffs", {}).items() if tag in relics.DRAWBACKS}
        self.buffs = dict(getattr(meal, "buffs", {}))
        for tag, turns in kept.items():
            self.buffs[tag] = max(self.buffs.get(tag, 0), turns)
        self.meal = meal.name

    def mealTurns(self):
        """Turns left on the current meal's bonuses (0 once they're gone, even if a drawback lingers)."""
        return max([turns for tag, turns in getattr(self, "buffs", {}).items() if tag not in relics.DRAWBACKS] or [0])

    def drawbacks(self):
        """The meal drawbacks still on you: [(effect tag, turns left)]."""
        return [(tag, turns) for tag, turns in getattr(self, "buffs", {}).items() if tag in relics.DRAWBACKS]

    def drinkEffect(self, tag, turns):
        """A potion's effect lasts turns (drinking another of the same sets it back to turns)."""
        if not hasattr(self, "potionEffects"):
            self.potionEffects = {}
        self.potionEffects[tag] = max(self.potionEffects.get(tag, 0), turns)

    def potionTurns(self):
        """[(effect tag, turns left)] for the potions you drank that still last."""
        return list(getattr(self, "potionEffects", {}).items())

    def stepBuffs(self):
        """One turn off every meal buff and drunk potion. Returns the tags that wore off. Losing Hearty's +2 max
        health can't kill you: you're left on at least 1."""
        buffs = getattr(self, "buffs", {})
        ended = [tag for tag in buffs if buffs[tag] <= 1]
        for tag in list(buffs):
            buffs[tag] -= 1
            if buffs[tag] <= 0:
                del buffs[tag]
        potions = getattr(self, "potionEffects", {})
        ended += [tag for tag in potions if potions[tag] <= 1]
        for tag in list(potions):
            potions[tag] -= 1
            if potions[tag] <= 0:
                del potions[tag]
        if ended:
            self.damageTaken = min(self.damageTaken, self.getMaxHealth() - 1)
        if not self.mealTurns():
            self.meal = None
        return ended

    def gearEffects(self):
        """Effect tags from what's equipped only (effects() adds the meal buffs and drunk potions)."""
        tags = self.effects()
        for tag in list(getattr(self, "buffs", {})) + list(getattr(self, "potionEffects", {})):
            tags.remove(tag)
        return tags

    def effects(self):
        """Every effect tag on what's equipped (relic powers and enchantments, see relics.EFFECTS), plus the
        buffs from a meal and the potions you drank."""
        tags = list(getattr(self, "buffs", {})) + list(getattr(self, "potionEffects", {}))
        for item in self.equipment.values():
            if item == "None":
                continue
            if getattr(item, "relicPower", None):
                tags.append(item.relicPower)
            tags.extend(getattr(item, "enchants", []))
        if self.burrow and "burrow" not in tags:
            tags.append("burrow")
        return tags

    def hasEffect(self, tag):
        return tag in self.effects()

    def countEffect(self, tag):
        return self.effects().count(tag)

    def holdingTorch(self):
        """True with a Torch in hand: its light can be seen by enemies (see gameManager.torchLight)."""
        return any(item != "None" and "Torch" in getattr(item, "name", "") for item in self.equipment.values())

    def getVisionRange(self):
        """How far the player sees: the base range, plus light in hand (a Torch), plus effects."""
        return self.visionRange + self.getequipmentBonus("Light") + self.countEffect("bright") + 3 * self.countEffect("far_sight")

    def hitDamage(self, damage):
        """How much an enemy hit of this size really hurts: armor (Defense) takes some off, but a hit always
        does at least 1."""
        if damage <= 0:
            return 0
        return max(1, damage - self.damageReduction())

    def alterGold(self,amount):
        self.gold += amount 

    def addItemToInventory(self,item):
        """Puts an item in the inventory: a potion goes onto a stack of the same potion if one has room (see
        potionStackLimit), anything else into a free slot. Returns False if there's no room."""
        if isPotion(item):
            limit = self.potionStackLimit()
            for held in self.inventory:
                if sameStack(held, item) and countOf(held) < limit:
                    held.count = countOf(held) + 1
                    return True
            item = copy.copy(item)  # its own object, so the stack's count isn't shared with anything else
            item.count = 1
        if len(self.inventory) < self.inventoryLimit:
            self.inventory.append(item)
            return True
        return False

    def potionStackLimit(self):
        """How many of the same potion fit in one inventory slot: 1, or a worn Potion Belt's bonus."""
        return max([1] + [item.bonus for item in self.equipment.values() if item != "None" and item.Etype == POTION_STACK])

    def roomFor(self, item):
        """How many more of this item the inventory could take (stacks with room count for potions)."""
        free = max(0, self.inventoryLimit - len(self.inventory))
        if not isPotion(item):
            return free
        limit = self.potionStackLimit()
        return free * limit + sum(limit - countOf(held) for held in self.inventory if sameStack(held, item) and countOf(held) < limit)

    def takeOne(self, index):
        """Takes one item out of inventory slot index: one potion off a stack, or the whole slot otherwise."""
        held = self.inventory[index]
        if countOf(held) > 1:
            held.count -= 1
            one = copy.copy(held)
            one.count = 1
            return one
        return self.inventory.pop(index)

    def takeDamage(self,damage):
        self.damageTaken += damage - self.damageReduction()

    def scalingBonus(self, item):
        """What an item gains from your attributes: one attribute ("strength"), several added together
        (the Molten Blade's ("strength", "intelligence")), or none."""
        scaling = getattr(item, "attributeScaling", None)
        if not scaling:
            return 0
        if isinstance(scaling, str):
            return self.attributeBonuses.get(scaling, 0)
        return sum(self.attributeBonuses.get(a, 0) for a in scaling)

    def fireImmune(self):
        """The Molten Blade: no fire hurts you or sets you burning."""
        return self.hasEffect("molten")

    def fireResistance(self):
        """Fire Resist from gear. Fire ignores Defense; only this takes damage off it."""
        if self.fireImmune():
            return 10 ** 6
        return self.getequipmentBonus("FireRes") + 2 * self.countEffect("fed_fire")

    def magicResistance(self):
        """Magic Resist from gear. Magic ignores Defense; only this takes damage off it."""
        return self.getequipmentBonus("MagicRes")

    def damageReduction(self):
        reduction = 0
        reduction += self.getequipmentBonus("Defense") + self.countEffect("fed_guard")
        return reduction


    def getCurrentHealth(self):
        health = self.getMaxHealth()
        return health - self.damageTaken

    def getMaxHealth(self):
        baseHealth = self.attributeBonuses["constitution"] + 10
        baseHealth += self.getequipmentBonus("Health") + 2 * self.countEffect("hardy")
        return baseHealth

    def getMinMaxDamage(self):
        minDamage = 0
        maxDamage = 1
        for key in self.equipment.keys():
            if self.equipment[key] != "None":
                if self.equipment[key].Etype == "Damage" or self.equipment[key].Etype == "DaWa":
                    minDamage += self.scalingBonus(self.equipment[key])
                    maxDamage += self.equipment[key].bonus + self.scalingBonus(self.equipment[key])
        fed = 2 * self.countEffect("fed_strength")
        return minDamage + fed, maxDamage + fed

    def getWallDamage(self):
        wallDamage = 1
        for key in self.equipment.keys():
            if self.equipment[key] != "None":
                if self.equipment[key].Etype == "WallDamage":
                    wallDamage += self.scalingBonus(self.equipment[key]) + self.equipment[key].bonus
                elif self.equipment[key].Etype == "DaWa":
                    wallDamage += self.scalingBonus(self.equipment[key]) + self.equipment[key].b2
        return wallDamage + 2 * self.countEffect("fed_dig")

    def checkValidMoveLocation(self,targetLocationType):
        if targetLocationType not in self.InvalidMoveLocations:
            return True
        return False


    def DealDamage(self):
        minDamage,maxDamage = self.getMinMaxDamage()
        return random.randint(minDamage,maxDamage)
    # need to make it so any action a player makes can register on the player class so that I can do -> if player.actionmade: change = True
        