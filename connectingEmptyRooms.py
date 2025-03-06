

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

    if grid[x][y-1] == 2 and grid[x][y+1] == 2 and grid[x-1][y] == 2 and grid[x+1][y] == 2:
        return True
    return False

def CheckAdjacency(positionOne,positionTwo):
    if positionOne[0] +1 == positionTwo[0] or positionOne[0] -1 == positionTwo[0]:
        return True
    if positionOne[1] +1 == positionTwo[1] or positionTwo[1] -1 == positionTwo[1]:
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


def CreateNode(emptySpots, node):
    for index in range(len(emptySpots)):
        if noAdjacency(emptySpots[index]):
            node.append(emptySpots[index])
            emptySpots.remove(emptySpots[index])
            return
        else:
            for index2 in range(len(emptySpots)):
                if emptySpots[index] != emptySpots[index2]:
                    if CheckAdjacency(emptySpots[index],emptySpots[index2]):
                        node.append(emptySpots[index2])
            node.append(emptySpots[index])

#def CreateNode(emptySpots, currentPosition):
#    node = []
#    for spot in emptySpots:
#        if CheckAdjacency(spot,currentPosition):
#            node.append(spot)
#    node.append(currentPosition)
#    return node


                
def mergeNodes(nodeOne,nodeTwo):
    for position in nodeTwo:
        nodeOne.append(position)
    return nodeOne

def createNodes(grid):
    emptySpots = findEmptySpots(grid)
    nodes = []

    for spot in emptySpots:
        node = []
        CreateNode(emptySpots, node)

    return nodes

createNodes(grid)


#emptyNodes = getEmptyNodes(emptyPockets,grid)



#consoleVersionOfGrid = []

#for x in range(len(grid)):
#    row = ""
#    for y in range(len(grid[x])):
#        row += str(grid[x][y])
#    consoleVersionOfGrid.append(row)

#for x in consoleVersionOfGrid:
#    print(x)