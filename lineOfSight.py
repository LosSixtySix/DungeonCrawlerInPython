import pygame
import pygame.ftfont
import random as rand
import connectingEmptyRooms as CER
import playerClass as pc
import items
import enemies
import wall
from spritesheet import spriteSheet as SS
import copy
import math
import numpy


"""
The Grid is a 2x2 grid that has been flattened into a dictionary of unique points of the grid. each point representing a location on a 2x2 grid,
see the drawing method to see the translation from point in the dictionary to point on a 2x2 grid. 

Further each entry in the Grid, dictionary, is a list that contains at least two integers like this [int, int] which is a representation of [what is there, visibility]
What is there:
0 -> nothing [0,int]
1 -> player [1,int]
2 -> wall [2,int,wall]
3 -> chest/items [3,int,[item*]]
4 -> next door [4,int]
5 -> enemy [5,int,enemy]
6 -> previous door [6,int]

visibility:
0 -> not visible
1 -> in vision range
2 -> memorized (if something new enters a memorized position it will not show up)

If there is a wall position there will also be a third entry in the list at the dictionary entry like so [2,int,wall].
This is also true of enemies, and items like the following: enemies -> [5,int,enemy] chest/items -> [3,int,[item*]]


Hot Keys:
 i = inventory
 u = unequip item
 l = level up
 q = quit
 e = interact/attack/break walls
 enter = interact with anything that the player is standing ontop of

NOTES:
    Perhaps depending on how a node type, higher the wall hardness, the more likely for the wall to have something valuable inside of it or behind it.
    Could also have walls that have a chance on break to drop items/resources. Item/Resource value or quality could be based on wall/node type and hardness of the
    wall.

    Would like to add a merchant node, this node could have a square room that has a merchant in the middle who sells random items/resources. Might have different kind
    of merchants depending on the floor type.
 
"""


pygame.init()
pygame.font.init()
pygame.ftfont.init()
win = pygame.display.set_mode((0,0))


fog = [15,4,7]
white = [255, 255, 255] 
green = [0, 255, 0] 
blue = [0, 0, 128] 
black = [0, 0, 0]
red = [255,0,0]
purple = [128, 0, 128]
brown = [88,57,39]
gray = [98,98,98]
tan = [253,217,181]
woodBrown = [96,59,42]
floorGray = [65,65,65]
gold = [239,191,4]
swampFloor = [108,148,108]

crimson = [75,0,0]
ratBrown = [86,75,73]

shadowyGray = [108,108,108]
shadowyTan = [193,154,121]
shadowywoodBrown = [56,19,2]
shadowyPurple = [88,0,88]
shadowyGold = [133,106,2]
shadowySwampFloor = [88,108,88]

woodRoomFloor = [139,90,43]
shadowyWoodFloor = [108,50,13]
stoneRoomFloor = [136,140,141]
shadowyfloorGray = [106,100,111]
goldRoomFloor = [164,125,171]
sandRoomFloor = [97,51,47]

colorDict = {"fog":fog,"white":white,"green":green,"blue":blue,"red":red,"purple":purple,"brown":brown,
             "gray":gray,"tan":tan,"woodBrown":woodBrown,"floorGray":floorGray,"gold":gold,"swampFloor":swampFloor,
             "crimson":crimson,"ratBrown":ratBrown,"sGray":shadowyGray,"sTan":shadowyTan,"sPurple":shadowyPurple,
             "sGold":shadowyGold,"sSwampFloor":shadowySwampFloor,"WoodRoomFloor":woodRoomFloor,"sWoodFloor":shadowyWoodFloor,
             "stoneRoomFloor":stoneRoomFloor,"sFloorGray":shadowyfloorGray,"goldRoomFloor":goldRoomFloor,"sandRoomFloor":sandRoomFloor}


SCREENWIDTH, SCREENHEIGHT = win.get_size()


TEXTSTARTWIDTH = 10
TEXTSTARTHEIGHT = 15

TEXTROWGAPDISTANCE = 20

LEFTPANELWIDTH = 250
LEFTPANELHEIGHT = SCREENHEIGHT

RIGHTPANELWIDTH = 250
RIGHTPANELHEIHGT = SCREENHEIGHT

BOTTOMPANELWIDTH = SCREENWIDTH - LEFTPANELWIDTH - RIGHTPANELWIDTH
BOTTOMPANELHEIGHT = 250

WIDTH = SCREENWIDTH - LEFTPANELWIDTH - RIGHTPANELWIDTH
HEIGHT = SCREENHEIGHT - BOTTOMPANELHEIGHT

s = SS("menuBackground.png")
menuBackground = s.get_sprite(0,0,200,250)
canvas = pygame.Surface((SCREENWIDTH,SCREENHEIGHT),pygame.SRCALPHA)

gameWindow = pygame.Surface((WIDTH,HEIGHT))
leftPanel = pygame.Surface((LEFTPANELWIDTH,LEFTPANELHEIGHT))
rightPanel = pygame.Surface((RIGHTPANELWIDTH,RIGHTPANELHEIHGT))
bottomPanel = pygame.Surface((BOTTOMPANELWIDTH,BOTTOMPANELHEIGHT))

enemyOccupiedItemSpaces = {}

# gameWindow.fill(white)


# s2 = SS("spriteSheet.png")
# sandFloorSprite = s2.get_sprite(0,0,10,10)
# woodFloorSprite = s2.get_sprite(9,0,10,10)
# goldFloorSprite = s2.get_sprite(19,0,10,10)
# stoneFloorSpite = s2.get_sprite(29,0,10,10)

def setTileSize() -> int:
    gettingValue:bool = True

    startingSize = 10
    
    while gettingValue:
        if WIDTH%startingSize == 0 and HEIGHT%startingSize == 0:
            return startingSize
        startingSize = startingSize + 1

tileSize = setTileSize()
ROWLENGHTH = int(WIDTH/tileSize)
COLUMNLENGTH = int(HEIGHT/tileSize)

numberOfSpots = int(WIDTH/tileSize) * int(HEIGHT/tileSize)

loadRoom = True
generateRoom = False
saveMap = False

menuOptions = {"Load Room":True,"Generate Room":True, "Save on Exit":True}

level = 0

FONTCOLOR = (196,137,18)

player:pc.PlayerClass = pc.PlayerClass()
# player.addItemToInventory(items.WarPick)
# player.addItemToInventory(items.BurrowersAmulet)
player.addItemToInventory(items.HealingPotion)
FONT = pygame.ftfont.Font('Forgore.otf',25)

playerposx = int((WIDTH/tileSize)/2)
playerposy = int((HEIGHT/tileSize)/2)

playerPosition = playerposx + (playerposy * ROWLENGHTH)

playerDirection = 0
levelGrids = []
visibleGrids = []
roomsList = []

def sameColumn(i,j,rowLength):
    if i%rowLength == j % rowLength:
        return True
    return False

def sameRow(i,j,rowLength):
    if int(i/rowLength) == int(j/rowLength):
        return True
    return False

