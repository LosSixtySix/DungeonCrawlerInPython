
import pygame
import pygame.freetype
import random as rand
import connectingEmptyRooms as CER
import playerClass as pc
import items
import enemies
import wall
import math

pygame.init()
pygame.font.init()

WIDTH = 720
HEIGHT = 720
SCREENWIDTH = 1000
SCREENHEIGHT = 800

MENUWIDTH = int(WIDTH/2)-125
MENUHEIGHT = 10

TEXTSTARTWIDTH = 732
TEXTSTARTHEIGHT = 15

TEXTROWGAPDISTANCE = 20



loadRoom = True
generateRoom = False
saveMap = False

menuOptions = {"Load Room":True,"Generate Room":True, "Save on Exit":True}

level = 0


white = (255, 255, 255) 
green = (0, 255, 0) 
blue = (0, 0, 128) 
black = (0, 0, 0)
red = (255,0,0)
purple = (128, 0, 128)
brown = (88,57,39)
gray = (128,128,128)
tan = (253,217,181)
woodBrown = (96,59,42)
floorGray = (65,65,65)
gold = (239,191,4)
swampFloor = (108,148,108)

crimson = (75,0,0)
ratBrown = (86,75,73)

shadowyGray = (108,108,108)
shadowyTan = (193,154,121)
shadowywoodBrown = (56,19,2)
shadowyfloorGray = (45,45,45)
shadowyPurple = (88,0,88)
shadowyGold = (133,106,2)
shadowySwampFloor = (88,108,88)

floorColor = None
shadowyFloorColor = None


FONTCOLOR = gray

player:pc = pc.PlayerClass()

FONT = pygame.font.Font('freesansbold.ttf',15)

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



def displayEquipmentHelper(key,startWidth,firstSlot=None,secondSlot=None,equipmentName=None,selectItem = False):
    gapBetweenText = 10
    text = FONT.render("Equipment",True,FONTCOLOR,black)
    textHeight = text.get_height()
    equipmentStartHeight = HEIGHT + textHeight*3

    textRect = text.get_rect()
    textWidth = text.get_width()
    
    textRect.center = (int(textWidth/2)+15,HEIGHT + textHeight*3)
    win.blit(text,textRect)

    equipmentStartWidth = startWidth

    if selectItem:
        equipmentText = FONT.render(f">{key}:[{equipmentName}]",True,FONTCOLOR,black)
    else:
        equipmentText = FONT.render(f"{key}:[{equipmentName}]",True,FONTCOLOR,black)

    equipmentTextRect = equipmentText.get_rect()
    equipmentTextWidth = equipmentText.get_width()
    equipmentTextHeight = equipmentText.get_height()
    equipmentTextRect.center = (int(equipmentTextWidth/2) + equipmentStartWidth, equipmentStartHeight + equipmentTextHeight)
    win.blit(equipmentText,equipmentTextRect)
    equipmentStartWidth += equipmentTextWidth + gapBetweenText

    return equipmentStartWidth

def displayEquipment(equipment,selectItem,selectItemIndex):
    keys = list(equipment.keys())
    equipmentStartWidth = 20
    for x in range(len(keys)):
        equipmentName = ""
        key = keys[x]
        selected = False
        if x == selectItemIndex and selectItem:
            selected = True  
        if equipment[key] != "None":
            equipmentName = equipment[key].name
        equipmentStartWidth = displayEquipmentHelper(key,equipmentName=equipmentName,startWidth=equipmentStartWidth,selectItem=selected)

def displayInventory(inventory,selectItem,selectItemIndex):
    passes = 0


    gapBetweenText = 10

    text = FONT.render("Inventory",True,FONTCOLOR,black)
    textRect = text.get_rect()
    textWidth = text.get_width()
    textHeight = text.get_height()
    textRect.center = (int(textWidth/2)+15,HEIGHT + int(textHeight/2))
    win.blit(text,textRect)

    inventoryStartHeight = HEIGHT + int(textHeight/2) + 5 
    inventoryStartWidth = 0
    if len(inventory) > 0:
        for index in range(len(inventory)):
            if selectItem:
                if index == selectItemIndex:
                    inventoryText = FONT.render(f">{inventory[index].name}",True,FONTCOLOR,black)
                    inventoryTextRect = inventoryText.get_rect()
                    inventoryTextWidth = inventoryText.get_width()
                    inventoryTextHeight = inventoryText.get_height()
                    inventoryTextRect.center = (inventoryStartWidth + int(inventoryTextWidth/2)+20, inventoryStartHeight + inventoryTextHeight)
                    win.blit(inventoryText,inventoryTextRect)
                    inventoryStartWidth += inventoryTextWidth + gapBetweenText
                else:
                    inventoryText = FONT.render(f"{inventory[index].name}",True,FONTCOLOR,black)
                    inventoryTextRect = inventoryText.get_rect()
                    inventoryTextWidth = inventoryText.get_width()
                    inventoryTextHeight = inventoryText.get_height()
                    inventoryTextRect.center = (inventoryStartWidth + int(inventoryTextWidth/2)+20,inventoryStartHeight + inventoryTextHeight)
                    win.blit(inventoryText,inventoryTextRect)
                    inventoryStartWidth += inventoryTextWidth + gapBetweenText
            else:
                inventoryText = FONT.render(f"{inventory[index].name}",True,FONTCOLOR,black)
                inventoryTextRect = inventoryText.get_rect()
                inventoryTextWidth = inventoryText.get_width()
                inventoryTextHeight = inventoryText.get_height()
                inventoryTextRect.center = (inventoryStartWidth + int(inventoryTextWidth/2)+20,inventoryStartHeight + inventoryTextHeight)
                win.blit(inventoryText,inventoryTextRect)
                inventoryStartWidth += inventoryTextWidth + gapBetweenText

