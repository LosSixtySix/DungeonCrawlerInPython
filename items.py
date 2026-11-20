import random as rand

"""
Dual equipment does not mean dual weilded, it means two bonus types. For example the warpick gives a bonus to damage that is different than it's bonus to wall damage

The string for quality means this:
H -> High quality
M -> Medium quality
V -> Varied/Random quality
L -> Low quality

The valid slot types are:
->  Hands
->  Head
->  Neck
->  Back    (a Backpack, a Discarded Vestigial Hand)
->  Chest
->  Belt    (a Potion Belt)
->  Legs
->  Feet
->  Gloves

"""

class equipment():
    def __init__(self,Etype:str,name:str,slot:str,bonus:int,description:str = "None",attributeScaling = None):
        self.Etype = Etype
        self.name = name
        self.slot = slot
        self.bonus = bonus
        self.description = description
        self.attributeScaling = attributeScaling



        

class consumable(equipment):
    def __init__(self,name,bonus,effect, description="None", attributeScaling=None,slot = None,Etype= "Consume"):
        super().__init__(Etype , name,slot,bonus,description, attributeScaling)
        self.effect = effect

        
class dualEquipment(equipment):
    def __init__(self, Etype:str, name:str, slot:str, bonus:int,b2:int,description=None,attributeScaling=None):
        super().__init__(Etype, name, slot, bonus,description,attributeScaling)
        self.b1:int = bonus
        self.b2:int =  b2

class uniqueEquipment(equipment):
    def __init__(self, type, name, slot,description,attributeScaling = None):
        super().__init__(type, name, slot,description,attributeScaling)

RustySword = equipment("Damage","Rusty Sword","Hands",1,attributeScaling="strength")
Pick = equipment("WallDamage","Pick-Axe","Hands",1,attributeScaling="strength")
BurrowersAmulet:uniqueEquipment = uniqueEquipment("Unique","Burrower's Amulet","Neck","An amulet that allows the user to burrow through soft material")
startingPick = equipment("WallDamage","Worn Pick-Axe","Hands",rand.randint(1,2),attributeScaling="strength")
HealingPotion:consumable = consumable("Healing Potion",rand.randint(1,5),"Heal",attributeScaling="wisdom")
LocateDoorPotion:consumable = consumable("Potion Of Door",0,"DoorLocate")

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
                RustySword:equipment = equipment("Damage","Rusty Sword","Hands",rand.randint(1,3),attributeScaling="strength")
                Pick:equipment = equipment("WallDamage","Pick-Axe","Hands",rand.randint(1,3),attributeScaling="strength")
                SimpleShield:equipment = equipment("Defense","Simple Shield","Hands",rand.randint(1,3),attributeScaling="strength")
                Sword:equipment = equipment("Damage","Sword","Hands",rand.randint(3,5),attributeScaling="strength")
                SteelPick:equipment = equipment("WallDamage","Steel Pick-Axe","Hands",rand.randint(3,5),attributeScaling="strength")
                TearShield:equipment = equipment("Defense","Tear Sheild","Hands",rand.randint(3,5),attributeScaling="strength")
                WarPick:dualEquipment = dualEquipment("DaWa","War Pick","Hands",rand.randint(3,5),rand.randint(1,3),attributeScaling="strength")
                HealingPotion:consumable = consumable("Healing Potion",rand.randint(1,5),"Heal",attributeScaling="wisdom")
                LocateDoorPotion:consumable = consumable("Potion Of Door",0,"DoorLocate")
                itemList.append(Sword)
                itemList.append(SteelPick)
                itemList.append(TearShield)
                itemList.append(RustySword)
                itemList.append(Pick)
                itemList.append(SimpleShield)
                itemList.append(WarPick)
                itemList.append(HealingPotion)
                itemList.append(LocateDoorPotion)
                i = i +1
        case "L":
            while i < ammount:
                RustySword:equipment = equipment("Damage","Rusty Sword","Hands",rand.randint(1,3),attributeScaling="strength")
                Pick:equipment = equipment("WallDamage","Pick-Axe","Hands",rand.randint(1,3),attributeScaling="strength")
                SimpleShield:equipment = equipment("Defense","Simple Shield","Hands",rand.randint(1,3),attributeScaling="strength")

                itemList.append(RustySword)
                itemList.append(Pick)
                itemList.append(SimpleShield)
                i = i +1
    return itemList



goblinEquipmentList = [RustySword,Pick]


PILE_LIMIT = 3   # items in one pile; more spill onto the nearest tiles with room
PILE_LOOKS = 4   # how many pictures a pile can have (sprites.PILE_SPRITES)
PILE_GOLD_LIMIT = 20  # gold in one pile; it has its own slot, so it doesn't count toward PILE_LIMIT


class ItemPile():
    """Items lying loose on the floor (tile type 9): enemy drops, a broken station's scrap, things you drop.
    Unlike a chest (tile type 3) you and enemies can walk over it. look is which picture it's drawn with,
    picked at random when the pile is made. gold is loose gold in its own slot (up to PILE_GOLD_LIMIT)."""

    def __init__(self, things=None, look=None, gold=0):
        self.items = list(things or [])
        self.look = rand.randrange(PILE_LOOKS) if look is None else look
        self.gold = gold



def getItemName(item):
    return item.name

if __name__ == "__main__":
    print(HealingPotion.Etype)
    print(HealingPotion.name)
    print(HealingPotion.effect)
    print(HealingPotion.bonus)
    print(HealingPotion.attributeScaling)
