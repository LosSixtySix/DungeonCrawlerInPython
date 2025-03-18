class Enemy():
    def __init__(self,hp,ac,speed,wallDamage):
        self.hp = hp
        self.ac = ac
        self.speed = speed
        self.wallDamage = wallDamage
        self.dig = self.CanDig()

    def CanDig(self):
        if self.wallDamage > 0:
            return True
        
class Goblin(Enemy):
    def __init__(self):
        super().__init__(5, 10, 1, 0)
        self.inventory = [5]

