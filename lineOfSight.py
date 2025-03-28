
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

player = pc.PlayerClass()

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

def displayEquipment(equipment,selectItem,selectItemIndex):
    keys = equipment.keys()
    
    gapBetweenText = 10
    
    text = FONT.render("Equipment",True,blue,black)
    textRect = text.get_rect()
    textWidth = text.get_width()
    textHeight = text.get_height()
    textRect.center = (int(textWidth/2),HEIGHT + textHeight*3 +5)
    win.blit(text,textRect)

    equipmentStartHeight = HEIGHT + textHeight*3 +5
    equipmentStartWidth = 0

    for key in keys:
        equipmentName = ""
        if selectItem:
            pass
        else:
            if equipment[key] != "None":
                equipment = equipment[key].name
            equipmentText = FONT.render(f"{key}:[{equipmentName}]",True,blue,black)
            equipmentTextRect = equipmentText.get_rect()
            equipmentTextWidth = equipmentText.get_width()
            equipmentTextHeight = equipmentText.get_height()
            equipmentTextRect.center = (int(equipmentTextWidth/2) + equipmentStartWidth, equipmentStartHeight + equipmentTextHeight)
            win.blit(equipmentText,equipmentTextRect)
            equipmentStartWidth += equipmentTextWidth + gapBetweenText

def displayInventory(inventory,selectItem,selectItemIndex):
    passes = 0

    gapBetweenText = 10

    text = FONT.render("Inventory",True,blue,black)
    textRect = text.get_rect()
    textWidth = text.get_width()
    textHeight = text.get_height()
    textRect.center = (int(textWidth/2),HEIGHT + int(textHeight/2)+5)
    win.blit(text,textRect)

    inventoryStartHeight = HEIGHT + int(textHeight/2) + 5 
    inventoryStartWidth = 0
    if len(inventory) > 0:
        for index in range(len(inventory)):
            if selectItem:
                if index == selectItemIndex:
                    inventoryText = FONT.render(f">{inventory[index].name}",True,blue,black)
                    inventoryTextRect = inventoryText.get_rect()
                    inventoryTextWidth = inventoryText.get_width()
                    inventoryTextHeight = inventoryText.get_height()
                    inventoryTextRect.center = (inventoryStartWidth + int(inventoryTextWidth/2), inventoryStartHeight + inventoryTextHeight )
                    win.blit(inventoryText,inventoryTextRect)
                    inventoryStartWidth += inventoryTextWidth + gapBetweenText
                else:
                    inventoryText = FONT.render(f"{inventory[index].name}",True,blue,black)
                    inventoryTextRect = inventoryText.get_rect()
                    inventoryTextWidth = inventoryText.get_width()
                    inventoryTextHeight = inventoryText.get_height()
                    inventoryTextRect.center = (inventoryStartWidth + int(inventoryTextWidth/2),inventoryStartHeight + inventoryTextHeight )
                    win.blit(inventoryText,inventoryTextRect)
                    inventoryStartWidth += inventoryTextWidth + gapBetweenText
            else:
                inventoryText = FONT.render(f"{inventory[index].name}",True,blue,black)
                inventoryTextRect = inventoryText.get_rect()
                inventoryTextWidth = inventoryText.get_width()
                inventoryTextHeight = inventoryText.get_height()
                inventoryTextRect.center = (inventoryStartWidth + int(inventoryTextWidth/2),inventoryStartHeight + inventoryTextHeight )
                win.blit(inventoryText,inventoryTextRect)
                inventoryStartWidth += inventoryTextWidth + gapBetweenText

def displayStatistics(stats,startHeight,selectItem,selectItemIndex):
    keys = stats.keys()

    
    selectItemIndex += 1
    passes = 0
    
    if len(keys) > 0:
        for key in keys:
            if isinstance(stats[key], list):
                if stats[key][0] == 3: #number 3 in a list for the grid means a list of items.
                    for item in stats[key]:
                        if item == 3:
                            text = FONT.render("Items in Room:",True,blue,black)
                            textRect = text.get_rect()
                            textWidth = text.get_width()
                            textRect.center = (TEXTSTARTWIDTH + int(textWidth/2), startHeight + (TEXTROWGAPDISTANCE * passes))
                            win.blit(text, textRect)
                            passes += 1
                        else:
                            text = FONT.render(f"{items.getItemName(item)}",True,blue,black)
                            if passes == selectItemIndex and selectItem:
                                text = FONT.render(f"> {items.getItemName(item)}",True,blue,black)
                            textRect = text.get_rect()
                            textWidth = text.get_width()
                            textRect.center = (TEXTSTARTWIDTH + int(textWidth/2) + 10, startHeight + (TEXTROWGAPDISTANCE * passes))
                            win.blit(text, textRect)
                            passes += 1
            else:
                text = FONT.render(f"{key}: {stats[key]}",True,blue,black)
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


