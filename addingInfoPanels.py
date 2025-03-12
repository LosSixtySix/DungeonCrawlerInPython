
import pygame
import pygame.freetype
import random as rand
import connectingEmptyRooms as CER
import playerClass as pc
import copy

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

menuOptions = {"Load Room":True,"Generate Room":False, "Save on Exit":False}


white = (255, 255, 255) 
green = (0, 255, 0) 
blue = (0, 0, 128) 
black = (0, 0, 0)

player = pc.PlayerClass()

FONT = pygame.font.Font('freesansbold.ttf',15)



def displayStatistics(stats,startHeight,selectItem,selectItemIndex):
    keys = stats.keys()

    
    selectItemIndex += 1
    passes = 0
    
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
                        text = FONT.render(f"{getItem(item)}",True,blue,black)
                        if passes == selectItemIndex and selectItem:
                            text = FONT.render(f"> {getItem(item)}",True,blue,black)
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
playerpos = (playerposx, playerposy)
playervel = 1

playerDirection = 0

grid = [[0 for i in range(int(WIDTH/10))] for j in range(int(HEIGHT/10))]


def convertToItemGrid(itemsGrid):
    for x in range(len(itemsGrid)):
        for y in range(len(itemsGrid[x])):
            itemsGrid[x][y] = [itemsGrid[x][y]]



def addItem(itemsGrid, position, item):
    x = position[0]
    y = position[1]

    if itemsGrid[x][y][0] != 2:
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

def getItem(itemId):
    if itemId == 4:
        return "Sword"

if menuOptions["Load Room"]:
    openMapFile = open("savedMaps.txt",'r')
    MapListFromTxt = openMapFile.readlines()
    openMapFile.close()
    MapListFromTxt = MapListFromTxt[0].split(',')

    startIndexForMapText = 0


    for x in range(len(grid)):
        for y in range(len(grid[x])):
            grid[x][y]=int(MapListFromTxt[startIndexForMapText])
            startIndexForMapText += 1
elif menuOptions["Generate Room"]:
    for x in range(len(grid)):
        for y in range(len(grid[x])):
            isWall = rand.randint(0,1)
            if isWall == 1:
                grid[x][y] = 2
else:
    wallStartx = 30
    wallstarty = 30

    grid[wallStartx][wallstarty] = 2
    grid[wallStartx][wallstarty- 2] = 2

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

def getRoomType(playerpos,rooms):
    keys = rooms.keys()

    for key in keys:
        for node in rooms[key]:
            for pos in node:
                if pos == playerpos:
                    return key
            
def gameRunning(menuOpen,selectItem):
    if menuOpen:
        return False
    if selectItem:
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

emptyNodes = CER.createNodes(grid)
rooms = CreateRooms(emptyNodes)

ItemsGrid = copy.deepcopy(grid)
convertToItemGrid(ItemsGrid)

print(ItemsGrid[playerposx][playerposy])

addItem(ItemsGrid,playerpos,4)
addItem(ItemsGrid,playerpos,4)
addItem(ItemsGrid,playerpos,4)
addItem(ItemsGrid,playerpos,4)

