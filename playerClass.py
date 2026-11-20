import items
import resources
import relics
import random
import math

BASE_INVENTORY = 10        # inventory slots with nothing on your back (a Backpack's Storage bonus adds to it)
EXTRA_HAND = "Third Hand"  # the hand slot a Discarded Vestigial Hand (the "extra_hand" effect) gives
# The order the Equipment window lists slots in. Back and Third Hand are also added to old saves (syncSlots).
SLOT_ORDER = ["Head", "Neck", "Back", "Chest", "Gloves", "Right Hand", "Left Hand", EXTRA_HAND, "Legs", "Feet"]


def storageOf(item):
    """How many inventory slots an item adds while worn (a Backpack's Storage bonus)."""
    return item.bonus if item != "None" and item.Etype == "Storage" else 0


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
        self.pouchLimit = resources.POUCH_LIMIT  # how many of each material fit (the Leather Pouch raises it)
        self.pouchFullShown = {}  # material id -> times "pouch full" has shown since it filled (gameManager.give)
        self.wardReady = True    # Warded Chainmail: the first hit on each floor does nothing
        self.burnTurns = 0       # turns of burning left (fire can set you alight; see gameManager.applyFire)
        self.buffs = {}          # effects from the meal you last ate: effect tag -> turns left (see eat and stepBuffs)
        self.meal = None         # that meal's name, while any of its buffs last

    def levelUp(self,attribute):
        if self.gold >= self.nextLevelGold:
            self.attributes[attribute] += 1
            self.level += 1
            self.gold -= self.nextLevelGold
            self.nextLevelGold = int(((self.level**5 - self.level**(4.99999999))+10 +self.level) *2)
            self.attributeBonuses[attribute] = int(math.log2(self.attributes[attribute])*4)
            if self.damageTaken > 0:
                self.damageTaken = 0

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
                    self.inventory.pop(inventorySlot)
                    self.actionMade = True
                case "Meal":
                    self.inventory.pop(inventorySlot)
                    self.actionMade = True
                    self.eat(item)
                case "DoorLocate":
                    self.inventory.pop(inventorySlot)
                    self.actionMade = True
                    self.seeDoor = True
    
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
        """Keeps the slots in step with what's worn: the Back slot (old saves didn't have it), the Third Hand
        while something gives "extra_hand", and the inventory's size from the Backpack's Storage."""
        equipment = dict(self.equipment)
        equipment.setdefault("Back", "None")
        if any(grants(item, "extra_hand") for item in equipment.values()):
            equipment.setdefault(EXTRA_HAND, "None")
        elif equipment.get(EXTRA_HAND, "None") == "None":  # a held one is left for overflow to spill
            equipment.pop(EXTRA_HAND, None)
        ordered = {slot: equipment[slot] for slot in SLOT_ORDER if slot in equipment}
        ordered.update({slot: item for slot, item in equipment.items() if slot not in ordered})
        self.equipment = ordered
        self.inventoryLimit = BASE_INVENTORY + sum(storageOf(item) for item in ordered.values())

    def sheds(self, item):
        """True if taking this item off takes slots away with it: a Backpack (its row) or the Vestigial Hand
        (its Third Hand). Whatever is in those spills onto the ground instead of stopping you."""
        return storageOf(item) > 0 or grants(item, "extra_hand")

    def overflow(self):
        """After a Backpack or Vestigial Hand comes off: takes out whatever no longer has a slot and returns it
        for the ground. Items past the end of the smaller inventory spill; what the Third Hand held goes in the
        inventory if there's room, otherwise it spills too."""
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

    def stepBuffs(self):
        """One turn off every meal buff. Returns the tags that wore off. Losing Hearty's +2 max health can't
        kill you: you're left on at least 1."""
        buffs = getattr(self, "buffs", {})
        ended = [tag for tag in buffs if buffs[tag] <= 1]
        for tag in list(buffs):
            buffs[tag] -= 1
            if buffs[tag] <= 0:
                del buffs[tag]
        if ended:
            self.damageTaken = min(self.damageTaken, self.getMaxHealth() - 1)
        if not self.mealTurns():
            self.meal = None
        return ended

    def gearEffects(self):
        """Effect tags from what's equipped only (effects() adds the meal buffs)."""
        tags = self.effects()
        for tag in getattr(self, "buffs", {}):
            tags.remove(tag)
        return tags

    def effects(self):
        """Every effect tag on what's equipped (relic powers and enchantments, see relics.EFFECTS), plus the
        buffs from a meal."""
        tags = list(getattr(self, "buffs", {}))
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
        if len(self.inventory) < self.inventoryLimit:
            self.inventory.append(item)
            return True
        return False

    def takeDamage(self,damage):
        self.damageTaken += damage - self.damageReduction()

    def fireResistance(self):
        """Fire Resist from gear. Fire ignores Defense; only this takes damage off it."""
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
                    minDamage += self.attributeBonuses[self.equipment[key].attributeScaling]
                    maxDamage += self.equipment[key].bonus + self.attributeBonuses[self.equipment[key].attributeScaling]
        fed = 2 * self.countEffect("fed_strength")
        return minDamage + fed, maxDamage + fed

    def getWallDamage(self):
        wallDamage = 1
        for key in self.equipment.keys():
            if self.equipment[key] != "None":
                if self.equipment[key].Etype == "WallDamage":
                    wallDamage += self.attributeBonuses[self.equipment[key].attributeScaling] + self.equipment[key].bonus
                elif self.equipment[key].Etype == "DaWa":
                    wallDamage += self.attributeBonuses[self.equipment[key].attributeScaling] + self.equipment[key].b2
        return wallDamage + 2 * self.countEffect("fed_dig")

    def checkValidMoveLocation(self,targetLocationType):
        if targetLocationType not in self.InvalidMoveLocations:
            return True
        return False


    def DealDamage(self):
        minDamage,maxDamage = self.getMinMaxDamage()
        return random.randint(minDamage,maxDamage)
    # need to make it so any action a player makes can register on the player class so that I can do -> if player.actionmade: change = True
        