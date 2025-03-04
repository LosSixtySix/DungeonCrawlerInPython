import pygame

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

playerposx = 350
playerposy = 250
playerpos = (playerposx, playerposy)
wallpos = (playerposx, playerposy-10)
playervel = 10

grid[playerposx][playerposy -10] = 2


runing = True
font2 = pygame.font.SysFont("timesnewroman",20)
font = pygame.font.SysFont("timesnewroman",16)
text = font.render('@',True,white,black)
wall = font2.render('*',True,white,black)



print(map)

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
    win.blit(wall, wallpos)
    win.blit(text,playerpos)
    pygame.display.update()

