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

grid = [[0 for i in range(int(WIDTH/10))] for j in range(int(HEIGHT/10))]



runing = True
while runing:
    

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
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

    mouse = pygame.mouse.get_pressed()
    mousePosition = pygame.mouse.get_pos()

    if mouse[0]:
        grid[int(mousePosition[0]/10)][int(mousePosition[1]/10)] = 2

    

    
    win.fill((black))
    for x in range(len(grid)):
        for y in range(len(grid[x])):
            if grid[x][y] == 2:
                pygame.draw.rect(win,blue,pygame.Rect(x*10,y*10,10,10))
    
    pygame.display.flip()


    pygame.display.update()

