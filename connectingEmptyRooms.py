


grid = [[2 for i in range(10)] for j in range(10)]


grid[0][0] = 0

grid[2][3] = 0
grid[2][4]= 0
grid[2][5] = 0
grid[2][6]= 0



def findEmptySpots(grid):
    listOfEmptySpots = []
    for x in range(len(grid)):
        for y in range(len(grid[x])):
            if grid[x][y] == 0:
                listOfEmptySpots.append((x,y))
    return listOfEmptySpots


def LookForEdges(position,listOfEdges,grid):
    if position[0] < len(grid) and position[1] < len(grid[0]):
        if grid[position[0]][position[1] -1] == 2:
            listOfEdges.append((position[0],position[1]))
        else:
            LookForEdges((position[0],position[1]-1),listOfEdges,grid)
        if grid[position[0]][position[1] +1] == 2:
            listOfEdges.append((position[0],position[1]))
        else:
            LookForEdges((position[0],position[1]+1),listOfEdges,grid)
        if grid[position[0]-1][position[1]] == 2:
            listOfEdges.append((position[0],position[1]))
        else:
            LookForEdges((position[0] -1,position[1]),listOfEdges,grid)
        if grid[position[0]+1][position[1]] == 2:
            listOfEdges.append((position[0],position[1]))
        else:
            LookForEdges((position[0]+1,position[1]),listOfEdges,grid)
        
def removeDuplicates(listOfPositions):
    newList = []
    currentValue = listOfPositions[0]
    isInList = False
    for x in listOfPositions:
        if currentValue != x:
            currentValue = x
            for val in newList:
                if val == x:
                    isInList = True
                    break
            if isInList == False:
                newList.append(x)
    isInList = False
    for val in newList:
        if val == currentValue:
            isInList = True
            break
    if isInList == False:
        newList.append(currentValue)
    return newList


def getEdgesOfEmptyNodes(emptySpots, grid):
    emptyNodes = []
    for emptyPosition in emptySpots:
        edges = []
        LookForEdges(emptyPosition,edges,grid)
        edges = removeDuplicates(edges)
        emptyNodes.append(edges)
    return emptyNodes





emptyPockets = findEmptySpots(grid)
emptyNodes = getEdgesOfEmptyNodes(emptyPockets,grid)



consoleVersionOfGrid = []

for x in range(len(grid)):
    row = ""
    for y in range(len(grid[x])):
        row += str(grid[x][y])
    consoleVersionOfGrid.append(row)

for x in emptyNodes:
    print(x)