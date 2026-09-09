import items
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
                case "Heal":
                    self.damageTaken -= item.bonus + self.attributeBonuses[item.attributeScaling]
                    self.inventory.pop(inventorySlot)
                    self.actionMade = True
    
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
            

    def unEquipItem(self,slot):
        item = self.equipment[slot]
        if item != "None":
            if item.Etype == "Unique":
                if item.name == "Burrower's Amulet":
                    self.burrow = False
            self.addItemToInventory(item)
            self.equipment[slot] = "None"
            self.actionMade = True

    def alterGold(self,amount):
        self.gold += amount 

    def addItemToInventory(self,item):
        if len(self.inventory) < self.inventoryLimit:
            self.inventory.append(item)
            return True
        return False

    def takeDamage(self,damage):
        self.damageTaken += damage - self.damageReduction()

    def damageReduction(self):
        reduction = 0
        reduction += self.getequipmentBonus("Defense")
        return reduction


    def getCurrentHealth(self):
        health = self.getMaxHealth()
        return health - self.damageTaken

    def getMaxHealth(self):
        baseHealth = self.attributeBonuses["constitution"] + 10
        baseHealth += self.getequipmentBonus("Health")
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


    def DealDamage(self):
        minDamage,maxDamage = self.getMinMaxDamage()
        return random.randint(minDamage,maxDamage)
    # need to make it so any action a player makes can register on the player class so that I can do -> if player.actionmade: change = True
        