def convertToItemGrid(itemsGrid):
    for x in range(len(itemsGrid)):
        for y in range(len(itemsGrid[x])):
            itemsGrid[x][y] = [itemsGrid[x][y]]

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
        player.addItemToInventory(itemId)


def CreateRooms(emptyNodes):
    rooms = {"Stone":[],"Wood":[],"Sand":[]}
    for node in emptyNodes:
        randomType = rand.randint(0,2)
        if randomType == 0:
            rooms["Stone"].append(node)
        elif randomType == 1:
            rooms["Wood"].append(node)
        else:
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
    if roomType == "Stone":
        newWall = wall.StoneWall()
    elif roomType == "Wood":
        newWall = wall.WoodWall()
    else:
        newWall = wall.SandWall()
    return newWall

def CreateNPC(position,grid,rooms):
    roomType = getRoomType(getNearestEmptyTile(position,grid),rooms)
    newNPC = None
    if roomType == "Stone":
        newNPC = enemies.Goblin()
    elif roomType == "Wood":
        newNPC = enemies.Goblin()
    else:
        newNPC = enemies.Goblin()
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
    pygame.draw.rect(win,black,pygame.Rect(MENUWIDTH-5,MENUHEIGHT,255,505))
    pygame.draw.rect(win,white,pygame.Rect(MENUWIDTH,MENUHEIGHT,250,500))

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
            textRect.center = (MENUWIDTH + int(textWidth/2), MENUHEIGHT + (TEXTROWGAPDISTANCE * passes) + TEXTROWGAPDISTANCE)
            win.blit(text, textRect)
            passes += 1
        else:
            text = FONT.render(f"{key} [ ]",True,black,white)
            if passes == selectItemIndex:
                text = FONT.render(f"> {key} [ ]",True,black,white)
            textRect = text.get_rect()
            textWidth = text.get_width()
            textRect.center = (MENUWIDTH + int(textWidth/2), MENUHEIGHT + (TEXTROWGAPDISTANCE * passes) + TEXTROWGAPDISTANCE)
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


playerpos = (playerposx, playerposy)
emptyNodes = CER.createNodes(grid)
rooms = CreateRooms(emptyNodes)


ListOfEnemyPositions = PlaceRandomEnemies(grid,75)

convertToItemGrid(ItemsGrid)
NPCGrid = convertToNPCGrid(NPCGrid,grid,rooms)
WallGrid = convertToWallGrid(WallGrid,grid,rooms)