def drawPlayer(playerDirection) -> pygame.Surface:
    canvas = pygame.Surface((tileSize,tileSize))
    even = False
    if tileSize %2 == 0:
        even = True
    drawPoint = []
    for x in range(0,int(tileSize/2)):
        match playerDirection:
            case 0: #left
                if even:
                    drawPoint.append((x,tileSize/2))
                    drawPoint.append((x,(tileSize/2)-1))
            case 1: #right
                if even:
                    drawPoint.append((tileSize-(x+1),tileSize/2))
                    drawPoint.append((tileSize-(x+1),(tileSize/2)-1))
            case 2: #up
                if even:
                    drawPoint.append((tileSize/2,x))
                    drawPoint.append(((tileSize/2)-1,x))
            case 3: #down
                if even:
                    drawPoint.append((tileSize/2,tileSize-(x+1)))
                    drawPoint.append(((tileSize/2)-1,tileSize-(x+1)))
    canvas.fill(green)
    for point in drawPoint:
        pygame.draw.rect(canvas,red,pygame.Rect(point[0],point[1],1,1))
    return canvas

def drawWall(wall:wall.Wall,color) -> pygame.Surface:
    canvas = pygame.Surface((tileSize,tileSize))
    canvas.fill(color)
    brokenColor = []
    for c in color:
        if c - 100 <=0:
            brokenColor.append(0)
        else:
            brokenColor.append(c-100)
    for point in wall.brokenPoints:
        pygame.draw.rect(canvas,brokenColor,pygame.Rect(point[0],point[1],1,1))
    pygame.draw.rect(canvas,brokenColor,pygame.Rect(0,0,tileSize,tileSize),width=2)
    return canvas

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

def displayStatistics(stats,startHeight,startWidth,selectItem,selectItemIndex,win,title = None):
    passes = 0
    longestWidth = 0

    if title != None:
        text = FONT.render(f"{title} :",True,FONTCOLOR)
        textRect = text.get_rect()
        textWidth = text.get_width()
        textHeight = text.get_height()
        textRect.center = (int(textWidth/2) +3,int(textHeight/2)+3)
        win.blit(text, textRect)

    if isinstance(stats,dict):
        keys = list(stats.keys())
        if len(keys) > 0:
            for x in range(len(keys)-1):
                arrow = ""
                if selectItem and selectItemIndex == x:
                    arrow = ">"
                if isinstance(stats[keys[x]],items.equipment):
                    text = FONT.render(f"{keys[x]} : {arrow} {stats[keys[x]].name}",True,FONTCOLOR)
                else:
                    text = FONT.render(f"{keys[x]} : {arrow} {stats[keys[x]]}",True,FONTCOLOR)
                textRect = text.get_rect()
                textWidth = text.get_width()
                textRect.center = (startWidth + int(textWidth/2), startHeight + (TEXTROWGAPDISTANCE * passes))
                win.blit(text, textRect)
                passes += 1
                if textWidth > longestWidth:
                    longestWidth = textWidth
        return startHeight + (TEXTROWGAPDISTANCE * passes)
    else:
        for x in range(len(stats)):   
            arrow = ""
            if selectItemIndex == x and selectItem:
                arrow = ">"
            if isinstance(stats[x],items.equipment):
                text = FONT.render(f"Slot{[x]} : {arrow} {stats[x].name}",True,FONTCOLOR)
            else:
                text = FONT.render(f"Slot{[x]} :{arrow} {stats[x]}",True,FONTCOLOR)
            textRect = text.get_rect()
            textWidth = text.get_width()
            textRect.center = (startWidth + int(textWidth/2), startHeight)
            win.blit(text, textRect)
            passes += 1
            startWidth += textWidth + 15
        return startWidth
    

def placeRandomItems(grid,listOfItems,NumOfitems,startingItemPosition):

    while(NumOfitems != 0):
        i = rand.randint(0,numberOfSpots-1)

        if grid[i][0] == 0 and i != startingItemPosition:
            grid[i][0] = 3
            grid[i].append([rand.choice(listOfItems)])
            NumOfitems -=1

def getItemsFromGrid(position):
    if position[0] == 3:
        return position[2]
    return None

def areItemsInTile(Id):
    if Id == 3:
        return True
    return False

def pickUpItem(items):
    player.addItemToInventory(items.pop())

def CreateRooms(emptyNodes):
    rooms = {"Stone":set(),"Wood":set(),"Sand":set(),"Gold":set()}

    nodes = []
    for node in emptyNodes:
        ns = set().union(node)
        nodes.append(ns)

    MostlyStone = [0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1,2,3]
    MostlySand = [3,3,3,3,3,3,3,3,3,3,3,3,3,3,3,3,3,3,3,3,3,3,3,3,3,3,3,0,2]
    MostlyWood = [1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,2,0,3]
    Gold = [2]
    Mixed = [0,1,2,3]
    randomProportions = {"Mostly Stone":MostlyStone,"Mostly Sand":MostlySand,"Mostly Wood":MostlyWood,"All Gold":Gold,"Mixed":Mixed}
    proportion = rand.choice(list(randomProportions))

    while len(emptyNodes) > 0:
        node = emptyNodes.pop()
        randomType = rand.choice(randomProportions[proportion])
        match randomType:
            case 0:
                rooms["Stone"]=rooms["Stone"].union(node)
            case 1:
                rooms["Wood"]=rooms["Wood"].union(node)
            case 2:
                rooms["Gold"]=rooms["Gold"].union(node)
            case 3:
                rooms["Sand"]=rooms["Sand"].union(node)    
            case _:
                rooms["Sand"]=rooms["Sand"].union(node)
    return rooms,proportion,nodes


def getRoomType(position,rooms):
    keys = rooms.keys()
    for key in keys:
        if position in rooms[key]:
            return key

def stepsToEmptyTile(position,grid,direction):
    steps = 0
    try:
        if direction == 0:
            if position >= ROWLENGHTH:
                if grid[position-ROWLENGHTH][0] != 0:
                    steps += stepsToEmptyTile(position-ROWLENGHTH,grid,direction)
                return steps +1
            return steps
        if direction == 1:
            if position <= ((ROWLENGHTH-1)*COLUMNLENGTH):
                if grid[position+ROWLENGHTH][0] != 0:
                    steps += stepsToEmptyTile(position+ROWLENGHTH,grid,direction)     
                return steps +1
            return steps
        if direction == 2:
            if position%ROWLENGHTH != 0:
                if grid[position-1][0] != 0:
                    steps += stepsToEmptyTile(position-1,grid,direction)   
                return steps +1
            return steps        
        if direction == 3:
            if position%ROWLENGHTH != (ROWLENGHTH-1):
                if grid[position+1][0] != 0:
                    steps += stepsToEmptyTile(position+1,grid,direction)   
                return steps +1
    except Exception as e:
        pass
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
                    return position-(upSteps*ROWLENGHTH)
                else:
                    return position - rightSteps
            else:
                if upSteps <= leftSteps and leftSteps !=0:
                    return position -(upSteps*ROWLENGHTH)
                else:
                    return position + leftSteps
        else:
            if downSteps > 0:
                if rightSteps <= leftSteps and rightSteps !=0:
                    if downSteps <= rightSteps:
                        return position + (downSteps*ROWLENGHTH)
                    else:
                        return position - rightSteps
                elif leftSteps <= downSteps and leftSteps !=0:
                    return position + leftSteps
                else:
                    return position + (downSteps*ROWLENGHTH)
            else:
                if rightSteps <= leftSteps and rightSteps !=0:
                    return(position - rightSteps)
                return(position + leftSteps)
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

