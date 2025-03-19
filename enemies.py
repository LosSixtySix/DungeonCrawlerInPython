class Enemy():
    def __init__(self,hp,ac,speed,wallDamage,damage):
        self.hp = hp
        self.ac = ac
        self.speed = speed
        self.wallDamage = wallDamage
        self.damage = damage
        self.dig = self.CanDig()
        self.move = True

    def CanDig(self):
        if self.wallDamage > 0:
            return True
        
class Goblin(Enemy):
    def __init__(self):
        super().__init__(5, 10, 1, 5,1)
        self.inventory = [5]

