menuOptions = {"Load Room":True,"Generate Room":False, "Save on Exit":True}

def saveMenuOptions(fileName,menuOptions):
    openOptions = open(fileName,'w')
    keys = menuOptions.keys()
    for key in keys:
        openOptions.write(f"{key},{menuOptions[key]}\n")


def loadMenuOptions(fileName,menuOptions):
    openOptions = open(fileName,'r')
    menuItems = openOptions.readlines()
    openOptions.close()

    for passes in range(len(menuItems)):
        menuItems.append(menuItems.pop(0).split(','))
    for item in menuItems:
        if item[1] == 'True\n' or item[1] == 'True':
            menuOptions[item[0]] = True
        elif item[1] == 'False\n' or item[1] == 'False':
            menuOptions[item[0]] = False
    print(menuOptions)


loadMenuOptions("menuOpts.txt",menuOptions)