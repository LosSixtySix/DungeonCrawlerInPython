import random as rand
import pygame as py
import math
def createNodes(grid,rowLength,radius):
    usedPoints = set()
    nodes = []

    points = list(grid.keys())

    while len(points) > 0:
        point = points.pop(rand.randint(0,len(points)-1))

        if point not in usedPoints:
            node = getCirclePoints(point,radius,grid,rowLength,usedPoints)
            usedPoints = node.union(usedPoints)
            nodes.append(node)
    return nodes

def getCirclePoints(position,radius,grid,rowLength,usedPoints) -> set:
    oPoints = set()
    positions = set()
    h = position%rowLength
    k = int((position-h)/rowLength)
    for r in range(0,radius+1):
        t = 0
        while t < 2*math.pi:
            x = (r*math.cos(t) + h)
            y = (r*math.sin(t) + k)
            oPoints.add((round(x),round(y)))
            t += .1
    for p in oPoints:
        flattened = (p[0]+(p[1]*rowLength))
        if flattened in grid.keys() and flattened not in usedPoints:
            positions.add(flattened)
    return positions


def getNNeighbors(point,keys,radius,rowlength) -> set:
    neighborsInRadius = set()
    neighborsInRadius.add(point)

    for x in range(1,radius+1):
        corners = set()
        rowValues = set()
        columnValues = set()

        corners.add(point - (x * rowlength) -x)
        corners.add(point - (x* rowlength) +x)
        corners.add(point + (x*rowlength) -x)
        corners.add(point + (x*rowlength) +x)

        rowValues.add(point -x)
        rowValues.add(point +x)

        columnValues.add(point - (x*rowlength))
        columnValues.add(point + (x*rowlength))

        for i in corners:
            if i in keys:
                neighborsInRadius.add(i)

        for i in rowValues:
            if i in keys and int(i/rowlength) == int(point/rowlength):
                neighborsInRadius.add(i)

        for i in columnValues:
            if i in keys and point%rowlength == i%rowlength:
                neighborsInRadius.add(i)
    return neighborsInRadius
if __name__ == "__main__":
    py.init()
    win = py.display.set_mode((0,0))
    SCREENWIDTH, SCREENHEIGHT = win.get_size()
    WIDTH = SCREENWIDTH
    HEIGHT = SCREENHEIGHT
    
    tileSize = 10
    numberOfSpots = int(WIDTH/tileSize) * int(HEIGHT/tileSize)

    ROWLENGHTH = int(WIDTH/tileSize)

    grid = {}
    
    for i in range(numberOfSpots):
        grid[i] = [0,0]

    createNodes(grid,ROWLENGHTH,50)