def displayStatistics(stats,startHeight,selectItem,selectItemIndex):
    keys = stats.keys()


    passes = 0
    
    if len(keys) > 0:
        for key in keys:
            if isinstance(stats[key], list):
                if stats[key][0] == 3: #number 3 in a list for the grid means a list of items.
                    for item in stats[key]:
                        if item == 3:
                            selectItemIndex += 1
                            text = FONT.render("Items in Room:",True,FONTCOLOR,black)
                            textRect = text.get_rect()
                            textWidth = text.get_width()
                            textRect.center = (TEXTSTARTWIDTH + int(textWidth/2), startHeight + (TEXTROWGAPDISTANCE * passes))
                            win.blit(text, textRect)
                            passes += 1
                        else:
                            text = FONT.render(f"{items.getItemName(item)}",True,FONTCOLOR,black)
                            if passes == selectItemIndex and selectItem:
                                text = FONT.render(f"> {items.getItemName(item)}",True,FONTCOLOR,black)
                            textRect = text.get_rect()
                            textWidth = text.get_width()
                            textRect.center = (TEXTSTARTWIDTH + int(textWidth/2) + 10, startHeight + (TEXTROWGAPDISTANCE * passes))
                            win.blit(text, textRect)
                            passes += 1
            else:
                text = FONT.render(f"{key}: {stats[key]}",True,FONTCOLOR,black)
                textRect = text.get_rect()
                textWidth = text.get_width()
                textRect.center = (TEXTSTARTWIDTH + int(textWidth/2), startHeight + (TEXTROWGAPDISTANCE * passes))
                win.blit(text, textRect)
                passes += 1
    return TEXTROWGAPDISTANCE * passes
win = pygame.display.set_mode((SCREENWIDTH,SCREENHEIGHT))




playerposx = 35
playerposy = 25

playervel = 1

playerDirection = 0
levelGrids = []
visibleGrids = []
roomsList = []

itemGridsList = []
NPCGridList = []
WallGridsList = []

grid = [[0 for i in range(int(WIDTH/10))] for j in range(int(HEIGHT/10))]
ItemsGrid = [[0 for i in range(int(WIDTH/10))] for j in range(int(HEIGHT/10))]
WallGrid = [[0 for i in range(int(WIDTH/10))] for j in range(int(HEIGHT/10))]
NPCGrid = [[0 for i in range(int(WIDTH/10))] for j in range(int(HEIGHT/10))]
VisibleGrid = [[0 for i in range(int(WIDTH/10))] for j in range(int(HEIGHT/10))]


def convertToItemGrid(itemsGrid,grid,rooms):
    returnValue = [[0 for i in range(int(WIDTH/10))] for j in range(int(HEIGHT/10))]
    for x in range(len(grid)):
        for y in range(len(grid[x])):
            returnValue[x][y] = [returnValue[x][y]]
    if returnValue == itemsGrid:
        print("error at itemsGrid generation, returnvalue and itemsgrid are equal")
    return returnValue

def convertToWallGrid(wallGrid,grid,rooms):
    returnValue = [[0 for i in range(int(WIDTH/10))] for j in range(int(HEIGHT/10))]
    for x in range(len(grid)):
        for y in range(len(grid[x])):
            if grid[x][y] == 2:
                wall = CreateWall((x,y),grid,rooms)
                returnValue[x][y] = wall
    if returnValue == wallGrid:
        print("Error At Wall generation, returnValue and Wallgrid are equal")
    return returnValue

def convertToNPCGrid(NPCGrid,grid,rooms):
    returnValue = [[0 for i in range(int(WIDTH/10))] for j in range(int(HEIGHT/10))]
    for x in range(len(grid)):
        for y in range(len(grid[x])):
            if grid[x][y] == 5:
                NPC = CreateNPC((x,y),grid,rooms)
                returnValue[x][y] = NPC
    if returnValue == NPCGrid:
        print("Error At Wall generation, returnValue and Wallgrid are equal")
    return returnValue

def addItem(itemsGrid,grid, position, item):
    x = position[0]
    y = position[1]

    if itemsGrid[x][y][0] != 2:
        grid[x][y] = 3

        itemsGrid[x][y][0] = 3
        itemsGrid[x][y].append(item)
def placeRandomItems(itemsGird,grid,listOfItems,NumOfitems):

    while(NumOfitems != 0):
        randX = rand.randint(0,len(grid)-1)
        randY = rand.randint(0,len(grid)-1)

        if grid[randX][randY] == 0:
            addItem(itemsGird,grid,(randX,randY),rand.choice(listOfItems))
            NumOfitems -=1

def getItemsFromGrid(itemsGrid,position):
    x = position[0]
    y = position[1]

    if itemsGrid[x][y][0] == 3:
        return itemsGrid[x][y]
    return "None"

def areItemsInTile(Id):
    if Id == 3:
        return True
    return False



def pickUpItem(player,itemGrid,position,selectItemIndex):
    x = position[0]
    y = position[1]

    if itemGrid[x][y][0] == 3:
        itemId = itemGrid[x][y].pop(selectItemIndex)
        if itemId != 3:
            player.addItemToInventory(itemId)