def CreateWall(position,rooms):
    roomType = getRoomType(position,rooms)
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
def CreateNPC(position,rooms):
    roomType = getRoomType(position,rooms)
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
def gameRunning(menuDict:dict) -> bool:
    if True in menuDict.values():
        return False
    return True

def DrawMenu(selectItemIndex,window):
    
    menW,menH = menuBackground.get_size()

    MENUWIDTH = int(WIDTH/2 - (menW/2))
    MENUHEIGHT = int(HEIGHT/2 - (menH/2))

    canvas.fill((39,37,35,128))
    window.blit(canvas,(0,0))
    window.blit(menuBackground,(MENUWIDTH,MENUHEIGHT))
    # pygame.draw.rect(win,black,pygame.Rect(MENUWIDTH-5,MENUHEIGHT+ (SCREENHEIGHT/4),255,255))
    # pygame.draw.rect(win,white,pygame.Rect(MENUWIDTH,MENUHEIGHT+ (SCREENHEIGHT/4),250,250))

    textColor = (148,131,105)

    keys = menuOptions.keys()

    textStartWidth = int(MENUWIDTH + (menW/4.5))
    testStartHeight = int(MENUHEIGHT + (menH/3.5))
    selectItemIndex -= 1
    passes = 0
    for key in keys:
        if menuOptions[key]:
            text = FONT.render(f"{key} [x]",True,textColor)
            if passes == selectItemIndex:
                text = FONT.render(f"> {key} [x]",True,textColor)
            textRect = text.get_rect()
            textWidth = text.get_width()
            textRect.center = (textStartWidth + int(textWidth/2), testStartHeight + (TEXTROWGAPDISTANCE * (passes + 1)))
            win.blit(text, textRect)
            passes += 1
        else:
            text = FONT.render(f"{key} [ ]",True,textColor)
            if passes == selectItemIndex:
                text = FONT.render(f"> {key} [ ]",True,textColor)
            textRect = text.get_rect()
            textWidth = text.get_width()
            textRect.center = (textStartWidth + int(textWidth/2), testStartHeight + (TEXTROWGAPDISTANCE * (passes + 1)))
            win.blit(text, textRect)
            passes += 1
def PlaceRandomEnemies(grid,amount)-> set:
    placed = 0
    placedPositions = set()
    while placed < amount:
        gettingPosition = True
        placed +=1
        x = 0
        y = 0
        while gettingPosition:
            i = rand.randint(0,numberOfSpots -1)
            if i in placedPositions:
                pass
            else:
                placedPositions.add(i)
                gettingPosition = False
        grid[i][0] = 5

    return placedPositions

def MoveEnemies(currentPositions,grid,playerPosition):
    listOfNewPositions = set()
    for i in currentPositions:
        moving = True
        passes = 0
        while moving:
            passes += 1
            newPosition = 0 + i
            currentEnemy:enemies.Enemy = grid[i].pop()
            movedToNewPosition = False
            try:
                visiblePositions = rayCircleVision(i,currentEnemy.visionRange,ROWLENGHTH,grid,5,currentEnemy.tremorSense)
            except:
                print(grid[i][0])
                print(currentEnemy)
                raise
            if currentEnemy.lastPlayerPosition != None:
                if currentEnemy.lastPlayerPosition == i or grid[currentEnemy.lastPlayerPosition][0] ==5:
                    currentEnemy.lastPlayerPosition = None
            if i in visiblePositions:
                visiblePositions.remove(i)
            if currentEnemy.allSight:
                visiblePositions.add(playerPosition)
            if len(visiblePositions)== 0:
                moving = False
                break
            # else:
            #     for v in visiblePositions:
            #         grid[v][1] = 1
            if playerPosition in visiblePositions:
                currentEnemy.lastPlayerPosition = playerPosition
            elif currentEnemy.lastPlayerPosition == None and moving:
                n = -1
                while True:
                    n = rand.choice(list(visiblePositions))
                    if n in grid.keys():
                        break
                currentEnemy.lastPlayerPosition = n
            direction = -1*((i-currentEnemy.lastPlayerPosition)/abs(i-currentEnemy.lastPlayerPosition))

            if sameColumn(i,currentEnemy.lastPlayerPosition,ROWLENGHTH):
                newPosition = int((direction * ROWLENGHTH) + i)
            elif sameRow(i,currentEnemy.lastPlayerPosition,ROWLENGHTH):
                newPosition = int(direction + i)
            else:
                if rand.randint(0,1):
                    newPosition = int((direction * ROWLENGHTH) + i)
                else:
                    newPosition = int(direction + i)
            if passes >= 4:
                moving = False
                break
            if newPosition not in grid.keys():
                currentEnemy.lastPlayerPosition = None
                grid[i].append(currentEnemy)
            else:
                moving = False
                if grid[newPosition][0] == 0:
                    movedToNewPosition = True
                elif grid[newPosition][0] == 1:
                    player.damageTaken += currentEnemy.damage
                elif grid[newPosition][0] == 2:
                    if currentEnemy.dig:
                        grid[newPosition][2].takeDamage(currentEnemy.wallDamage,tileSize)
                        if grid[newPosition][2].hp <= 0:
                            grid[newPosition].pop()
                            grid[newPosition][0] = 0
                    elif currentEnemy.burrow:
                        enemyOccupiedItemSpaces[newPosition] = copy.copy(grid[newPosition])
                        enemyOccupiedItemSpaces[newPosition][2].hp -= 1
                        movedToNewPosition = True
                        grid[newPosition].pop()
                    elif currentEnemy.lastPlayerPosition == newPosition:
                        currentEnemy.lastPlayerPosition = None
                        moving = True
                elif grid[newPosition][0] == 3:
                    enemyOccupiedItemSpaces[newPosition] = copy.copy(grid[newPosition])
                    movedToNewPosition = True
            if movedToNewPosition:
                grid[i][0] = 0
                grid[newPosition][0] = 5
                grid[newPosition].append(currentEnemy)
                listOfNewPositions.add(newPosition)
            else:
                grid[i].append(currentEnemy)
                if moving == False:
                    listOfNewPositions.add(i)
            if movedToNewPosition:
                try:
                    item = enemyOccupiedItemSpaces.pop(i)
                    grid[i] = item
                except:
                    pass
    return listOfNewPositions


