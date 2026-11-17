import items
import resources
import random
import math
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
        self.inventoryLimit = 10
        self.visionRange = 2
        self.equipment = {"Head":"None","Neck":"None","Chest":"None","Gloves":"None","Right Hand":"None","Left Hand":"None","Legs":"None","Feet":"None"}
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
        self.wardReady = True    # Warded Chainmail: the first hit on each floor does nothing
        self.burnTurns = 0       # turns of burning left (fire can set you alight; see gameManager.applyFire)

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
        match item.slot:
            case "Hands":
                if self.equipment["Right Hand"] == "None":
                    self.equipment["Right Hand"] = item
                    self.inventory.pop(inventoryIndex)
                elif self.equipment["Left Hand"] == "None":
                    self.equipment["Left Hand"] = item
                    self.inventory.pop(inventoryIndex)
                self.actionMade = True
            case _:
                if self.equipment[item.slot] == "None":
                    self.equipment[item.slot] = item
                    self.inventory.pop(inventoryIndex)
                self.actionMade = True
            

    def slotsFor(self, item):
        """The equipment slots an item can go in."""
        if item.slot == "Hands":
            return ["Right Hand", "Left Hand"]
        return [item.slot] if item.slot in self.equipment else []

    def freeSlotFor(self, item):
        return next((s for s in self.slotsFor(item) if self.equipment[s] == "None"), None)

    def swapEquip(self, inventoryIndex, slot):
        """Puts an inventory item on in place of what's in slot; the old item takes its spot in the inventory."""
        item, old = self.inventory[inventoryIndex], self.equipment[slot]
        if getattr(old, "name", None) == "Burrower's Amulet":
            self.burrow = False
        if item.name == "Burrower's Amulet":
            self.burrow = True
        self.equipment[slot] = item
        if old == "None":
            self.inventory.pop(inventoryIndex)
        else:
            self.inventory[inventoryIndex] = old
        self.actionMade = True

    def unEquipItem(self,slot):
        item = self.equipment[slot]
        if item != "None":
            if not self.addItemToInventory(item):  # no room in the inventory: it stays on
                return False
            if item.Etype == "Unique":
                if item.name == "Burrower's Amulet":
                    self.burrow = False
            self.equipment[slot] = "None"
            self.actionMade = True
            return True
        return False

    def addMaterial(self, materialId, amount):
        """Puts materials in the pouch, up to resources.POUCH_LIMIT of each. Returns how many fit."""
        have = self.materials.get(materialId, 0)
        added = max(0, min(amount, self.pouchLimit - have))
        if added:
            self.materials[materialId] = have + added
        return added

    def have(self, materialId):
        """How many of a material the player has ("gold" is their gold)."""
        return self.gold if materialId == "gold" else self.materials.get(materialId, 0)

    def hasMaterials(self, needs, times=1):
        """True if the pouch (and gold) holds everything in needs ({material id: count}), times over."""
        return all(self.have(materialId) >= count * times for materialId, count in needs.items())

    def spendMaterials(self, needs):
        for materialId, count in needs.items():
            if materialId == "gold":
                self.gold -= count
                continue
            self.materials[materialId] -= count
            if self.materials[materialId] <= 0:
                del self.materials[materialId]

    def effects(self):
        """Every effect tag on what's equipped: relic powers and enchantments (see relics.EFFECTS)."""
        tags = []
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
        return self.getequipmentBonus("FireRes")

    def magicResistance(self):
        """Magic Resist from gear. Magic ignores Defense; only this takes damage off it."""
        return self.getequipmentBonus("MagicRes")

    def damageReduction(self):
        reduction = 0
        reduction += self.getequipmentBonus("Defense")
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
        return minDamage,maxDamage

    def getWallDamage(self):
        wallDamage = 1
        for key in self.equipment.keys():
            if self.equipment[key] != "None":
                if self.equipment[key].Etype == "WallDamage":
                    wallDamage += self.attributeBonuses[self.equipment[key].attributeScaling] + self.equipment[key].bonus
                elif self.equipment[key].Etype == "DaWa":
                    wallDamage += self.attributeBonuses[self.equipment[key].attributeScaling] + self.equipment[key].b2
        return wallDamage

    def checkValidMoveLocation(self,targetLocationType):
        if targetLocationType not in self.InvalidMoveLocations:
            return True
        return False


    def DealDamage(self):
        minDamage,maxDamage = self.getMinMaxDamage()
        return random.randint(minDamage,maxDamage)
    # need to make it so any action a player makes can register on the player class so that I can do -> if player.actionmade: change = True
        