def CreateRooms(emptyNodes):
    rooms = {"Stone":[],"Wood":[],"Sand":[],"Gold":[]}
    for node in emptyNodes:
        randomType = rand.randint(0,8)
        match randomType:
            case 0|3|5:
                rooms["Stone"].append(node)
            case 1|4|6:
                rooms["Wood"].append(node)
            case 2:
                rooms["Gold"].append(node)
            case _:
                rooms["Sand"].append(node)
    return rooms


def getRoomType(position,rooms):
    keys = rooms.keys()

    for key in keys:
        for node in rooms[key]:
            for pos in node:
                if pos == position:
                    return key

def stepsToEmptyTile(position,grid,direction):
    steps = 0
    x = position[0]
    y = position[1]
    if direction == 0:
        if y - 1 > 0:
            if grid[x][y-1] != 0:
                steps += stepsToEmptyTile((x,y-1),grid,direction)
            return steps +1
        return steps
    if direction == 1:
        if y + 1 < len(grid[x]):
            if grid[x][y+1] != 0:
                steps += stepsToEmptyTile((x,y+1),grid,direction)     
            return steps +1
        return steps
    if direction == 2:
        if x -1 > 0:
            if grid[x-1][y] != 0:
                steps += stepsToEmptyTile((x-1,y),grid,direction)   
            return steps +1
        return steps        
    if direction == 3:
        if x + 1 < len(grid):
            if grid[x+1][y] != 0:
                steps += stepsToEmptyTile((x+1,y),grid,direction)   
            return steps +1
        return steps     
    return steps
    
def getNearestEmptyTile(position,grid):
    upSteps = stepsToEmptyTile(position,grid,0)
    downSteps = stepsToEmptyTile(position,grid,1)
    rightSteps = stepsToEmptyTile(position,grid,2)
    leftSteps = stepsToEmptyTile(position,grid,3)

    if (upSteps != 0 or downSteps !=0 or rightSteps !=0 or leftSteps !=0):
        if upSteps <= downSteps and upSteps != 0:
            if rightSteps <= leftSteps and rightSteps !=0:
                if upSteps <=rightSteps:
                    return (position[0],position[1] - upSteps)
                else:
                    return (position[0] - rightSteps,position[1])
            else:
                if upSteps <= leftSteps and leftSteps !=0:
                    return(position[0],position[1]-upSteps)
                else:
                    return (position[0] + leftSteps, position[1])
        else:
            if downSteps > 0:
                if rightSteps <= leftSteps and rightSteps !=0:
                    if downSteps <= rightSteps:
                        return(position[0],position[1] + downSteps)
                    else:
                        return(position[0] - rightSteps,position[1])
                elif leftSteps <= downSteps and leftSteps !=0:
                    return(position[0] + leftSteps,position[1])
                else:
                    return (position[0], position[1] + downSteps)
            else:
                if rightSteps <= leftSteps and rightSteps !=0:
                    return(position[0] - rightSteps,position[1])
                return(position[0] + leftSteps,position[1])
    return position

def getDirection(direction):
    if direction == 0:
        return "Left"
    elif direction ==1:
        return "Right"
    elif direction ==2:
        return "Up"
    elif direction ==3:
        return "Down"

def CreateWall(position,grid,rooms):
    roomType = getRoomType(getNearestEmptyTile(position,grid),rooms)
    newWall = None
    match roomType:
        case "Stone":
            newWall = wall.StoneWall()
        case "Wood":
            newWall = wall.WoodWall()
        case "Gold":
            newWall = wall.GoldWall()
        case _:
            newWall = wall.SandWall()
    return newWall

def CreateNPC(position,grid,rooms):
    roomType = getRoomType(getNearestEmptyTile(position,grid),rooms)
    newNPC = None
    if level < 10:
        match roomType:
            case "Stone":
                newNPC = enemies.lowerFloorEnemies[rand.randint(0,len(enemies.lowerFloorEnemies)-1)]()
            case "Wood":
                newNPC = enemies.lowerFloorEnemies[rand.randint(0,len(enemies.lowerFloorEnemies)-1)]()
            case _:
                newNPC = enemies.lowerFloorEnemies[rand.randint(0,len(enemies.lowerFloorEnemies)-1)]()
    return newNPC

def gameRunning(menuOpen,selectItem,inventoryOpen,unEquip):
    if menuOpen:
        return False
    if selectItem:
        return False
    if inventoryOpen:
        return False
    if unEquip:
        return False
    return True


def DrawMenu(selectItemIndex):
    pygame.draw.rect(win,black,pygame.Rect(MENUWIDTH-5,MENUHEIGHT+ (SCREENHEIGHT/4),255,255))
    pygame.draw.rect(win,white,pygame.Rect(MENUWIDTH,MENUHEIGHT+ (SCREENHEIGHT/4),250,250))

    keys = menuOptions.keys()

    selectItemIndex -= 1
    passes = 0
    for key in keys:
        if menuOptions[key]:
            text = FONT.render(f"{key} [x]",True,black,white)
            if passes == selectItemIndex:
                text = FONT.render(f"> {key} [x]",True,black,white)
            textRect = text.get_rect()
            textWidth = text.get_width()
            textRect.center = (MENUWIDTH + int(textWidth/2), MENUHEIGHT + (TEXTROWGAPDISTANCE * passes) + TEXTROWGAPDISTANCE + (SCREENHEIGHT/4))
            win.blit(text, textRect)
            passes += 1
        else:
            text = FONT.render(f"{key} [ ]",True,black,white)
            if passes == selectItemIndex:
                text = FONT.render(f"> {key} [ ]",True,black,white)
            textRect = text.get_rect()
            textWidth = text.get_width()
            textRect.center = (MENUWIDTH + int(textWidth/2), MENUHEIGHT + (TEXTROWGAPDISTANCE * passes) + TEXTROWGAPDISTANCE + (SCREENHEIGHT/4))
            win.blit(text, textRect)
            passes += 1

