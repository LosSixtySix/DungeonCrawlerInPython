import items
import random as rand

class Enemy():
    def __init__(self,hp,ac,speed,wallDamage,damage,name):
        self.hp = hp
        self.ac = ac
        self.speed = speed
        self.name = name
        self.wallDamage = wallDamage
        self.damage = damage
        self.dig = self.CanDig()
        self.move = True

    def CanDig(self):
        if self.wallDamage > 0:
            return True
        
class Goblin(Enemy):
    def __init__(self):
        super().__init__(5, 10, 1, 2,1,"Goblin")
        self.inventory = [items.goblinEquipmentList[rand.randint(0,len(items.goblinEquipmentList)-1)]]
class GoblinChief(Enemy):
    def __init__(self):
        super().__init__(10,12,2,2,3,"Goblin Chieftan")
class DireRat(Enemy):
    def __init__(self):
        super().__init__(3,2,2,0,2,"Dire Rat")

lowerFloorEnemies = [Goblin,GoblinChief,DireRat]

if __name__ == "__main__":
    for i in range(0,5):
        print(lowerFloorEnemies[0]().inventory[0].name)