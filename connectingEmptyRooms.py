


grid = [[2 for i in range(10)] for j in range(10)]


grid[0][0] = 0

grid[2][3]= 0
grid[2][4]= 0
grid[2][5]= 0
grid[2][6]= 0
grid[3][6] =0
grid[4][6] =0
grid[3][5] =0
grid[4][5] =0
grid[3][4] =0
grid[4][4] =0



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
def CheckDuplicatePosition(NodeOne,NodeTwo):
    for positionOne in NodeOne:
        for positionTwo in NodeTwo:
            if positionOne == positionTwo:
                return True
    return False


def LookForEdges(position,listOfEdges,grid):
    if CheckIfEdge(position, grid):
        listOfEdges.append(position)
        
def removeDuplicates(listOfPositions):
    if len(listOfPositions) != 0:
        for position in listOfPositions:
            for positionTwo in listOfPositions:
                if position == positionTwo:
                    while(position in listOfPositions):
                        listOfPositions.remove(position)
                    listOfPositions.append(position)

def CreateNode(emptySpots, currentPosition):
    node = []
    for spot in emptySpots:
        if CheckAdjacency(spot,currentPosition):
            node.append(spot)
    node.append(currentPosition)
    return node

def getEmptyNodes(emptySpots, grid):
    emptyNodes = []



    for emptyPosition in emptySpots:
        edges = []
        LookForEdges(emptyPosition,edges,grid)
        edges = removeDuplicates(edges)
        emptyNodes.append(edges)
    return emptyNodes


def detectDuplicatesInNodes(nodes):
    for nodeOne in nodes:
        for nodeTwo in nodes:
            if nodeOne == nodeTwo:
                pass
            else:
                if CheckDuplicatePosition(nodeOne,nodeTwo):
                    return True
                
def mergeNodes(nodeOne,nodeTwo):
    for position in nodeTwo:
        nodeOne.append(position)
    return nodeOne

emptyPockets = findEmptySpots(grid)
nodes = []

for x in emptyPockets:
    node = CreateNode(emptyPockets, x)
    nodes.append(node)


while(detectDuplicatesInNodes(nodes)):
    for nodeOne in nodes:
        for nodeTwo in nodes:
            if nodeOne == nodeTwo:
                pass
            else:
                if CheckAdjacentNode(nodeOne,nodeTwo):
                    mergedNode = mergeNodes(nodeOne,nodeTwo)
                    nodes.remove(nodeOne)
                    nodes.remove(nodeTwo)
                    nodes.append(mergedNode)

for node in nodes:
    removeDuplicates(node)
    print(node)



#emptyNodes = getEmptyNodes(emptyPockets,grid)



consoleVersionOfGrid = []

for x in range(len(grid)):
    row = ""
    for y in range(len(grid[x])):
        row += str(grid[x][y])
    consoleVersionOfGrid.append(row)

for x in consoleVersionOfGrid:
    print(x)