def SetGridTile(grid,position,tileIndex):
    x = position[0]
    y = position[1]

    grid[x][y] = tileIndex
def PlaceRandomEnemies(grid,amount):
    placed = 0
    placedPositions = []
    while placed < amount:
        gettingPosition = True
        placed +=1
        x = 0
        y = 0
        while gettingPosition:
            x = rand.randint(0,len(grid) -1)
            y = rand.randint(0,len(grid[0]) -1)
            if (x,y) in placedPositions:
                pass
            else:
                placedPositions.append((x,y))
                gettingPosition = False
        grid[x][y] = 5
    return placedPositions
def MoveEnemiesRandomly(grid,NPCGrid,wallGrid):
    listOfMovedEnemies = []
    listOfNewPositions = []
    for x in range(len(grid)):
        for y in range(len(grid[x])):
            if grid[x][y] == 5 and NPCGrid[x][y].move:
                NPCGrid[x][y].move = False
                listOfMovedEnemies.append(NPCGrid[x][y])
                moving = True
                newPositionAdded = False
                passes = 0
                while moving:
                    passes += 1
                    randomDirection = rand.randint(0,3)
                    if randomDirection == 0 and y -1 >= 0:
                        if grid[x][y-1] == 0:
                            grid[x][y] = 0
                            grid[x][y-1] = 5

                            NPCGrid[x][y-1]=NPCGrid[x][y]
                            NPCGrid[x][y] = 0
                            listOfNewPositions.append((x,y-1))
                            newPositionAdded = True
                            moving = False
                        elif NPCGrid[x][y].dig and grid[x][y-1] == 2:
                            wallGrid[x][y-1].hp -= NPCGrid[x][y].wallDamage
                            moving = False
                            if WallGrid[x][y-1].hp <= 0:
                                WallGrid[x][y-1] = 0
                                grid[x][y-1] = 0
                        elif grid[x][y-1] == 1:
                            player.hp -= NPCGrid[x][y].damage
                            moving = False
                            print(player.hp)
                    if randomDirection == 1 and y+1 < len(grid[x]):
                        if grid[x][y+1] == 0:
                            grid[x][y] = 0
                            grid[x][y+1] = 5

                            NPCGrid[x][y+1] = NPCGrid[x][y]
                            NPCGrid[x][y] = 0
                            listOfNewPositions.append((x,y+1))
                            newPositionAdded = True
                            moving = False
                        elif NPCGrid[x][y].dig and grid[x][y+1] == 2:
                            wallGrid[x][y+1].hp -= NPCGrid[x][y].wallDamage
                            moving = False
                            if WallGrid[x][y+1].hp <= 0:
                                WallGrid[x][y+1] = 0
                                grid[x][y+1] = 0
                        elif grid[x][y+1] == 1:
                            player.hp -= NPCGrid[x][y].damage
                            moving = False
                            print(player.hp)
                    if randomDirection == 2 and x -1 >= 0:
                        if grid[x-1][y] == 0:
                            grid[x][y] = 0
                            grid[x-1][y] = 5

                            NPCGrid[x-1][y] = NPCGrid[x][y]
                            NPCGrid[x][y] = 0
                            listOfNewPositions.append((x-1,y))
                            newPositionAdded = True
                            moving = False
                        elif NPCGrid[x][y].dig and grid[x-1][y] == 2:
                            wallGrid[x-1][y].hp -= NPCGrid[x][y].wallDamage
                            moving = False
                            if WallGrid[x -1][y].hp <= 0:
                                WallGrid[x -1][y] = 0
                                grid[x - 1][y] = 0
                        elif grid[x-1][y] == 1:
                            player.hp -= NPCGrid[x][y].damage
                            moving = False
                            print(player.hp)
                    if randomDirection == 3 and x+1 < len(grid):
                        if grid[x+1][y] == 0:
                            grid[x][y] = 0
                            grid[x+1][y] = 5

                            NPCGrid[x+1][y] = NPCGrid[x][y]
                            NPCGrid[x][y] = 0
                            listOfNewPositions.append((x+1,y))
                            newPositionAdded = True
                            moving = False
                        elif NPCGrid[x][y].dig and grid[x+1][y] == 2:
                            wallGrid[x+1][y].hp -= NPCGrid[x][y].wallDamage
                            moving = False
                            if WallGrid[x +1][y].hp <= 0:
                                WallGrid[x +1][y] = 0
                                grid[x +1][y] = 0
                        elif grid[x+1][y] == 1:
                            player.hp -= NPCGrid[x][y].damage
                            moving = False
                            print(player.hp)
                    if passes == 4:
                        moving = False
                        if newPositionAdded == False:
                            listOfNewPositions.append((x,y))
                
    for NPC in listOfMovedEnemies:
        NPC.move = True
    return listOfNewPositions

def CheckForItem(grid,itemGrid):
    for x in range(len(itemGrid)):
        for y in range(len(itemGrid[x])):
            if itemGrid[x][y][0] == 3:
                grid[x][y] = 3

def saveToTxt(txtFile):
    openMapFile = open(txtFile,'a')
    for row in levelGrids:
        for y in range(len(row)):
            if y == 0:
                openMapFile.write(f"{row[y]}")
            elif y == len(row)-1:
                openMapFile.write(f",{row[y]}\n")
            else:
                openMapFile.write(f",{row[y]}")