addItem(ItemsGrid,grid,playerpos,items.sword)
addItem(ItemsGrid,grid,playerpos,items.sword)


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
    if selectItem:
        if len(roomItems) == 1:
                ItemsGrid[playerposx][playerposy][0] = 0
                selectItem = False
                selectItemIndex = 1
        if selectItemIndex > len(roomItems):
            selectItemIndex -=2
        if selectItemIndex == len(roomItems):
            selectItemIndex -=1

    CharacterStatistics = {"Health":player.hp,"AC":player.ac,"Player Direction":cardinalDirection,"Wall Damage":player.wallDamage,"Player X":playerposx,"Player Y":playerposy}
    RoomStatistics = {"Room Type":roomType, "Items in Room":roomItems,"Level":level}
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
                elif selectItem == False and menuOpen == False:
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
                if event.key == pygame.K_e:
                    if playerDirection == 0:
                        if playerposx - 1 >= 0:
                            if grid[playerposx - 1][playerposy] == 2:
                                if WallGrid[playerposx -1][playerposy].hp > 0:
                                    WallGrid[playerposx -1][playerposy].hp -= player.wallDamage
                                    print("You damaged the wall")
                                    enemyMove = True
                                if WallGrid[playerposx -1][playerposy].hp <= 0:
                                    WallGrid[playerposx -1][playerposy] = 0
                                    grid[playerposx - 1][playerposy] = 0
                            elif grid[playerposx-1][playerposy] == 5:
                                damage = player.DealDamage()
                                print(f"I dealt {damage} damage")
                                NPCGrid[playerposx -1][playerposy].hp -= damage
                                enemyMove = True
                                
                    elif playerDirection == 1:
                        if playerposx + 1 < int(WIDTH/10):
                            if grid[playerposx + 1][playerposy] == 2:
                                if WallGrid[playerposx + 1][playerposy].hp > 0:
                                    WallGrid[playerposx + 1][playerposy].hp -= player.wallDamage
                                    print("You damaged the wall")
                                    enemyMove = True
                                if WallGrid[playerposx + 1][playerposy].hp <= 0:
                                    print((playerposx +1,playerposy))
                                    WallGrid[playerposx + 1][playerposy] = 0
                                    grid[playerposx + 1][playerposy] = 0
                            elif grid[playerposx+1][playerposy] == 5:
                                damage = player.DealDamage()
                                print(f"I dealt {damage} damage")
                                NPCGrid[playerposx+1][playerposy].hp -= damage
                                enemyMove = True
                    elif playerDirection == 2:
                        if playerposy - 1 >= 0:
                            if grid[playerposx][playerposy - 1] == 2:
                                if WallGrid[playerposx][playerposy -1].hp > 0:
                                    WallGrid[playerposx][playerposy -1].hp -= player.wallDamage
                                    print("You damaged the wall")
                                    enemyMove = True
                                if WallGrid[playerposx][playerposy -1].hp <= 0:
                                    print((playerposx,playerposy-1))
                                    WallGrid[playerposx][playerposy -1] = 0
                                    grid[playerposx][playerposy - 1] = 0
                            elif grid[playerposx][playerposy-1] == 5:
                                damage = player.DealDamage()
                                print(f"I dealt {damage} damage")
                                NPCGrid[playerposx][playerposy-1].hp -= damage
                                enemyMove = True
                    elif playerDirection == 3:
                        if playerposy + 1 < int(HEIGHT/10):
                            if grid[playerposx][playerposy + 1] == 2:
                                if WallGrid[playerposx][playerposy + 1].hp > 0:
                                    WallGrid[playerposx][playerposy + 1].hp -= player.wallDamage
                                    print("You damaged the wall")
                                    enemyMove = True
                                if WallGrid[playerposx][playerposy + 1].hp <= 0:
                                    print((playerposx,playerposy+1))
                                    WallGrid[playerposx][playerposy + 1] = 0
                                    grid[playerposx][playerposy + 1] = 0
                            elif grid[playerposx][playerposy+1] == 5:
                                damage = player.DealDamage()
                                print(f"I dealt {damage} damage")
                                NPCGrid[playerposx][playerposy+1].hp -= damage
                                enemyMove = True

            if event.key == pygame.K_i:
                if gameRunning(selectItem,menuOpen,inventoryOpen,unEquip):
                    inventoryOpen = True
                    selectItemIndex = 0
                elif inventoryOpen:
                    inventoryOpen = False
                    selectItemIndex = 0

            if event.key == pygame.K_u:
                if gameRunning(selectItem,menuOpen,inventoryOpen,unEquip):
                    unEquip = True
                    selectItemIndex = 0
                elif unEquip:
                    unEquip = False
                    selectItemIndex = 0

            if event.key == pygame.K_LEFT:
                if gameRunning(selectItem,menuOpen,inventoryOpen,unEquip):
                    playerDirection = 0
                    if playerposx - 1 >= 0:
                        if grid[playerposx - playervel][playerposy] != 2 and grid[playerposx - playervel][playerposy] != 5:
                            grid[playerposx][playerposy] = 0
                            playerposx -= playervel
                            enemyMove = True
                            CheckForItem(grid,ItemsGrid)
            if event.key == pygame.K_RIGHT:
                if gameRunning(selectItem,menuOpen,inventoryOpen,unEquip):
                    playerDirection = 1
                    if playerposx + 1 < int(WIDTH/10):
                        if grid[playerposx + playervel][playerposy] != 2 and grid[playerposx + playervel][playerposy] != 5:
                            grid[playerposx][playerposy] = 0
                            playerposx += playervel
                            enemyMove = True
                            CheckForItem(grid,ItemsGrid)
                            
            if event.key == pygame.K_UP:
                if gameRunning(selectItem,menuOpen,inventoryOpen,unEquip):
                    playerDirection = 2
                    if playerposy - 1 >= 0:
                        if grid[playerposx][playerposy- playervel] != 2 and grid[playerposx][playerposy- playervel] != 5:
                            grid[playerposx][playerposy] = 0
                            playerposy -= playervel
                            enemyMove = True
                            CheckForItem(grid,ItemsGrid)        
                else:
                    if selectItem:
                        if selectItemIndex - 1 > 0:
                            selectItemIndex -=1
                    elif menuOpen:
                        if selectItemIndex - 1 > 0:
                            selectItemIndex -= 1
                    elif inventoryOpen:
                        if selectItemIndex -1 >=0:
                            selectItemIndex -=1
                            print(selectItemIndex)
            if event.key == pygame.K_DOWN:
                if gameRunning(selectItem,menuOpen,inventoryOpen,unEquip):
                    playerDirection = 3
                    if playerposy + 1 < int(HEIGHT/10):
                        if grid[playerposx][playerposy+ playervel] != 2 and grid[playerposx][playerposy+ playervel] != 5:
                            grid[playerposx][playerposy] = 0
                            playerposy += playervel
                            enemyMove = True
                            CheckForItem(grid,ItemsGrid)
                            
                else:
                    if selectItem:
                        if selectItemIndex + 1 < len(roomItems):
                            selectItemIndex +=1
                    elif menuOpen:
                        if selectItemIndex +1 <= len(menuOptions.keys()):
                            selectItemIndex +=1
                    elif inventoryOpen:
                        if selectItemIndex +1 < len(player.inventory):
                            selectItemIndex +=1
                            print(selectItemIndex)

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

        convertToItemGrid(ItemsGrid)
        NPCGrid = convertToNPCGrid(NPCGrid,grid,rooms)
        WallGrid = convertToWallGrid(WallGrid,grid,rooms)



        for x in range(len(WallGridsList)):
            if x == level:
                pass
            else:
                if WallGridsList[x] == WallGrid:
                    print(f"Error Wall Grid equals index {x} in wall grid list")
        PlacePreviousLevelDoor(grid,doorPostions[-1])

        NewLevelDoorNotAdded = True
        generateNewLevel = False

    TextHeightIncrement = displayStatistics(CharacterStatistics,TEXTSTARTHEIGHT,selectItem,selectItemIndex)
    TextHeightIncrement += displayStatistics(RoomStatistics,TEXTSTARTHEIGHT + TextHeightIncrement,selectItem,selectItemIndex)
    TextHeightIncrement += displayStatistics(player.equipment,TEXTSTARTHEIGHT + TextHeightIncrement,selectItem,selectItemIndex)
    displayInventory(player.inventory,inventoryOpen,selectItemIndex)
    displayEquipment(player.equipment,unEquip,selectItemIndex)

    visiblePositions = getVisiblePositions(grid,playerpos,player)
    setPositionsVisible(VisibleGrid,visiblePositions)

    for x in range(len(grid)):
        for y in range(len(grid[x])):
            if VisibleGrid[x][y] == 1:
                if grid[x][y] == 0:
                    VisibleGrid[x][y] = 0
                if grid[x][y] == 2:
                    pygame.draw.rect(win,blue,pygame.Rect(x*10,y*10,10,10))
                if grid[x][y] == 1:
                    pygame.draw.rect(win,green,pygame.Rect(x*10,y*10,10,10))
                if grid[x][y] == 3:
                    pygame.draw.rect(win,purple,pygame.Rect(x*10,y*10,10,10))
                if grid[x][y] == 4:
                    pygame.draw.rect(win,brown,pygame.Rect(x*10,y*10,10,10))
                if grid[x][y] == 6:
                    pygame.draw.rect(win,brown,pygame.Rect(x*10,y*10,10,10))
                if grid[x][y] ==5:
                    VisibleGrid[x][y] = 0
                    pygame.draw.rect(win,red,pygame.Rect(x*10,y*10,10,10))
    if menuOpen:
        DrawMenu(selectItemIndex)
    
    pygame.display.flip()


    pygame.display.update()