def MoveEnemiesRandomly(currentPositions,grid):
    listOfNewPositions = []
    for i in currentPositions:
        if grid[i][2].move:
            currentEnemy = grid[i].pop(2)
            moving = True
            passes = 0
            possiblePositions = [i+1,i-1,i+ROWLENGHTH,i-ROWLENGHTH]
            while moving:
                passes += 1
                randomDirection = possiblePositions[rand.randint(0,len(possiblePositions)-1)]
                try:
                    if randomDirection >= 0 and randomDirection <= numberOfSpots:
                        currentEnemy.lastpositions.append(i)
                        if passes >= 4:
                            moving = False
                            listOfNewPositions.append(i)
                            grid[i].append(currentEnemy)
                            break
                        if grid[randomDirection][0] == 0:
                            grid[randomDirection][0] = 5
                            grid[randomDirection].append(currentEnemy)
                            listOfNewPositions.append(randomDirection)
                            grid[i][0] = 0
                            moving = False
                        elif grid[randomDirection][0] == 1:
                            player.damageTaken += currentEnemy.damage
                            grid[i].append(currentEnemy)
                            listOfNewPositions.append(i)
                            moving = False
                        elif grid[randomDirection][0] == 2:
                            if currentEnemy.dig:
                                grid[randomDirection][2].hp -= currentEnemy.wallDamage
                                if grid[randomDirection][2].hp <= 0:
                                    grid[i][0] = 0
                                    grid[randomDirection].pop(2)
                                    grid[randomDirection].append(currentEnemy)
                                    grid[randomDirection][0] = 5
                                    listOfNewPositions.append(randomDirection)
                                else:
                                    grid[i].append(currentEnemy)
                                    listOfNewPositions.append(i)
                                moving = False
                except Exception as e:
                    print(f"\n\n\n{str(e)}\n\n\n")
                    grid[i].append(currentEnemy)
                    listOfNewPositions.append(i)
                    moving = False
    return listOfNewPositions

def CheckForItem(grid):
    for i in grid.keys():
        if grid[i][0] == 3:
            grid[i][0] = 3

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

def saveLevel(grid,rooms,proportions,enemies,level,listOfGrids): 
    if level < len(listOfGrids):
        listOfGrids[level] = [grid,rooms,proportions,enemies]
    else:
        listOfGrids.append([grid,rooms,proportions,enemies])   

def RemoveDeadNPCs(listOfPositions):
    stillAlivePositions = []
    while(len(listOfPositions) > 0):
        position = listOfPositions.pop()
        if grid[position][2].hp <= 0:
            grid[position][0] = 0
            grid[position].pop(2)
            print("Dead Cleaned up")
        else:
            stillAlivePositions.append(position)
    return stillAlivePositions

def PlacePreviousLevelDoor(grid,position):
    grid[position][0] = 6

def rayCircleVision(position,visionRange,rowLength,grid,selfNum,tremorSense = False) -> set:
    Lrays = []
    Frays = []
    positions = set()
    h = position%rowLength
    k = int((position-h)/rowLength)
    t = 0
    while t < 2 *math.pi:
        ray = []
        for r in range(0,visionRange+1):
            x = (r*math.cos(t) + h)
            y = (r*math.sin(t) + k)
            point = (round(x),round(y))
            if point not in ray:
                ray.append(point)
        Lrays.append(ray)
        t += .1
    for r in Lrays:
        FRay = []
        for p in r:
            flatened = (p[0]+(p[1]*rowLength))
            if flatened in grid.keys():
                FRay.append(flatened)
        Frays.append(FRay)
    for r in Frays:
        for p in r:
            if grid[p][0] == 0 or grid[p][0] == selfNum or tremorSense:
                positions.add(p)
            else:
                positions.add(p)
                break
    return positions

def createARay(startPosition,targetPosition,rowLength):
    sX = startPosition%rowLength
    sY = int((startPosition-sX)/rowLength)

    tX = targetPosition%rowLength
    tY = int((targetPosition-tX)/rowLength)

    angle = math.atan2(tY-sY,tX-sX)
    distance = int(math.sqrt(((tX-sX)**2)+((tY-sY)**2)))

    ray = set()
    flatRays = set()
    for r in range(0,distance+1):
        x = (r*math.cos(angle) + sX)
        y = (r*math.sin(angle) + sY)

        ray.add((round(x),round(y)))
    flatRays.add(targetPosition)
    for p in ray:
        flatRays.add(p[0]+(p[1]*rowLength))
    
    if startPosition in flatRays:
        flatRays.remove(startPosition)
    return flatRays

def setPositionsVisible(grid,visiblePositions):
    for i in grid.keys():
        try:
            if grid[i][1] == 1:
                grid[i][1] = 2
        except Exception as e:
            raise e
                

    for position in visiblePositions:
        grid[position][1] = 1

def PlaceNextLevelDoor(grid) -> int:
    gettingRandomPosition = True
    while(gettingRandomPosition):
        i = rand.randint(0,numberOfSpots -1)
        if(grid[i][0] == 0 or grid[i][0] == 2):
            gettingRandomPosition = False
            grid[i][0] = 4
            return i

loadMenuOptions("menuOpts.txt",menuOptions)

def LoadTxtFile(txtFile):
    openMapFile = open(txtFile,'r')
    MapListFromTxt = openMapFile.readlines()
    openMapFile.close()
    for row in MapListFromTxt:
        levelGrids.append(row.split(','))

def LoadLevel(level,listOfGrids):

    return listOfGrids[level][0],listOfGrids[level][1],listOfGrids[level][2],listOfGrids[level][3]
    

def GetEnemyPositions(grid):
    enemyPositions = []

    for i in grid.keys():
        if grid[i][0] == 5:
            enemyPositions.append(i)
    return enemyPositions

def GenerateRandomLevel(grid):
    for i in grid.keys():
        isWall = rand.randint(0,1)
        if isWall == 1:
            grid[i][0] = 2

def createObjects(grid,rooms):
    for i in grid.keys():
        if grid[i][0] == 2:
            grid[i].append(CreateWall(i,rooms))
        elif grid[i][0] == 5:
            grid[i].append(CreateNPC(i,rooms))

def generateNewLevel(addStartingItem = False):
    grid = {}
    ListOfEnemyPositions = set()
    for i in range(numberOfSpots):
        grid[i] = [0,0]
    GenerateRandomLevel(grid)
    if addStartingItem:
        startingItem = [3,0,[items.startingPick]]
        grid[playerPosition-1] = startingItem
    rooms,proportion,nodes = CreateRooms(CER.createNodes(grid,ROWLENGHTH,5))
    for room in nodes:
        caveIn = rand.randint(0,100)
        if caveIn == False:
            for i in room:
                grid[i][0] = 2
    if proportion != "All Gold":
        ListOfEnemyPositions = PlaceRandomEnemies(grid,5)
    placeRandomItems(grid,items.createRandomStatItems(3),10,playerPosition-1)
    createObjects(grid,rooms)

    return grid, ListOfEnemyPositions,rooms,proportion,nodes
def getRandomPoint(width,height):
    x = rand.randint(width[0],width[1]-1)
    y = rand.randint(height[0],height[1]-1)

    return (x,y)

def getLookPosition(direction,playerPosition):
    match direction:
        case 0:
            return playerPosition - 1
        case 1:
            return playerPosition + 1
        case 2:
            return playerPosition - ROWLENGHTH
        case 3:
            return playerPosition + ROWLENGHTH

def drawMessage(message:str,size,color,fade =255) -> pygame.Surface:
    
    MessageFont = pygame.ftfont.Font('Forgore.otf',size)
    text = MessageFont.render(message,True,color)
    textRect = text.get_rect()
    textWidth = text.get_width()
    textHeight = text.get_height()
    canvas = pygame.Surface((WIDTH,HEIGHT),pygame.SRCALPHA)
    canvas.fill((0,0,0,fade))
    textRect.center = (int(textWidth/2) +3,int(textHeight/2)+3)
    text.set_alpha(fade)
    canvas.blit(text, (int(WIDTH/2)-int(textWidth/2),int(HEIGHT/2)-int(textHeight/2)))

    return canvas

