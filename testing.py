menuOptions = {"Load Room":True,"Generate Room":False, "Save on Exit":False}

keys = menuOptions.keys()

selectIndex = 1

def printKey():
    passes = 0
    for key in keys:
        if selectIndex == passes:
            if menuOptions[key]:
                menuOptions[key] = False
            else:
                menuOptions[key] = True
        passes +=1
        print(menuOptions[key])

printKey()
printKey()
printKey()
printKey()
input()