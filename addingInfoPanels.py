
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

TEXTSTARTWIDTH = 732
TEXTSTARTHEIGHT = 15

TEXTROWGAPDISTANCE = 20

roomLoaded = 0
loadRoom = True
generateRoom = False
saveMap = False

white = (255, 255, 255) 
green = (0, 255, 0) 
blue = (0, 0, 128) 
black = (0, 0, 0)

player = pc.PlayerClass()





def displayStatistics(stats,startHeight):
    keys = stats.keys()

    font = pygame.font.Font('freesansbold.ttf',15)
    passes = 0
    
    for key in keys:
        if isinstance(stats[key], list):
            if stats[key][0] == 3: #number 3 in a list for the grid means a list of items.
                for item in stats[key]:
                    if item == 3:
                        text = font.render("Items in Room:",True,blue,black)
                        textRect = text.get_rect()
                        textWidth = text.get_width()
                        textRect.center = (TEXTSTARTWIDTH + int(textWidth/2), startHeight + (TEXTROWGAPDISTANCE * passes))
                        win.blit(text, textRect)
                        passes += 1
                    else:
                        text = font.render(f"{getItem(item)}",True,blue,black)
                        textRect = text.get_rect()
                        textWidth = text.get_width()
                        textRect.center = (TEXTSTARTWIDTH + int(textWidth/2) + 10, startHeight + (TEXTROWGAPDISTANCE * passes))
                        win.blit(text, textRect)
                        passes += 1
        else:
            text = font.render(f"{key}: {stats[key]}",True,blue,black)
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

def getItem(itemId):
    if itemId == 4:
        return "Sword"

if loadRoom:
    openMapFile = open("savedMaps.txt",'r')
    MapListFromTxt = openMapFile.readlines()
    openMapFile.close()
    MapListFromTxt = MapListFromTxt[0].split(',')

    startIndexForMapText = 0


    for x in range(len(grid)):
        for y in range(len(grid[x])):
            grid[x][y]=int(MapListFromTxt[startIndexForMapText])
            startIndexForMapText += 1
elif generateRoom:
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


emptyNodes = CER.createNodes(grid)
rooms = CreateRooms(emptyNodes)

ItemsGrid = copy.deepcopy(grid)
convertToItemGrid(ItemsGrid)

print(ItemsGrid[playerposx][playerposy])

addItem(ItemsGrid,playerpos,4)


runing = True
while runing:
    
    roomType = getRoomType(playerpos,rooms)
    roomItems = getItemsFromGrid(ItemsGrid,playerpos)

    CharacterStatistics = {"Health":player.hp,"AC":player.ac,"Wall Damage":player.wallDamage}
    RoomStatistics = {"Room Type":roomType, "Items in Room":roomItems}
    pygame.time.delay(100)
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            if saveMap:
                f = open("savedMaps.txt","w")   
                for x in range(len(grid)):
                    for y in range(len(grid[x])):
                        if x == 0 and y == 0:
                            f.write(f"{grid[x][y]}")
                        elif x == len(grid) -1 and y == len(grid[0]) -1:
                            f.write(f",{grid[x][y]}\n")
                        else:
                            f.write(f",{grid[x][y]}")

            runing = False

    keys = pygame.key.get_pressed()
    
    if keys[pygame.K_e]:
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


    if keys[pygame.K_LEFT]:
        playerDirection = 0
        if playerposx - 1 >= 0:
            if grid[playerposx - playervel][playerposy] != 2:
                grid[playerposx][playerposy] = 0
                playerposx -= playervel
                print("left")
    if keys[pygame.K_RIGHT]:
        playerDirection = 1
        if playerposx + 1 < int(WIDTH/10):
            if grid[playerposx + playervel][playerposy] != 2:
                grid[playerposx][playerposy] = 0
                playerposx += playervel 
                print("right")
    if keys[pygame.K_UP]:
        playerDirection = 2
        if playerposy - 1 >= 0:
            if grid[playerposx][playerposy- playervel] != 2:
                grid[playerposx][playerposy] = 0
                playerposy -= playervel
                print("up")
    if keys[pygame.K_DOWN]:
        playerDirection = 3
        if playerposy + 1 < int(HEIGHT/10):
            if grid[playerposx][playerposy+ playervel] != 2:
                grid[playerposx][playerposy] = 0
                playerposy += playervel
                print(playerposy)

    playerpos = (playerposx,playerposy)
    grid[playerposx][playerposy] = 1

    
    win.fill((black))

    TextHeightIncrement = displayStatistics(CharacterStatistics,TEXTSTARTHEIGHT)
    displayStatistics(RoomStatistics,TEXTSTARTHEIGHT + TextHeightIncrement)

    for x in range(len(grid)):
        for y in range(len(grid[x])):
            if grid[x][y] == 2:
                pygame.draw.rect(win,blue,pygame.Rect(x*10,y*10,10,10))
            if grid[x][y] == 1:
                pygame.draw.rect(win,green,pygame.Rect(x*10,y*10,10,10))
    
    
    pygame.display.flip()


    pygame.display.update()