def saveLevel(grid,level,listOfGrids):
    
    if level < len(listOfGrids):
        listOfGrids[level] = grid
    else:
        listOfGrids.append(grid)
    
def CheckIfMovedMoreThanOne(current,last,lastDir):
    current_x = current[0]
    current_y = current[1]

    last_x = last[0]
    last_y = last[1]

    if current_x -2 == last_x or current_x +2 == last_x:
        print(f"x moved more than two lastDir: {lastDir}\nC: {current}\nL: {last}\n")

    elif current_y -2 == last_y or current_y +2 == last_y:
        print(f"y moved more than two lastDir: {lastDir}\nC: {current}\nL: {last}\n")

    return current

def RemoveDeadNPCs(listOfPositions):
    stillAlivePositions = []
    while(len(listOfPositions) > 0):
        position = listOfPositions.pop()
        x = position[0]
        y = position[1]
        if NPCGrid[x][y].hp <= 0:
            print(f"{NPCGrid[x][y].name} is dead")
            grid[x][y] = 0
            NPCGrid[x][y] = 0
        else:
            stillAlivePositions.append(position)
    return stillAlivePositions
def PlacePreviousLevelDoor(grid,position):
    x = position[0]
    y = position[1]

    grid[x][y] = 6

def getVisiblePositions(grid,playerPosition,player):
    visiblePositions = []
    x = playerPosition[0]
    y = playerPosition[1]
    radius = player.visionRange
    gettingPositions = True
    sides = 0
    while(gettingPositions):
        if(sides >= radius):
            gettingPositions = False
        startY = radius - sides
        if y - startY >= 0:
            visiblePositions.append((x,y - startY))
        if y + startY < len(grid):
            visiblePositions.append((x,y + startY))

        for index in range(sides):
            if y - startY >=0:
                if x - index >=0:
                    visiblePositions.append((x-index, y-startY))
                if x + index < len(grid):
                    visiblePositions.append((x+index,y-startY))

            if y + startY < len(grid):
                if x + index < len(grid):
                    visiblePositions.append((x+index,y+startY))
                if x - index >= 0:
                    visiblePositions.append((x-index,y+startY))
        sides +=1
    return visiblePositions

def setPositionsVisible(visibleGrid,visiblePositions):

    for x in range(len(visibleGrid[0])):
        for y in range(len(visibleGrid[1])):
            if visibleGrid[x][y] == 1:
                visibleGrid[x][y] = 2

    for position in visiblePositions:
        x = position[0]
        y = position[1]

        visibleGrid[x][y] = 1

def PlaceNextLevelDoor(grid):
    gettingRandomPosition = True
    DoorPosition = ()
    while(gettingRandomPosition):
        x = rand.randint(0,len(grid) - 1)
        y = rand.randint(0,len(grid[x]) - 1)
        if(grid[x][y] == 0 or grid[x][y] == 2):
            gettingRandomPosition = False
            DoorPosition = (x,y)
            grid[x][y] = 4
    return DoorPosition

loadMenuOptions("menuOpts.txt",menuOptions)

def LoadTxtFile(txtFile):
    print("Loaded Level")
    openMapFile = open(txtFile,'r')
    MapListFromTxt = openMapFile.readlines()
    openMapFile.close()
    for row in MapListFromTxt:
        levelGrids.append(row.split(','))

def LoadLevel(level,listOfGrids):
    print(f"Loading level {level}")
    return listOfGrids[level]
    

def GetEnemyPositions(grid):
    enemyPositions = []

    for x in range(len(grid)):
        for y in range(len(grid[x])):
            if grid[x][y] == 5:
                enemyPositions.append((x,y))
    return enemyPositions

def GenerateRandomLevel(grid):
    print("Generated Level")
    for x in range(len(grid)):
        for y in range(len(grid[x])):
            isWall = rand.randint(0,1)
            if isWall == 1:
                grid[x][y] = 2

if menuOptions["Load Room"]:
    LoadTxtFile("dungeonLevels.txt")
elif menuOptions["Generate Room"]:
    GenerateRandomLevel(grid)
else:
    wallStartx = 30
    wallstarty = 30

    grid[wallStartx][wallstarty] = 2
    grid[wallStartx][wallstarty- 2] = 2

for x in range(len(grid)):
    for y in range(len(grid[x])):
        if grid[x][y] == 1:
            playerposx = x
            playerposy = y


# First Level Creation
playerpos = (playerposx, playerposy)
emptyNodes = CER.createNodes(grid)
rooms = CreateRooms(emptyNodes)

ListOfEnemyPositions = PlaceRandomEnemies(grid,75)

ItemsGrid = convertToItemGrid(ItemsGrid,grid,rooms)
NPCGrid = convertToNPCGrid(NPCGrid,grid,rooms)
WallGrid = convertToWallGrid(WallGrid,grid,rooms)
ListOfItems = items.equipmentList

placeRandomItems(ItemsGrid,grid,ListOfItems,5)

floorRandInt:int = rand.randint(0,1)

if floorRandInt == 0:
    floorColor = swampFloor
    shadowyFloorColor = shadowySwampFloor
else:
    floorColor = floorGray
    shadowyFloorColor = shadowyfloorGray


enemyMove = False

doorPostions = []

playerTurn = True

generateNewLevel = False
generatePreviousLevel = False
generateNextLevel = False

