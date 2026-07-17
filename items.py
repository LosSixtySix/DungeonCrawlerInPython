class equipment():
    def __init__(self,type,name,slot,damageBounus):
        self.type = type
        self.name = name
        self.slot = slot
        self.damageBonus = damageBounus

RustySword = equipment("Weapon","Rusty Sword","Hands",1)
Pick = equipment("Tool","Pick-Axe","Hands",1)
SimpleShield = equipment("Armor","Simple Shield","Hands",1)

goblinEquipmentList = [RustySword,Pick]

equipmentList = [RustySword,Pick,SimpleShield]

def getItemName(item):
    return item.name
