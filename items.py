class equipment():
    def __init__(self,type,name,slot):
        self.type = type
        self.name = name
        self.slot = slot

sword = equipment("Weapon","Sword","hand")


def getItemName(item):
    return item.name
