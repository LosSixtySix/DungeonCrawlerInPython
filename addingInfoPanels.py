
import pygame
import pygame.freetype
import random as rand
import connectingEmptyRooms as CER

pygame.init()
pygame.font.init()

WIDTH = 720
HEIGHT = 720
SCREENWIDTH = 1000
SCREENHEIGHT = 1000

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

CharacterStatistics = {"Health":90,"AC":5,"Wall Damage":1}


def displayStatistics(stats):
    keys = stats.keys()

    font = pygame.font.Font('freesansbold.ttf',15)
    passes = 0

    for key in keys:
        text = font.render(f"{key}: {stats[key]}",True,blue,black)
        textRect = text.get_rect()
        textWidth = text.get_width()
        textRect.center = (TEXTSTARTWIDTH + int(textWidth/2), TEXTSTARTHEIGHT + (TEXTROWGAPDISTANCE * passes))
        win.blit(text, textRect)
        passes += 1

win = pygame.display.set_mode((SCREENWIDTH,SCREENHEIGHT))




playerposx = 35
playerposy = 25
playerpos = (playerposx, playerposy)
playervel = 1

playerDirection = 0

grid = [[0 for i in range(int(WIDTH/10))] for j in range(int(HEIGHT/10))]

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

emptyNodes = CER.createNodes(grid)




runing = True
while runing:
    
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

    displayStatistics(CharacterStatistics)
    for x in range(len(grid)):
        for y in range(len(grid[x])):
            if grid[x][y] == 2:
                pygame.draw.rect(win,blue,pygame.Rect(x*10,y*10,10,10))
            if grid[x][y] == 1:
                pygame.draw.rect(win,green,pygame.Rect(x*10,y*10,10,10))
    
    
    pygame.display.flip()


    pygame.display.update()
