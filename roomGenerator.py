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

playerposx = 200
playerposy = 250
playerpos = (playerposx, playerposy)
wallpos = (playerposx, playerposy-10)
playervel = 10

grid[playerposx][playerposy] = 2
grid[playerposx][playerposy-20] = 2


runing = True
font2 = pygame.font.SysFont("timesnewroman",20)
font = pygame.font.SysFont("timesnewroman",10)
text = font.render('@',True,white,black)
wall = font2.render('-',True,white,black)


print(map)


while runing:
    
    pygame.time.delay(100)
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            runing = False



    keys = pygame.key.get_pressed()




    win.fill((black))
    for x in range(len(grid)):
        for y in range(len(grid[x])):
            if grid[x][y] == 2:
                win.blit(wall,(x,y))


    pygame.display.update()