menuOpen = True
selectItem = False
selectItemIndex = 1
runing = True
while runing:
    
    roomType = getRoomType(playerpos,rooms)
    roomItems = getItemsFromGrid(ItemsGrid,playerpos)

    CharacterStatistics = {"Health":player.hp,"AC":player.ac,"Wall Damage":player.wallDamage}
    RoomStatistics = {"Room Type":roomType, "Items in Room":roomItems}
    pygame.time.delay(100)
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            if menuOptions["Save on Exit"]:
                f = open("savedMaps.txt","a")   
                for x in range(len(grid)):
                    for y in range(len(grid[x])):
                        if x == 0 and y == 0:
                            f.write(f"{grid[x][y]}")
                        elif x == len(grid) -1 and y == len(grid[0]) -1:
                            f.write(f",{grid[x][y]}\n")
                        else:
                            f.write(f",{grid[x][y]}")

            runing = False

    KEYS = pygame.key.get_pressed()
    
    if KEYS[pygame.K_RETURN]:
        if selectItem == False and menuOpen == False:
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
        else:
            pass
    
    if KEYS[pygame.K_ESCAPE]:
        if menuOpen:
            menuOpen = False
            selectItemIndex = 1
        else:
            menuOpen = True

    if KEYS[pygame.K_q]:
        if selectItem:
            selectItem = False
            selectItemIndex = 1
        if menuOpen:
            menuOpen = False
            selectItemIndex = 1

    if gameRunning(selectItem,menuOpen):
        if KEYS[pygame.K_e]:
            if playerDirection == 0:
                if playerposx - 1 >= 0:
                    if grid[playerposx - 1][playerposy] == 2:
                        grid[playerposx - 1][playerposy] = 0
            elif playerDirection == 1:
                if playerposx + 1 < int(WIDTH/10):
                    if grid[playerposx + 1][playerposy] == 2:
                        grid[playerposx + 1][playerposy] = 0
            elif playerDirection == 2:
                if playerposy - 1 >= 0:
                    if grid[playerposx][playerposy - 1] == 2:
                        grid[playerposx][playerposy - 1] = 0
            elif playerDirection == 3:
                if playerposy + 1 < int(HEIGHT/10):
                    if grid[playerposx][playerposy + 1] == 2:
                        grid[playerposx][playerposy + 1] = 0

    
    if KEYS[pygame.K_LEFT]:
        if gameRunning(selectItem,menuOpen):
            playerDirection = 0
            if playerposx - 1 >= 0:
                if grid[playerposx - playervel][playerposy] != 2:
                    grid[playerposx][playerposy] = 0
                    playerposx -= playervel
    if KEYS[pygame.K_RIGHT]:
        if gameRunning(selectItem,menuOpen):
            playerDirection = 1
            if playerposx + 1 < int(WIDTH/10):
                if grid[playerposx + playervel][playerposy] != 2:
                    grid[playerposx][playerposy] = 0
                    playerposx += playervel 
    if KEYS[pygame.K_UP]:
        if gameRunning(selectItem,menuOpen):
            playerDirection = 2
            if playerposy - 1 >= 0:
                if grid[playerposx][playerposy- playervel] != 2:
                    grid[playerposx][playerposy] = 0
                    playerposy -= playervel
        else:
            if selectItem:
                if selectItemIndex - 1 > 0:
                    selectItemIndex -=1
            elif menuOpen:
                if selectItemIndex - 1 > 0:
                    selectItemIndex -= 1
    if KEYS[pygame.K_DOWN]:
        if gameRunning(selectItem,menuOpen):
            playerDirection = 3
            if playerposy + 1 < int(HEIGHT/10):
                if grid[playerposx][playerposy+ playervel] != 2:
                    grid[playerposx][playerposy] = 0
                    playerposy += playervel
        else:
            if selectItem:
                if selectItemIndex + 1 < len(roomItems):
                    selectItemIndex +=1
            elif menuOpen:
                if selectItemIndex +1 <= len(menuOptions.keys()):
                    selectItemIndex +=1

    playerpos = (playerposx,playerposy)
    grid[playerposx][playerposy] = 1

    
    win.fill((black))


    

    TextHeightIncrement = displayStatistics(CharacterStatistics,TEXTSTARTHEIGHT,selectItem,selectItemIndex)
    displayStatistics(RoomStatistics,TEXTSTARTHEIGHT + TextHeightIncrement,selectItem,selectItemIndex)

    for x in range(len(grid)):
        for y in range(len(grid[x])):
            if grid[x][y] == 2:
                pygame.draw.rect(win,blue,pygame.Rect(x*10,y*10,10,10))
            if grid[x][y] == 1:
                pygame.draw.rect(win,green,pygame.Rect(x*10,y*10,10,10))
    if menuOpen:
        DrawMenu(selectItemIndex)
    
    pygame.display.flip()


    pygame.display.update()
