import random as rand
class equipment():
    def __init__(self,type,name,slot,bonus):
        self.type = type
        self.name = name
        self.slot = slot
        self.bonus = bonus

class dualEquipment(equipment):
    def __init__(self, type:str, name:str, slot:str, bonus:int,b2:int):
        super().__init__(type, name, slot, bonus)
        self.b1:int = bonus
        self.b2:int =  b2

RustySword = equipment("Damage","Rusty Sword","Hands",1)
Pick = equipment("WallDamage","Pick-Axe","Hands",1)
SimpleShield = equipment("Defense","Simple Shield","Hands",1)
WarPick:dualEquipment = dualEquipment("DaWa","War Pick","Hands",rand.randint(3,5),rand.randint(1,3))

def createRandomStatItems(ammount:int,quality:str = "V") -> list:
    itemList = []
    i:int = 0

    match quality:
        case "H":
            pass
        case "M":
            pass
        case "V":
            while i < ammount:
                RustySword:equipment = equipment("Damage","Rusty Sword","Hands",rand.randint(1,3))
                Pick:equipment = equipment("WallDamage","Pick-Axe","Hands",rand.randint(1,3))
                SimpleShield:equipment = equipment("Defense","Simple Shield","Hands",rand.randint(1,3))
                Sword:equipment = equipment("Damage","Sword","Hands",rand.randint(3,5))
                SteelPick:equipment = equipment("WallDamage","Steel Pick-Axe","Hands",rand.randint(3,5))
                TearShield:equipment = equipment("Defense","Tear Sheild","Hands",rand.randint(3,5))
                WarPick:dualEquipment = dualEquipment("DaWa","War Pick","Hands",rand.randint(3,5),rand.randint(1,3))

                itemList.append(Sword)
                itemList.append(SteelPick)
                itemList.append(TearShield)
                itemList.append(RustySword)
                itemList.append(Pick)
                itemList.append(SimpleShield)
                itemList.append(WarPick)
                i = i +1
        case "L":
            while i < ammount:
                RustySword:equipment = equipment("Damage","Rusty Sword","Hands",rand.randint(1,3))
                Pick:equipment = equipment("WallDamage","Pick-Axe","Hands",rand.randint(1,3))
                SimpleShield:equipment = equipment("Defense","Simple Shield","Hands",rand.randint(1,3))

                itemList.append(RustySword)
                itemList.append(Pick)
                itemList.append(SimpleShield)
                i = i +1
    return itemList



goblinEquipmentList = [RustySword,Pick]

def getItemName(item):
    return item.name

if __name__ == "__main__":
    l = createRandomStatItems(1)
    for i in l:
        print(i.type)
