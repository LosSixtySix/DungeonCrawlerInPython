import items
import random

class PlayerClass():
    def __init__(self):
        self.hp = 0
        self.ac = 0
        self.itemIncrement = 0
        self.wallDamage = 100
        self.minDamage = 0
        self.MaxDamage = 6
        self.inventory = []
        self.inventoryLimit = 10
        self.visionRange = 5
        self.equipment = {"Head":"None","Chest":"None","Gloves":"None","Right Hand":"None","Left Hand":"None","Legs":"None","Feet":"None"}
        self.gold = 0

    def equipItem(self,inventoryIndex):
        item = self.inventory[inventoryIndex]
        match item.type:
            case "Weapon":
                self.MaxDamage += item.damageBonus
            case "Tool":
                self.wallDamage += item.damageBonus
            case "Armor":
                self.ac += item.damageBonus
        match item.slot:
            case "Hands":
                if self.equipment["Right Hand"] == "None":
                    self.equipment["Right Hand"] = item
                    self.inventory.pop(inventoryIndex)
                elif self.equipment["Left Hand"] == "None":
                    self.equipment["Left Hand"] = item
                    self.inventory.pop(inventoryIndex)
            case _:
                if self.equipment[item.slot] == "None":
                    self.equipment[item.slot] = item
                    self.inventory.pop(inventoryIndex)

    def unEquipItem(self,slot):
        item = self.equipment[slot]
        if item != "None":
            match item.type:
                case "Weapon":
                    self.MaxDamage -= item.damageBonus
                case "Tool":
                    self.wallDamage -= item.damageBonus
                case "Armor":
                    self.ac -= item.damageBonus
            self.addItemToInventory(item)
            self.equipment[slot] = "None"

    def alterGold(self,amount):
        self.gold += amount 

    def addItemToInventory(self,item):
        if len(self.inventory) < self.inventoryLimit:
            self.inventory.append(item)
            return True
        return False
    
    def DealDamage(self):
        return random.randint(self.minDamage,self.MaxDamage)