def startGame():
    rooms = []
    ListOfEnemyPositions = set()
    nodes = []
    proportion = None
    grid = None
    if menuOptions["Load Room"]:
        LoadTxtFile("dungeonLevels.txt")
    elif menuOptions["Generate Room"]:
        # First Level Creation
        grid, ListOfEnemyPositions,rooms,proportion,nodes = generateNewLevel(True)
    else:
        pass
        # wallStartx = 30
        # wallstarty = 30
        # grid[wallStartx][wallstarty] = 2
        # grid[wallStartx][wallstarty- 2] = 2
    enemyMove = False
    doorPostions = []

    playerTurn = True

    generateNewLevelBool = False
    generatePreviousLevel = False
    generateNextLevel = False

    EnemyCount = 1
    selectItemIndex = 0
    runing = True
    NewLevelDoorNotAdded = True
    menuDict = {"selectItem":False,"menuOpen":False,"inventoryOpen":False,"unEquip":False,"ChangingColor":False,"ColorSelected":False,"levelup":False}
    selectedColor = "white"
    colorIndex = 0
    currentPosition = "Floor"
    currentLocation = copy.copy(grid[playerPosition])
    currentAimSpot = None
    aimLine = None

    return grid,rooms,ListOfEnemyPositions,nodes,proportion,enemyMove,doorPostions,playerTurn,generateNewLevelBool,generatePreviousLevel,generateNextLevel, EnemyCount,selectItemIndex,runing, NewLevelDoorNotAdded, menuDict,selectedColor,colorIndex,currentPosition,currentLocation,currentAimSpot,aimLine

grid,rooms,ListOfEnemyPositions,nodes,proportion,enemyMove,doorPostions,playerTurn,generateNewLevelBool,generatePreviousLevel,generateNextLevel, EnemyCount,selectItemIndex,runing, NewLevelDoorNotAdded, menuDict,selectedColor,colorIndex,currentPosition,currentLocation,currentAimSpot,aimLine = startGame()
change = True
fade = 255

messageBools = {"escapeMessage":True,"floorLevelMessage":False,"brokenSealMessage":False}
addUnsealed = False
goldWallCount = 0


