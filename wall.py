class Wall():
    def __init__(self):
        self.name = "Wall"
        self.hp = 0
        self.hardness = 0

class StoneWall(Wall):
    def __init__(self):
        super().__init__()
        self.name = "Stone Wall"
        self.hp = 15
        self.hardness = 3

class WoodWall(Wall):
    def __init__(self):
        super().__init__()
        self.name = "Wood Wall"
        self.hp = 10
        self.hardness = 2

class SandWall(Wall):
    def __init__(self):
        super().__init__()
        self.name = "Sand Wall"
        self.hp = 5
        self.hardness = 1

class GoldWall(Wall):
    def __init__(self):
        super().__init__()
        self.name = "Gold Wall"
        self.hp = 7
        self.hardness = 2