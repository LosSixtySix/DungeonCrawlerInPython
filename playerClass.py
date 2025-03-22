import items
import random

class PlayerClass():
    def __init__(self):
        self.hp = 0
        self.ac = 0
        self.itemIncrement = 0
        self.wallDamage = 100
        self.MaxDamage = 6
        self.inventory = {"Inventory":[4]}
        self.inventoryLimit = 10
        self.visionRange = 3
        self.equipment = {"Head":"None","Chest":"None","Gloves":"None","Left Hand":"None","Right Hand":"None","Legs":"None","Feet":"None"}

    def equipItem(self,item,place):
        self.equipment[place] = item

    def addItemToInventory(self,item):
        if len(self.inventory) < self.inventoryLimit:
            self.inventory["Inventory"].append(item)
            return True
        return False
    def DealDamage(self):
        return random.randint(0,6)