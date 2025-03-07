

WIDTH = 720
HEIGHT = 720
#grid = [[2 for i in range(10)] for j in range(10)]

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

grid2 = [[0 for i in range(12)] for j in range(3)]

for x in range(3):
    for y in range(12):
        grid2[x][y] = grid[x][y]

grid = grid2


def findEmptySpots(grid):
    listOfEmptySpots = []
    for x in range(len(grid)):
        for y in range(len(grid[x])):
            if grid[x][y] == 0:
                listOfEmptySpots.append((x,y))
    return listOfEmptySpots

def CheckIfEdge(position, grid):
    x = position[0]
    y = position[1]

    if grid[x][y-1] == 2:
        return True
    if grid[x][y+1] == 2:
        return True
    if grid[x-1][y] == 2:
        return True
    if grid[x+1][y] == 2:
        return True
    return False

def noAdjacency(position):
    x = position[0]
    y = position[1]

    if y == 0 and x == 0:
        if  grid[x][y+1] == 2 and grid[x+1][y] ==2:
            return True
    elif y == len(grid[x])-1 and x == len(grid) -1:
          if  grid[x][y-1] == 2 and grid[x-1][y] ==2:
            return True
    elif y == len(grid[x])-1 and x == 0:
        if  grid[x][y-1] == 2 and grid[x+1][y] ==2:
            return True
    elif x == len(grid)-1 and y == 0:
        if  grid[x][y+1] == 2 and grid[x-1][y] ==2:
            return True
    else:
        if x == 0:
            if grid[x][y-1] == 2 and grid[x][y+1] == 2 and grid[x+1][y] ==2:
                return True
        elif x == len(grid)-1:
            if grid[x][y-1] == 2 and grid[x][y+1] == 2 and grid[x-1][y] ==2:
                return True
        elif y == 0:
            if grid[x-1][y] == 2 and grid[x][y+1] == 2 and grid[x+1][y] ==2:
                return True
        elif y == len(grid[x])-1:
            if grid[x][y-1] == 2 and grid[x-1][y] == 2 and grid[x+1][y] ==2:
                return True
        else:
            if grid[x][y-1] == 2 and grid[x][y+1] == 2 and grid[x-1][y] == 2 and grid[x+1][y] == 2:
                return True
    return False

def CheckAdjacency(positionOne,positionTwo):
    if positionOne[0] +1 == positionTwo[0] or positionOne[0] -1 == positionTwo[0]:
        if positionOne[1] +1 == positionTwo[1] or positionOne[1] -1 == positionTwo[1]:
            return True
    if positionOne[1] +1 == positionTwo[1] or positionOne[1] -1 == positionTwo[1]:
        if positionOne[0] +1 == positionTwo[0] or positionOne[0] -1 == positionTwo[0]:
            return True
    return False

def CheckAdjacentNode(nodeOne,nodeTwo):
    for positionOne in nodeOne:
        for positionTwo in nodeTwo:
            if positionOne == positionTwo:
                return True
            if CheckAdjacency(positionOne,positionTwo):
                return True
    return False

         
def mergeNodes(nodeOne,nodeTwo):
    for position in nodeTwo:
        nodeOne.append(position)
    return nodeOne

def createNodes(grid):
    emptySpots = findEmptySpots(grid)
    nodes = []
    spotOne = 0
    spotTwo = 0
    if len(emptySpots) > 1:
        spotOne = emptySpots.pop(0)
        spotTwo = emptySpots.pop(0)
        notOdd = True
        foundSpotOneAdjacency = False
        foundSpotTwoAdjacency = False
        while(len(emptySpots) > 0):
            if notOdd == False:
                spotOne = emptySpots.pop()
            if notOdd:
                foundSpotOneAdjacency = False
                foundSpotTwoAdjacency = False
            if noAdjacency(spotOne):
                nodes.append([spotOne])
                if len(emptySpots) > 0:
                    spotOne = emptySpots.pop(0)
            if noAdjacency(spotTwo):
                nodes.append([spotTwo])
                if len(emptySpots) > 0:
                    spotTwo = emptySpots.pop(0)

            if len(nodes) == 0:
                if CheckAdjacency(spotOne,spotTwo):
                    nodes.append([spotOne,spotTwo])
                    if len(emptySpots) > 1:
                        spotOne = emptySpots.pop(0)
                        spotTwo = emptySpots.pop(0)
                else:
                    emptySpots.append(spotTwo)
                    if len(emptySpots > 1):
                        spotTwo = emptySpots.pop(0)
                    else:
                        nodes.append(emptySpots.pop())
            elif len(nodes) > 0:
                for index in range(len(nodes)):
                    for position in nodes[index]:
                        if CheckAdjacency(spotOne, position) and foundSpotOneAdjacency == False:
                            nodes[index].append(spotOne)
                            if len(emptySpots) > 0:
                                spotOne = emptySpots.pop(0)
                                foundSpotOneAdjacency = True
                        if CheckAdjacency(spotTwo,position) and foundSpotTwoAdjacency == False:
                            nodes[index].append(spotTwo)
                            if len(emptySpots)> 0:
                                spotTwo = emptySpots.pop(0)
                                foundSpotTwoAdjacency = True
                        if foundSpotOneAdjacency and foundSpotTwoAdjacency:
                            break
            if foundSpotOneAdjacency == False and foundSpotTwoAdjacency == False:
                if CheckAdjacency(spotOne,spotTwo):
                    nodes.append([spotOne,spotTwo])
                    if len(emptySpots) > 1:
                        spotOne = emptySpots.pop(0)
                        spotTwo = emptySpots.pop(0)
                    elif len(emptySpots) > 0:
                        spotOne = emptySpots.pop(0)
                        emptySpots.append(spotOne)
                else:
                    nodes.append([spotOne])
                    nodes.append([spotTwo])
                    if len(emptySpots) >1:
                        spotOne = emptySpots.pop(0)
                        spotTwo = emptySpots.pop(0)
                    elif len(emptySpots) > 0:
                        spotOne = emptySpots.pop(0)
                        emptySpots.append(spotOne)
            if foundSpotOneAdjacency and foundSpotTwoAdjacency:
                if CheckAdjacency(spotOne, spotTwo):
                    if len(emptySpots) == 0:
                        nodes.append([spotOne,spotTwo])
                    elif len(emptySpots) == 1:
                        spotThree = emptySpots.pop()
                        if CheckAdjacency(spotOne,spotThree) or CheckAdjacency(spotTwo,spotThree):
                            nodes.append([spotOne,spotTwo,spotThree])
                        else:
                            nodes.append([spotOne,spotTwo])
                            spotOne = spotThree
                            emptySpots.append(spotOne)
                            foundSpotOneAdjacency = False

    else:
        nodes.append(emptySpots.pop())
    return nodes

nodes = createNodes(grid)

print(nodes[0])

consoleVersionOfGrid = []

for x in range(len(grid)):
    row = ""
    for y in range(len(grid[x])):
        row += str(grid[x][y])
    consoleVersionOfGrid.append(row)

for x in consoleVersionOfGrid:
    print(x)