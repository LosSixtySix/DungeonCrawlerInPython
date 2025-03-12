class PlayerClass():
    def __init__(self):
        self.hp = 0
        self.ac = 0
        self.wallDamage = 0 
        self.inventory = []
        self.inventoryLimit = 10
        self.equipment = {"Head":0,"Chest":0,"Gloves":0,"Left Hand":0,"Right Hand":0,"Legs":0,"Feet":0}

    def equipItem(self,item,place):
        self.equipment[place] = item

    def addItemToInventory(self,item):
        if len(self.inventory) < self.inventoryLimit:
            self.inventory.append(item)