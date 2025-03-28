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
        self.equipment = {"Head":"None","Chest":"None","Gloves":"None","Hands":["None","None"],"Legs":"None","Feet":"None"}

    def equipItem(self,inventoryIndex):
        item = self.inventory.pop(inventoryIndex)
        if item.type == "Weapon":
            self.MaxDamage += item.damageBonus

        if item.slot == "Hands":
            if self.equipment["Hands"][0] == "None":
                self.equipment["Hands"][0] = item
                return
            elif self.equipment["Hands"][1] == "None":
                self.equipment["Hands"][1] = item
            else:
                self.inventory.append(self.equipment["Hands"][0])
                self.equipment["Hands"][0] = item

        else:
            if self.equipment[item.slot] != "None":
                self.inventory.append(self.equipment[item.slot])
            self.equipment[item.slot] = item

    def unEquipItem(self,slot):
        pass
    def addItemToInventory(self,item):
        if len(self.inventory) < self.inventoryLimit:
            self.inventory.append(item)
            return True
        return False
    
    def DealDamage(self):
        return random.randint(self.minDamage,self.MaxDamage)