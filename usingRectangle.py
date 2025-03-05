import pygame
import pygame.freetype

pygame.init()
pygame.font.init()

WIDTH = 720
HEIGHT = 720

roomLoaded = 0
loadRoom = True

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
else:
    wallStartx = 30
    wallstarty = 30

    grid[wallStartx][wallstarty] = 2
    grid[wallStartx][wallstarty- 2] = 2


win = pygame.display.set_mode((WIDTH,HEIGHT))

white = (255, 255, 255) 
green = (0, 255, 0) 
blue = (0, 0, 128) 
black = (0, 0, 0)


playerposx = 35
playerposy = 25
playerpos = (playerposx, playerposy)
playervel = 1


runing = True
while runing:
    
    pygame.time.delay(100)
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            runing = False

    keys = pygame.key.get_pressed()

    if keys[pygame.K_LEFT]:
        if grid[playerposx - playervel][playerposy] != 2:
            grid[playerposx][playerposy] = 0
            playerposx -= playervel
            print("left")
    if keys[pygame.K_RIGHT]:
        if grid[playerposx + playervel][playerposy] != 2:
            grid[playerposx][playerposy] = 0
            playerposx += playervel
            print("right")
    if keys[pygame.K_UP]:
        if grid[playerposx][playerposy- playervel] != 2:
            grid[playerposx][playerposy] = 0
            playerposy -= playervel
            print("up")
    if keys[pygame.K_DOWN]:
        if grid[playerposx][playerposy+ playervel] != 2:
            grid[playerposx][playerposy] = 0
            playerposy += playervel
            print("down")

    playerpos = (playerposx,playerposy)
    grid[playerposx][playerposy] = 1

    
    win.fill((black))
    for x in range(len(grid)):
        for y in range(len(grid[x])):
            if grid[x][y] == 2:
                pygame.draw.rect(win,blue,pygame.Rect(x*10,y*10,10,10))
            if grid[x][y] == 1:
                pygame.draw.rect(win,green,pygame.Rect(x*10,y*10,10,10))
    
    
    pygame.display.flip()


    pygame.display.update()