EnemyCount = 3
menuOpen = False
selectItem = False
inventoryOpen = False
unEquip = False
selectItemIndex = 1
runing = True
NewLevelDoorNotAdded = True
while runing:
    
    grid[playerposx][playerposy] = 1

    

    roomType = getRoomType(playerpos,rooms)
    roomItems = getItemsFromGrid(ItemsGrid,playerpos)
    cardinalDirection = getDirection(playerDirection)
    currentPosition = "Floor"
    
   
    

    CharacterStatistics = {"Health":player.hp,"AC":player.ac,"Gold":player.gold,"Player Direction":cardinalDirection,"Wall Damage":player.wallDamage,"Player Min Damage":player.minDamage,"Player Max Damage":player.MaxDamage,"Player X":playerposx,"Player Y":playerposy}
    RoomStatistics = {"Room Type":roomType,"Items at Current Position":roomItems,"Level":level,"Current Position":currentPosition}
    pygame.time.delay(100)
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            saveMenuOptions("menuOpts.txt",menuOptions)
            if menuOptions["Save on Exit"]:
                saveToTxt("dungeonLevels.txt")
            runing = False
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_RETURN:
                if playerpos == doorPostions[level]:
                    if level < len(doorPostions) -1:
                        generateNextLevel = True
                    else:
                        generateNewLevel = True
                elif playerpos == doorPostions[level -1]:
                    generatePreviousLevel = True
                elif gameRunning(selectItem,menuOpen,inventoryOpen,unEquip):
                    if selectItem == False:
                        if areItemsInTile(roomItems[0]):
                            print("There are items in this room")
                            selectItem = True
                elif menuOpen:
                    keys = menuOptions.keys()
                    passes = 0
                    for key in keys:
                        if passes == selectItemIndex -1:
                            if menuOptions[key]:
                                menuOptions[key] = False
                            else:
                                menuOptions[key] = True
                        passes += 1
                elif selectItem:
                    pickUpItem(player,ItemsGrid,playerpos,selectItemIndex)
                    if len(roomItems) == 1:
                            ItemsGrid[playerposx][playerposy][0] = 0
                            selectItem = False
                            selectItemIndex = 0
                    if selectItemIndex > len(roomItems):
                        selectItemIndex -=1
                    if selectItemIndex == len(roomItems):
                        selectItemIndex -=1
                elif inventoryOpen:
                    print("Equipping ...")
                    player.equipItem(selectItemIndex)
                    if len(player.inventory) == 0:
                        inventoryOpen = False
                        selectItemIndex = 1
                elif unEquip:
                    print("Unequipping ...")
                    keys = player.equipment.keys()
                    equipmentSlot = None
                    passes = 0
                    for key in keys:
                        if passes == selectItemIndex:
                            equipmentSlot = key
                            break
                        passes +=1
                    player.unEquipItem(equipmentSlot)
            if event.key == pygame.K_ESCAPE:
                if menuOpen:
                    menuOpen = False
                    selectItemIndex = 1
                else:
                    menuOpen = True
                    selectItemIndex =1
            if event.key == pygame.K_q:
                if selectItem:
                    selectItem = False
                    selectItemIndex = 1
                if menuOpen:
                    menuOpen = False
                    selectItemIndex = 1
            if gameRunning(selectItem,menuOpen,inventoryOpen,unEquip):
                targetPos:tuple = ()
                validMove:bool = False
                if event.key == pygame.K_e:
                    if playerDirection == 0:
                        targetPos = (playerposx - 1,playerposy)
                        if playerposx - 1 >= 0:
                            validMove = True       
                    elif playerDirection == 1:
                        targetPos = (playerposx + 1,playerposy)
                        if playerposx + 1 < int(WIDTH/10):
                            validMove = True
                    elif playerDirection == 2:
                        targetPos = (playerposx,playerposy - 1)
                        if playerposy - 1 >= 0:
                            validMove = True
                    elif playerDirection == 3:
                        targetPos = (playerposx,playerposy + 1)
                        if playerposy + 1 < int(HEIGHT/10):
                            validMove = True

                    if validMove:
                            if grid[targetPos[0]][targetPos[1]] == 2: #if that spot is a wall
                                if WallGrid[targetPos[0]][targetPos[1]].hp > 0:
                                    WallGrid[targetPos[0]][targetPos[1]].hp -= player.wallDamage
                                    print("You damaged the wall")
                                    enemyMove = True
                                if WallGrid[targetPos[0]][targetPos[1]].hp <= 0:
                                    if WallGrid[targetPos[0]][targetPos[1]].name == "Gold Wall":
                                        player.alterGold(1)
                                    WallGrid[targetPos[0]][targetPos[1]] = 0
                                    grid[targetPos[0]][targetPos[1]] = 0
                            elif grid[targetPos[0]][targetPos[1]] == 5: #if that spot is an enemy
                                damage = player.DealDamage()
                                print(f"I dealt {damage} damage")
                                NPCGrid[targetPos[0]][targetPos[1]].hp -= damage
                                enemyMove = True

            if event.key == pygame.K_i:
                if gameRunning(selectItem,menuOpen,inventoryOpen,unEquip) and len(player.inventory) > 0:
                    inventoryOpen = True
                    selectItemIndex = 0
                elif inventoryOpen:
                    inventoryOpen = False
                    selectItemIndex = 1

            if event.key == pygame.K_u:
                if gameRunning(selectItem,menuOpen,inventoryOpen,unEquip):
                    unEquip = True
                    selectItemIndex = 0
                elif unEquip:
                    unEquip = False
                    selectItemIndex = 1

            moveMade:bool = False
            targetLocation = None
            xvelocity = 0
            yvelocity = 0
            indexMove = 0
            match event.key:
                case pygame.K_LEFT | pygame.K_a:
                    playerDirection = 0
                    if playerposx -1 >= 0:
                        moveMade = True
                        targetLocation = grid[playerposx-playervel][playerposy]
                        xvelocity -= playervel
                case pygame.K_RIGHT | pygame.K_d:
                    playerDirection = 1
                    if playerposx + 1 < int(WIDTH/10):
                        moveMade = True
                        targetLocation = grid[playerposx + playervel][playerposy]
                        xvelocity += playervel
                case pygame.K_UP | pygame.K_w:
                    playerDirection = 2
                    indexMove -= 1
                    if playerposy - 1 >= 0:
                        moveMade = True
                        targetLocation = grid[playerposx][playerposy- playervel]
                        yvelocity -= playervel
                case pygame.K_DOWN | pygame.K_s:
                    playerDirection = 3
                    indexMove += 1
                    if playerposy + 1 < int(HEIGHT/10):
                        moveMade = True
                        targetLocation = grid[playerposx][playerposy+ playervel]
                        yvelocity += playervel
            if moveMade:
                if gameRunning(selectItem,menuOpen,inventoryOpen,unEquip):
                    if targetLocation != 2 and targetLocation != 5:
                        grid[playerposx][playerposy] = 0
                        playerposy += yvelocity
                        playerposx += xvelocity
                        enemyMove = True
                        CheckForItem(grid,ItemsGrid)
                else:
                    if selectItem:
                        if selectItemIndex + indexMove < len(roomItems) and selectItemIndex + indexMove > 0:
                            selectItemIndex +=indexMove
                    elif menuOpen:
                        if selectItemIndex +indexMove <= len(menuOptions.keys()) and selectItemIndex + indexMove >= 0:
                            selectItemIndex +=indexMove
                    elif inventoryOpen:
                        if selectItemIndex +indexMove < len(player.inventory) and selectItemIndex + indexMove >= 0:
                            selectItemIndex +=indexMove
                    elif unEquip:
                        if selectItemIndex +indexMove < len(player.equipment.keys()) and selectItemIndex + indexMove >=0:
                            selectItemIndex +=indexMove
            
            

    playerpos = (playerposx,playerposy)
    grid[playerposx][playerposy] = 1
    if enemyMove:
        ListOfEnemyPositions = MoveEnemiesRandomly(grid,NPCGrid,WallGrid)
        enemyMove = False
    
    win.fill((black))

    ListOfEnemyPositions = RemoveDeadNPCs(ListOfEnemyPositions)

    if NewLevelDoorNotAdded:
        NewLevelDoorNotAdded = False
        doorPostions.append(PlaceNextLevelDoor(grid))

    currentDoor_x = doorPostions[level][0]
    currentDoor_y =  doorPostions[level][1]
    if level > 0:
        previousDoor_x = doorPostions[level -1][0]
        previousDoor_y = doorPostions[level -1][1]

    match playerpos:
        case (currentDoor_x,currentDoor_y):
            currentPosition = "Door to Next Level"
        case (previousDoor_x,previousDoor_y):
            currentPosition = "Door to previous Level"
        case _:
            currentPosition = "Floor"
    
    if len(doorPostions) > 0:
        currentDoor_x = doorPostions[level][0]
        currentDoor_y =  doorPostions[level][1]
        if grid[currentDoor_x][currentDoor_y] != 1:
            grid[currentDoor_x][currentDoor_y] = 4
        if level > 0:
            previousDoor_x = doorPostions[level -1][0]
            previousDoor_y = doorPostions[level -1][1]
            if grid[previousDoor_x][previousDoor_y] !=1:
                grid[previousDoor_x][previousDoor_y] = 6

    if generateNextLevel:

        floorRandInt:int = rand.randint(0,1)

        if floorRandInt == 0:
            floorColor = swampFloor
            shadowyFloorColor = shadowySwampFloor
        else:
            floorColor = floorGray
            shadowyFloorColor = shadowyfloorGray

        print("Generating Next Level")
        saveLevel(grid,level,levelGrids)
        saveLevel(VisibleGrid,level,visibleGrids)
        saveLevel(ItemsGrid,level,itemGridsList)
        saveLevel(NPCGrid,level,NPCGridList)
        saveLevel(WallGrid,level,WallGridsList)

        level = level + 1
        VisibleGrid = LoadLevel(level,visibleGrids)
        grid = LoadLevel(level,levelGrids)
        ItemsGrid = LoadLevel(level,itemGridsList)
        NPCGrid = LoadLevel(level,NPCGridList)
        WallGrid = LoadLevel(level, WallGridsList)
        

        ListOfEnemyPositions = GetEnemyPositions(grid)

        generateNextLevel = False
    if generatePreviousLevel and level -1 >=0:

        print("Generating Previous Level")
        saveLevel(grid,level,levelGrids)
        saveLevel(VisibleGrid,level,visibleGrids)
        saveLevel(ItemsGrid,level,itemGridsList)
        saveLevel(NPCGrid,level,NPCGridList)
        saveLevel(WallGrid,level,WallGridsList)

        level = level - 1

        VisibleGrid = LoadLevel(level,visibleGrids)
        grid = LoadLevel(level,levelGrids)
        ItemsGrid = LoadLevel(level,itemGridsList)
        NPCGrid = LoadLevel(level,NPCGridList)
        WallGrid = LoadLevel(level, WallGridsList)


        

        ListOfEnemyPositions = GetEnemyPositions(grid)


        generatePreviousLevel = False
    if generateNewLevel:
        print("Generating New Level")
        saveLevel(grid,level,levelGrids)
        saveLevel(VisibleGrid,level,visibleGrids)
        saveLevel(ItemsGrid,level,itemGridsList)
        saveLevel(NPCGrid,level,NPCGridList)
        saveLevel(WallGrid,level,WallGridsList)

        roomsList.append(rooms)

        VisibleGrid = [[0 for i in range(int(WIDTH/10))] for j in range(int(HEIGHT/10))]
        grid = [[0 for i in range(int(WIDTH/10))] for j in range(int(HEIGHT/10))]
        
        GenerateRandomLevel(grid)

        level +=1
        
        emptyNodes = CER.createNodes(grid)
        rooms = CreateRooms(emptyNodes)
        roomsList.append(rooms)
        ListOfEnemyPositions = PlaceRandomEnemies(grid,EnemyCount*level)

        ItemsGrid = convertToItemGrid(ItemsGrid,grid,rooms)
        NPCGrid = convertToNPCGrid(NPCGrid,grid,rooms)
        WallGrid = convertToWallGrid(WallGrid,grid,rooms)
        placeRandomItems(ItemsGrid,grid,ListOfItems,5)


        for x in range(len(WallGridsList)):
            if x == level:
                pass
            else:
                if WallGridsList[x] == WallGrid:
                    print(f"Error Wall Grid equals index {x} in wall grid list")
        PlacePreviousLevelDoor(grid,doorPostions[-1])

        NewLevelDoorNotAdded = True
        generateNewLevel = False

    TextHeightIncrement = displayStatistics(CharacterStatistics,TEXTSTARTHEIGHT +35,selectItem,selectItemIndex)
    TextHeightIncrement += displayStatistics(RoomStatistics,TEXTSTARTHEIGHT + TextHeightIncrement +35,selectItem,selectItemIndex)
    displayInventory(player.inventory,inventoryOpen,selectItemIndex)
    displayEquipment(player.equipment,unEquip,selectItemIndex)

    visiblePositions = getVisiblePositions(grid,playerpos,player)
    setPositionsVisible(VisibleGrid,visiblePositions)

    for x in range(len(grid)):
        for y in range(len(grid[x])):
            if VisibleGrid[x][y] == 1:
                match grid[x][y]:
                    case 0: #Empty space
                        pygame.draw.rect(win,floorColor,pygame.Rect(x*10,y*10,10,10))
                    case 1: #Player
                        pygame.draw.rect(win,green,pygame.Rect(x*10,y*10,10,10))
                    case 2: #Wall
                        w = WallGrid[x][y]
                        match w.name:
                            case "Stone Wall":
                                pygame.draw.rect(win,gray,pygame.Rect(x*10,y*10,10,10))
                            case "Wood Wall":
                                pygame.draw.rect(win,woodBrown,pygame.Rect(x*10,y*10,10,10))
                            case "Sand Wall":
                                pygame.draw.rect(win,tan,pygame.Rect(x*10,y*10,10,10))
                            case "Gold Wall":
                                pygame.draw.rect(win,gold,pygame.Rect(x*10,y*10,10,10))
                            case _:
                                pygame.draw.rect(win,blue,pygame.Rect(x*10,y*10,10,10))
                    case 3: #Chest
                        pygame.draw.rect(win,purple,pygame.Rect(x*10,y*10,10,10))
                    case 4: #NextDoor
                        pygame.draw.rect(win,blue,pygame.Rect(x*10,y*10,10,10))
                    case 5:#Enemy
                        match NPCGrid[x][y].name:
                            case "Goblin":
                                pygame.draw.rect(win,red,pygame.Rect(x*10,y*10,10,10))
                            case "Goblin Chieftan":
                                pygame.draw.rect(win,crimson,pygame.Rect(x*10,y*10,10,10))
                            case "Dire Rat":
                                pygame.draw.rect(win,ratBrown,pygame.Rect(x*10,y*10,10,10))
                    case 6: #PreviousDoor
                        pygame.draw.rect(win,blue,pygame.Rect(x*10,y*10,10,10))
            elif VisibleGrid[x][y] == 2:
                match grid[x][y]:
                    case 2: #wall
                        w = WallGrid[x][y]
                        match w.name:
                            case "Stone Wall":
                                pygame.draw.rect(win,shadowyGray,pygame.Rect(x*10,y*10,10,10))
                            case "Wood Wall":
                                pygame.draw.rect(win,shadowywoodBrown,pygame.Rect(x*10,y*10,10,10))
                            case "Sand Wall":
                                pygame.draw.rect(win,shadowyTan,pygame.Rect(x*10,y*10,10,10))
                            case "Gold Wall":
                                pygame.draw.rect(win,shadowyGold,pygame.Rect(x*10,y*10,10,10))
                            case _:
                                pygame.draw.rect(win,blue,pygame.Rect(x*10,y*10,10,10))
                    case 3: #Chest
                        pygame.draw.rect(win,shadowyPurple,pygame.Rect(x*10,y*10,10,10))
                    case 4: #NextDoor
                        pygame.draw.rect(win,blue,pygame.Rect(x*10,y*10,10,10))
                    case 6: #PreviousDoor
                        pygame.draw.rect(win,blue,pygame.Rect(x*10,y*10,10,10))
                    case _: #floor
                        pygame.draw.rect(win,shadowyFloorColor,pygame.Rect(x*10,y*10,10,10))

    if menuOpen:
        DrawMenu(selectItemIndex)

    pygame.display.flip()


    pygame.display.update()