while runing:
    if True in messageBools.values():
        change = True

    rotate = False
    aim = False
    lookPosition = getLookPosition(playerDirection,playerPosition)
    try:
        roomItems = getItemsFromGrid(grid[lookPosition])
    except:
        pass
    cardinalDirection = getDirection(playerDirection)
    itemsInRoom = False
    if roomItems != None:
        itemsInRoom = True
    minDamage,maxDamage = player.getMinMaxDamage()

    if player.getCurrentHealth() <= 0:
        grid,rooms,ListOfEnemyPositions,nodes,proportion,enemyMove,doorPostions,playerTurn,generateNewLevelBool,generatePreviousLevel,generateNextLevel, EnemyCount,selectItemIndex,runing, NewLevelDoorNotAdded, menuDict,selectedColor,colorIndex,currentPosition,currentLocation,currentAimSpot,aimLine = startGame()
        player:pc.PlayerClass = pc.PlayerClass()
    
    
    # pygame.time.delay(100)
    KeyboardKeys = pygame.key.get_pressed()
    if KeyboardKeys[pygame.K_LCTRL]:
        aim = True
        change = True
    elif KeyboardKeys[pygame.K_LALT]:
        rotate = True
        change = True

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            saveMenuOptions("menuOpts.txt",menuOptions)
            if menuOptions["Save on Exit"]:
                saveToTxt("dungeonLevels.txt")
            runing = False
        if event.type == pygame.MOUSEWHEEL:
            if menuDict["ChangingColor"]:
                if selectItemIndex -event.y < len(colorDict.keys()) and selectItemIndex -event.y >=0:
                    selectItemIndex -= event.y
                    keys = colorDict.keys()
                    passes = 0
                    for key in keys:
                        if passes == selectItemIndex:
                            selectedColor = key
                            break
                        passes += 1
            elif menuDict["ColorSelected"]:
                if colorDict[selectedColor][colorIndex] +event.y <= 255 and colorDict[selectedColor][colorIndex] +event.y >= 0:
                    colorDict[selectedColor][colorIndex] += event.y
        if event.type == pygame.KEYUP:
            if event.key == pygame.K_LCTRL:
                currentAimSpot = None
                aimLine = None
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_l:
                if menuDict["levelup"]:
                    menuDict["levelup"] = False
                    selectItemIndex = 0
                else:
                    menuDict["levelup"] = True
            if event.key == pygame.K_p:
                if menuDict["ChangingColor"]:
                    menuDict["ChangingColor"] = False
                elif menuDict["ColorSelected"]:
                    menuDict["ColorSelected"] = False
                else:
                    menuDict["ChangingColor"] = True
            if event.key == pygame.K_q:
                saveMenuOptions("menuOpts.txt",menuOptions)
                if menuOptions["Save on Exit"]:
                    saveToTxt("dungeonLevels.txt")
                runing = False
            if event.key == pygame.K_RETURN:
                if aim:
                    pass
                elif playerPosition == doorPostions[level]:
                    if level < len(doorPostions) -1:
                        generateNextLevel = True
                    else:
                        generateNewLevelBool = True
                elif playerPosition == doorPostions[level -1]:
                    generatePreviousLevel = True
                elif menuDict["menuOpen"]:
                    keys = menuOptions.keys()
                    passes = 0
                    for key in keys:
                        if passes == selectItemIndex -1:
                            if menuOptions[key]:
                                menuOptions[key] = False
                            else:
                                menuOptions[key] = True
                        passes += 1
                elif menuDict["selectItem"]:
                    pickUpItem(roomItems)
                    selectItemIndex = 0
                    if len(roomItems) == 0:
                            grid[lookPosition] = [0,1]
                            menuDict["selectItem"] = False
                            selectItemIndex = 0
                elif menuDict["inventoryOpen"]:
                    if player.inventory[selectItemIndex].Etype == "Consume":
                        player.useConsumable(selectItemIndex)
                        if selectItemIndex >0:
                            selectItemIndex -= 1
                    else:
                        player.equipItem(selectItemIndex)
                        selectItemIndex -= 1
                    if len(player.inventory) == 0:
                        menuDict["inventoryOpen"] = False
                        selectItemIndex = 0
                elif menuDict["unEquip"]:
                    keys = player.equipment.keys()
                    equipmentSlot = None
                    passes = 0
                    for key in keys:
                        if passes == selectItemIndex:
                            equipmentSlot = key
                            break
                        passes +=1
                    player.unEquipItem(equipmentSlot)
                elif menuDict["ChangingColor"]:
                    menuDict["ChangingColor"] = False
                    menuDict["ColorSelected"] = True
                elif menuDict["levelup"]:
                    keys = player.attributes.keys()
                    attributeKey = None
                    passes = 0
                    for key in keys:
                        if passes == selectItemIndex:
                            attributeKey = key
                            break
                        passes +=1
                    player.levelUp(attributeKey)
            if event.key == pygame.K_ESCAPE:
                if menuDict["menuOpen"]:
                    menuDict["menuOpen"] = False
                    selectItemIndex = 1
                else:
                    menuDict["menuOpen"] = True
                    selectItemIndex =1
            if event.key == pygame.K_q:
                if menuDict["selectItem"]:
                    menuDict["selectItem"] = False
                    selectItemIndex = 1
                if menuDict["menuOpen"]:
                    menuDict["menuOpen"] = False
                    selectItemIndex = 1
            if gameRunning(menuDict):
                targetPos:tuple = ()
                validMove:bool = False
                if event.key == pygame.K_e:
                    if playerDirection == 0:
                        targetPos = playerPosition-1 
                    elif playerDirection == 1:
                        targetPos = playerPosition+1
                    elif playerDirection == 2:
                        targetPos = playerPosition-ROWLENGHTH
                    elif playerDirection == 3:
                        targetPos = playerPosition+ROWLENGHTH
                    try:
                        if grid[targetPos][0] == 2: #if that spot is a wall
                            dig = True
                            if player.burrow:
                                if grid[targetPos][2].soft:
                                    dig = False
                            if dig:
                                if grid[targetPos][2].hp > 0:
                                    grid[targetPos][2].takeDamage(player.getWallDamage(),tileSize)
                                if grid[targetPos][2].hp <= 0:
                                    if grid[targetPos][2].name == "Gold Wall":
                                        player.alterGold(1)
                                        if proportion == "All Gold":
                                            goldWallCount += 1
                                            if goldWallCount >= 10 and addUnsealed == False:
                                                messageBools["brokenSealMessage"] = True
                                                addUnsealed = True
                                    grid[targetPos][0] = 0
                                    grid[targetPos].pop()
                                
                            else:
                                currentWall = copy.copy(grid[targetPos])
                                currentWall[2].hp -= 1
                                if currentWall[2].hp <= 0:
                                    grid[targetPos][0] = 0
                                    grid[targetPos][2].pop()
                                else:
                                    grid[playerPosition] = copy.copy(currentLocation)
                                    currentLocation = currentWall
                                    grid[targetPos][0] = 1
                                    playerPosition = targetPos
                        elif grid[targetPos][0] == 5: #if that spot is an enemy
                            damage = player.DealDamage()
                            grid[targetPos][2].hp -= damage
                            if grid[targetPos][2].hp <= 0:
                                player.gold += grid[targetPos].pop().gold
                                grid[targetPos][0] = 0
                                ListOfEnemyPositions.remove(targetPos)
                        elif grid[targetPos][0] == 3:
                            print("Trying to select Items")
                            if menuDict["selectItem"] == False:
                                if roomItems != None:
                                    menuDict["selectItem"] = True
                                                        
                        enemyMove = True
                    except Exception as e:
                        print("An Exception Occured!")
                        print(str(e))
                        raise

            if event.key == pygame.K_i:
                if gameRunning(menuDict) and len(player.inventory) > 0:
                    menuDict["inventoryOpen"] = True
                    selectItemIndex = 0
                elif menuDict["inventoryOpen"]:
                    menuDict["inventoryOpen"] = False
                    selectItemIndex = 0

            if event.key == pygame.K_u:
                if gameRunning(menuDict):
                    menuDict["unEquip"] = True
                    selectItemIndex = 0
                elif menuDict["unEquip"]:
                    menuDict["unEquip"] = False
                    selectItemIndex = 1
            
            moveMade:bool = False
            targetLocation = None
            xvelocity = 0
            yvelocity = 0
            indexMove = 0
            newDirection = playerDirection
            match event.key:
                case pygame.K_LEFT | pygame.K_a:
                    newDirection = 0
                    if colorIndex - 1 >=0:
                        colorIndex -=1
                    xvelocity -= 1
                case pygame.K_RIGHT | pygame.K_d:
                    newDirection = 1
                    if colorIndex + 1 <3:
                        colorIndex +=1
                    xvelocity += 1
                case pygame.K_UP | pygame.K_w:
                    indexMove -= 1
                    newDirection = 2
                    yvelocity -= 1
                case pygame.K_DOWN | pygame.K_s:
                    indexMove += 1
                    newDirection = 3
                    yvelocity += 1
            if enemyMove == False:
                change = True
                if aim:
                    if currentAimSpot == None:
                        currentAimSpot = playerPosition + xvelocity + (yvelocity*ROWLENGHTH)
                    else:
                        currentAimSpot = currentAimSpot + xvelocity + (yvelocity*ROWLENGHTH)
                    aimLine = createARay(playerPosition,currentAimSpot,ROWLENGHTH)
                elif rotate:
                    playerDirection = newDirection
                elif gameRunning(menuDict):
                    playerDirection = newDirection
                    newPlayerPosition = playerPosition + xvelocity + (yvelocity*ROWLENGHTH)
                    targetLocation = None
                    try:
                        if newPlayerPosition >=0:
                            targetLocation = grid[newPlayerPosition][0]
                        else:
                            newPlayerPosition = playerPosition
                    except:
                        newPlayerPosition = playerPosition
                    if targetLocation != 2 and targetLocation != 5 and targetLocation != None:
                        grid[playerPosition] = copy.copy(currentLocation)
                        currentLocation = copy.copy(grid[newPlayerPosition])
                        playerPosition = newPlayerPosition
                        enemyMove = True
                        CheckForItem(grid)
                        
                else:
                    if menuDict["selectItem"]:
                        if selectItemIndex + indexMove < len(roomItems) and selectItemIndex + indexMove > 0:
                            selectItemIndex +=indexMove
                    elif menuDict["menuOpen"]:
                        if selectItemIndex +indexMove <= len(menuOptions.keys()) and selectItemIndex + indexMove >= 0:
                            selectItemIndex +=indexMove
                    elif menuDict["inventoryOpen"]:
                        if selectItemIndex +indexMove < len(player.inventory) and selectItemIndex + indexMove >= 0:
                            selectItemIndex +=indexMove
                    elif menuDict["unEquip"]:
                        if selectItemIndex +indexMove < len(player.equipment.keys())-1 and selectItemIndex + indexMove >=0:
                            selectItemIndex +=indexMove
                    elif menuDict["levelup"]:
                        if selectItemIndex + indexMove < len(player.attributes.keys())-1 and selectItemIndex + indexMove >= 0:
                            selectItemIndex += indexMove
                    
    grid[playerPosition][0] = 1
    if enemyMove:
        change = True
        ListOfEnemyPositions = MoveEnemies(ListOfEnemyPositions,grid,playerPosition)
        enemyMove = False
        if addUnsealed:
            keys = grid.keys()
            validSpots = []
            for k in keys:
                if grid[k][0] == 2:
                    validSpots.append(k)
            if len(validSpots) > 0:
                addPosition = rand.choice(validSpots)
                unsealed = enemies.Unsealed()
                grid[addPosition][0] = 5
                grid[addPosition].pop()
                grid[addPosition].append(unsealed)
                ListOfEnemyPositions.add(addPosition)
            else:
                addUnsealed = False
                

    
    gameWindow.fill((fog))

    previousDoorPos = None
    if NewLevelDoorNotAdded:
        NewLevelDoorNotAdded = False
        doorPostions.append(PlaceNextLevelDoor(grid))

    currentDoorPos = doorPostions[level]
    if level > 0:
        previousDoorPos = doorPostions[level -1]
    if playerPosition == currentDoorPos:
        currentPosition = "Door to Next Level"
    elif playerPosition == previousDoorPos:
        currentPosition = "Door to previous Level"
    elif currentLocation[0] == 3:
        if len(currentLocation[2]) > 1:
            currentPosition = "Items"
        else:
            currentPosition = "Item"
    else:
        currentPosition = "Floor"
    
    if len(doorPostions) > 0:
        currentDoorPos = doorPostions[level]
        if grid[currentDoorPos][0] != 1:
            grid[currentDoorPos][0] = 4
        if level > 0:
            previousDoorPos = doorPostions[level -1]
            if grid[previousDoorPos][0] !=1:
                grid[previousDoorPos][0] = 6

    if generateNextLevel:

        saveLevel(grid,rooms,proportion,ListOfEnemyPositions,level,levelGrids)

        level = level + 1
        grid,rooms,proportion,ListOfEnemyPositions = LoadLevel(level,levelGrids)
        

        generateNextLevel = False
        messageBools["floorLevelMessage"] = True

    elif generatePreviousLevel and level -1 >=0:

        saveLevel(grid,rooms,proportion,ListOfEnemyPositions,level,levelGrids)

        level = level - 1
        grid,rooms,proportion,ListOfEnemyPositions = LoadLevel(level,levelGrids)


        generatePreviousLevel = False
        messageBools["floorLevelMessage"] = True
    elif generateNewLevelBool:
        saveLevel(grid,rooms,proportion,ListOfEnemyPositions,level,levelGrids)

        grid, ListOfEnemyPositions,rooms,proportion,nodes = generateNewLevel()

        level +=1
        
        PlacePreviousLevelDoor(grid,doorPostions[-1])

        NewLevelDoorNotAdded = True
        generateNewLevelBool = False
        messageBools["floorLevelMessage"] = True

    leftPanel.fill((black))
    rightPanel.fill((black))
    bottomPanel.fill((black))

    roomType = getRoomType(playerPosition,rooms)
    CharacterStatistics = {"Health":player.getCurrentHealth(),"AC":player.damageReduction(),"Gold":player.gold,"Player Direction":cardinalDirection,"Wall Damage":player.getWallDamage(),"Player Min Damage":minDamage,"Player Max Damage":maxDamage,"Player X":playerposx,"Player Y":playerposy}
    RoomStatistics = {"Floor Type":proportion,"Room Type":roomType,"Items":str(itemsInRoom),"Level":level,"Current Position":currentPosition,"Color Selected":selectedColor}
    
    textStartHeight = displayStatistics(CharacterStatistics,TEXTSTARTHEIGHT + 35,TEXTSTARTWIDTH,False,selectItemIndex,leftPanel)
    textStartHeight += displayStatistics(RoomStatistics,TEXTSTARTHEIGHT +35 +textStartHeight,TEXTSTARTWIDTH,False,selectItemIndex,leftPanel)
    displayStatistics(player.equipment,TEXTSTARTHEIGHT + 35,TEXTSTARTWIDTH,menuDict["unEquip"],selectItemIndex,rightPanel)

    if menuDict["inventoryOpen"]:
        displayStatistics(player.inventory,TEXTSTARTHEIGHT + 35,TEXTSTARTWIDTH,menuDict["inventoryOpen"],selectItemIndex,bottomPanel,"Inventory")
    elif menuDict["selectItem"]:
        displayStatistics(roomItems,TEXTSTARTHEIGHT + 35,TEXTSTARTWIDTH,menuDict["selectItem"],selectItemIndex,bottomPanel,"Items in Room")
    elif menuDict["levelup"]:
        displayStatistics(player.attributes,TEXTSTARTHEIGHT + 35,TEXTSTARTWIDTH,menuDict["levelup"],selectItemIndex,bottomPanel,f"Player Gold: {player.gold} LevelUp Cost: {player.nextLevelGold}")

    
    if change:
        visiblePositions = rayCircleVision(playerPosition,player.visionRange,ROWLENGHTH,grid,1)
        setPositionsVisible(grid,visiblePositions)
        # canvas.fill((0,0,0,0))
        # backGroundCanvas.fill((0,0,0))
        for i in grid.keys():
            x = i%ROWLENGHTH
            y = int((i-x)/ROWLENGHTH)
            if grid[i][1] == 1: #Is this position visible?
                # backGroundCanvas.blit(FloorSwampSprite,(x*tileSize,y*tileSize))
                match grid[i][0]:
                    case 0: #Empty space
                        if i in rooms["Stone"]:
                            pygame.draw.rect(gameWindow,stoneRoomFloor,pygame.Rect(x*tileSize,y*tileSize,tileSize,tileSize))
                        elif i in rooms["Wood"]:
                            pygame.draw.rect(gameWindow,woodRoomFloor,pygame.Rect(x*tileSize,y*tileSize,tileSize,tileSize))
                        elif i in rooms["Gold"]:
                            pygame.draw.rect(gameWindow,gold,pygame.Rect(x*tileSize,y*tileSize,tileSize,tileSize))
                        else:
                            pygame.draw.rect(gameWindow,tan,pygame.Rect(x*tileSize,y*tileSize,tileSize,tileSize))
                    case 1: #Player
                        # canvas.blit(playerSpriteTopDown,(x*tileSize,y*tileSize))
                        gameWindow.blit(drawPlayer(playerDirection),(x*tileSize,y*tileSize))
                        # pygame.draw.rect(gameWindow,green,drawPlayer(playerDirection))
                    case 2: #Wall
                        w = grid[i][2]
                        # canvas.blit(stoneWallSprite,(x*tileSize,y*tileSize))
                        match w.name:
                            case "Stone Wall":
                                gameWindow.blit(drawWall(w,stoneRoomFloor),(x*tileSize,y*tileSize))
                                #pygame.draw.rect(gameWindow,stoneRoomFloor,pygame.Rect(x*tileSize,y*tileSize,tileSize,tileSize))
                            case "Wood Wall":
                                gameWindow.blit(drawWall(w,woodRoomFloor),(x*tileSize,y*tileSize))
                                #pygame.draw.rect(gameWindow,woodRoomFloor,pygame.Rect(x*tileSize,y*tileSize,tileSize,tileSize))
                            case "Sand Wall":
                                gameWindow.blit(drawWall(w,tan),(x*tileSize,y*tileSize))
                                #pygame.draw.rect(gameWindow,tan,pygame.Rect(x*tileSize,y*tileSize,tileSize,tileSize))
                            case "Gold Wall":
                                gameWindow.blit(drawWall(w,gold),(x*tileSize,y*tileSize))
                                #pygame.draw.rect(gameWindow,gold,pygame.Rect(x*tileSize,y*tileSize,tileSize,tileSize))
                            case _:
                                gameWindow.blit(drawWall(w,blue),(x*tileSize,y*tileSize))
                                #pygame.draw.rect(gameWindow,blue,pygame.Rect(x*tileSize,y*tileSize,tileSize,tileSize))
                        #pygame.draw.rect(gameWindow,black,pygame.Rect(x*tileSize,y*tileSize,tileSize,tileSize),width=2)
                    case 3: #Chest
                        pygame.draw.rect(gameWindow,purple,pygame.Rect(x*tileSize,y*tileSize,tileSize,tileSize))
                    case 4: #NextDoor
                        pygame.draw.rect(gameWindow,blue,pygame.Rect(x*tileSize,y*tileSize,tileSize,tileSize))
                    case 5:#Enemy
                        # canvas.blit(enemySprite,(x*tileSize,y*tileSize))
                        pygame.draw.rect(gameWindow,red,pygame.Rect(x*tileSize,y*tileSize,tileSize,tileSize))
                        # match grid[i][2].name:
                        #     case "Goblin":
                        #         pygame.draw.rect(gameWindow,red,pygame.Rect(x*tileSize,y*tileSize,tileSize,tileSize))
                        #     case "Goblin Chieftan":
                        #         pygame.draw.rect(gameWindow,crimson,pygame.Rect(x*tileSize,y*tileSize,tileSize,tileSize))
                        #     case "Dire Rat":
                        #         pygame.draw.rect(gameWindow,ratBrown,pygame.Rect(x*tileSize,y*tileSize,tileSize,tileSize))
                    case 6: #PreviousDoor
                        pygame.draw.rect(gameWindow,blue,pygame.Rect(x*tileSize,y*tileSize,tileSize,tileSize))
            elif grid[i][1] == 2: #Is this position memorized?
                # backGroundCanvas.blit(FloorSwampSprite,(x*tileSize,y*tileSize))
                match grid[i][0]:
                    case 2: #wall
                        w = grid[i][2]
                        # canvas.blit(stoneWallSprite,(x*tileSize,y*tileSize))
                        match w.name:
                            case "Stone Wall":
                                gameWindow.blit(drawWall(w,shadowyfloorGray),(x*tileSize,y*tileSize))
                                #pygame.draw.rect(gameWindow,shadowyfloorGray,pygame.Rect(x*tileSize,y*tileSize,tileSize,tileSize))
                            case "Wood Wall":
                                gameWindow.blit(drawWall(w,shadowyWoodFloor),(x*tileSize,y*tileSize))
                                #pygame.draw.rect(gameWindow,shadowyWoodFloor,pygame.Rect(x*tileSize,y*tileSize,tileSize,tileSize))
                            case "Sand Wall":
                                gameWindow.blit(drawWall(w,shadowyTan),(x*tileSize,y*tileSize))
                                #pygame.draw.rect(gameWindow,shadowyTan,pygame.Rect(x*tileSize,y*tileSize,tileSize,tileSize))
                            case "Gold Wall":
                                gameWindow.blit(drawWall(w,shadowyGold),(x*tileSize,y*tileSize))
                                #pygame.draw.rect(gameWindow,shadowyGold,pygame.Rect(x*tileSize,y*tileSize,tileSize,tileSize))
                            case _:
                                pygame.draw.rect(gameWindow,blue,pygame.Rect(x*tileSize,y*tileSize,tileSize,tileSize))
                        # pygame.draw.rect(gameWindow,black,pygame.Rect(x*tileSize,y*tileSize,tileSize,tileSize),width=2)
                    case 3: #Chest
                        pygame.draw.rect(gameWindow,shadowyPurple,pygame.Rect(x*tileSize,y*tileSize,tileSize,tileSize))
                    case 4: #NextDoor
                        pygame.draw.rect(gameWindow,blue,pygame.Rect(x*tileSize,y*tileSize,tileSize,tileSize))
                    case 6: #PreviousDoor
                        pygame.draw.rect(gameWindow,blue,pygame.Rect(x*tileSize,y*tileSize,tileSize,tileSize))
                    case _: #floor
                        if i in rooms["Stone"]:
                            pygame.draw.rect(gameWindow,shadowyfloorGray,pygame.Rect(x*tileSize,y*tileSize,tileSize,tileSize))
                        elif i in rooms["Wood"]:
                            pygame.draw.rect(gameWindow,shadowyWoodFloor,pygame.Rect(x*tileSize,y*tileSize,tileSize,tileSize))
                        elif i in rooms["Gold"]:
                            pygame.draw.rect(gameWindow,shadowyGold,pygame.Rect(x*tileSize,y*tileSize,tileSize,tileSize))
                        else:
                            pygame.draw.rect(gameWindow,shadowyTan,pygame.Rect(x*tileSize,y*tileSize,tileSize,tileSize))
            # if grid[i][0] == 5:
            #     pygame.draw.rect(gameWindow,red,pygame.Rect(x*tileSize,y*tileSize,tileSize,tileSize))
        if currentAimSpot != None:
            if aimLine != None:
                for i in aimLine:
                    x = i%ROWLENGHTH
                    y = int((i-x)/ROWLENGHTH)
                    pygame.draw.rect(gameWindow,crimson,pygame.Rect(x*tileSize,y*tileSize,tileSize,tileSize))

        pygame.draw.rect(leftPanel,FONTCOLOR,pygame.Rect(0,0,LEFTPANELWIDTH,LEFTPANELHEIGHT),width=2)
        pygame.draw.rect(rightPanel,FONTCOLOR,pygame.Rect(0,0,RIGHTPANELWIDTH,RIGHTPANELHEIHGT),width=2)
        pygame.draw.rect(bottomPanel,FONTCOLOR,pygame.Rect(0,0,BOTTOMPANELWIDTH,BOTTOMPANELHEIGHT),width=2)
        pygame.draw.rect(gameWindow,FONTCOLOR,pygame.Rect(0,0,WIDTH,HEIGHT),width=2)
        #win.blit(backGroundCanvas,(0,0))
        #win.blit(canvas,(0,0))
        if messageBools["escapeMessage"]:
            gameWindow.blit(drawMessage("Escape",150,FONTCOLOR,fade),(0,0))
            fade -= .2
            if fade <= 0:
                messageBools["escapeMessage"] = False
                fade = 255
        elif messageBools["floorLevelMessage"]:
            gameWindow.blit(drawMessage(f"Floor {level}",150,FONTCOLOR,fade))
            fade -= .5
            if fade <= 0:
                messageBools["floorLevelMessage"] = False
                fade = 255
        elif messageBools["brokenSealMessage"]:
            gameWindow.blit(drawMessage("The Seal is Broken",150,FONTCOLOR,fade))
            fade -= .5
            if fade <= 0:
                fade = 255
                messageBools["brokenSealMessage"] = False
        if menuDict["menuOpen"]:
            DrawMenu(selectItemIndex,gameWindow)
        
        
        win.blit(gameWindow,(LEFTPANELWIDTH,0))
        win.blit(leftPanel,(0,0))
        win.blit(rightPanel,(LEFTPANELWIDTH+WIDTH,0))
        win.blit(bottomPanel,(LEFTPANELWIDTH,HEIGHT))
        change = False

    pygame.display.flip()


    pygame.display.update()
# except Exception as e:
#     with open("log.txt","a") as file:
#         file.write(str(e))
