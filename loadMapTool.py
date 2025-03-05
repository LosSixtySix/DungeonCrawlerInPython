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

openMapFile = open("savedMaps.txt",'r')
MapListFromTxt = openMapFile.readlines()
openMapFile.close()
MapListFromTxt = MapListFromTxt[0].split(',')

startIndexForMapText = 0


for x in range(len(grid)):
    for y in range(len(grid[x])):
        grid[x][y]=int(MapListFromTxt[startIndexForMapText])
        startIndexForMapText += 1

runing = True
while runing:
    

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            runing = False

    
    win.fill((black))
    for x in range(len(grid)):
        for y in range(len(grid[x])):
            if grid[x][y] == 2:
                pygame.draw.rect(win,blue,pygame.Rect(x*10,y*10,10,10))
    
    pygame.display.flip()


    pygame.display.update()
