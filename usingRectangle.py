import pygame
import pygame.freetype

pygame.init()
pygame.font.init()

WIDTH = 720
HEIGHT = 720

win = pygame.display.set_mode((WIDTH,HEIGHT))

white = (255, 255, 255) 
green = (0, 255, 0) 
blue = (0, 0, 128) 
black = (0, 0, 0)

grid = [[0 for i in range(WIDTH)] for j in range(HEIGHT)]

wallStartx = 300
wallstarty = 300


playerposx = 350
playerposy = 250
playerpos = (playerposx, playerposy)
wallpos = (playerposx, playerposy-10)
playervel = 10

grid[wallStartx][wallstarty] = 2
grid[wallStartx][wallstarty- 20] = 2


runing = True
while runing:
    
    pygame.time.delay(100)
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            runing = False

    keys = pygame.key.get_pressed()

    if keys[pygame.K_LEFT]:
        if grid[playerposx - playervel][playerposy] != 2:
            playerposx -= playervel
            print("left")
    if keys[pygame.K_RIGHT]:
        if grid[playerposx + playervel][playerposy] != 2:
            playerposx += playervel
            print("right")
    if keys[pygame.K_UP]:
        if grid[playerposx][playerposy- playervel] != 2:
            playerposy -= playervel
            print("up")
    if keys[pygame.K_DOWN]:
        if grid[playerposx][playerposy+ playervel] != 2:
            playerposy += playervel
            print("down")

    playerpos = (playerposx,playerposy)
    grid[playerposx][playerposy] = 1

    
    win.fill((black))
    for x in range(len(grid)):
        for y in range(len(grid[x])):
            if grid[x][y] == 2:
                pygame.draw.rect(win,blue,pygame.Rect(x,y,10,10))
    
    pygame.draw.rect(win,green,pygame.Rect(playerposx,playerposy,10,10))
    pygame.display.flip()


    pygame.display.update()

