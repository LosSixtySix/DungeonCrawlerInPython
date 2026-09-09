import random as rand

def getRandomPoints(width,height,amount):
    points = set()
    for i in range(0,amount):
        x = rand.randint(width[0],width[1]-1)
        y = rand.randint(height[0],height[1]-1)
        points.add((x,y))
    return points




class Wall():
    def __init__(self):
        self.name = "Wall"
        self.hp = 0
        self.hardness = 0
        self.brokenPoints = set()

    def takeDamage(self,damage,tilesize):
        total = (damage%self.hardness) + 1
        proportion = int(total/self.hp * (tilesize**2))
        self.brokenPoints = self.brokenPoints.union(getRandomPoints((1,tilesize-1),(1,tilesize-1),proportion))
        self.hp -= total


class StoneWall(Wall):
    def __init__(self):
        super().__init__()
        self.name = "Stone Wall"
        self.hp = 50
        self.hardness = 5
        self.soft = False

class WoodWall(Wall):
    def __init__(self):
        super().__init__()
        self.name = "Wood Wall"
        self.hp = 20
        self.hardness = 15
        self.soft = True

class SandWall(Wall):
    def __init__(self):
        super().__init__()
        self.name = "Sand Wall"
        self.hp = 10
        self.hardness = 10
        self.soft = True

class GoldWall(Wall):
    def __init__(self):
        super().__init__()
        self.name = "Gold Wall"
        self.hp = 7
        self.hardness = 2
        self.soft = False