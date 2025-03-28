class equipment():
    def __init__(self,type,name,slot,damageBounus):
        self.type = type
        self.name = name
        self.slot = slot
        self.damageBonus = damageBounus

sword = equipment("Weapon","Sword","Hands",2)


def getItemName(item):
    return item.name
