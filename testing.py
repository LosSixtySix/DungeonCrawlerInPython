WIDTH = 720
HEIGHT = 720
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


def simpleTest(limit,returnVal = 0):

    if returnVal != limit:
        returnVal += simpleTest(limit - 1, returnVal)
    return returnVal



def stepsToEmptyTile(position,grid,direction):
    steps = 0
    x = position[0]
    y = position[1]
    if direction == 0:
        if y - 1 > 0:
            if grid[x][y-1] != 0:
                steps += stepsToEmptyTile((x,y-1),grid,direction)
            return steps +1
        return steps
    if direction == 1:
        if y + 1 < len(grid[x]):
            if grid[x][y+1] != 0:
                steps += stepsToEmptyTile((x,y+1),grid,direction)     
            return steps +1
        return steps
    if direction == 2:
        if x -1 > 0:
            if grid[x-1][y] != 0:
                steps += stepsToEmptyTile((x-1,y),grid,direction)   
            return steps +1
        return steps        
    if direction == 3:
        if x + 1 < len(grid):
            if grid[x+1][y] != 0:
                steps += stepsToEmptyTile((x+1,y),grid,direction)   
            return steps +1
        return steps     
    return steps
    
def getNearestEmptyTile(position,grid):
    upSteps = stepsToEmptyTile(position,grid,0)
    downSteps = stepsToEmptyTile(position,grid,1)
    rightSteps = stepsToEmptyTile(position,grid,2)
    leftSteps = stepsToEmptyTile(position,grid,3)

    print(upSteps,downSteps,rightSteps,leftSteps)

    if (upSteps != 0 or downSteps !=0 or rightSteps !=0 or leftSteps !=0):
        if upSteps <= downSteps and upSteps != 0:
            if rightSteps <= leftSteps and rightSteps !=0:
                if upSteps <=rightSteps:
                    return (position[0],position[1] - upSteps)
                else:
                    return (position[0] - rightSteps,position[1])
            else:
                if upSteps <= leftSteps and leftSteps !=0:
                    return(position[0],position[1]-upSteps)
                else:
                    return (position[0] + leftSteps, position[1])
        else:
            if downSteps > 0:
                if rightSteps <= leftSteps and rightSteps !=0:
                    if downSteps <= rightSteps:
                        return(position[0],position[1] + downSteps)
                    else:
                        return(position[0] - rightSteps,position[1])
                elif leftSteps <= downSteps and leftSteps !=0:
                    return(position[0] + leftSteps,position[1])
                else:
                    return (position[0], position[1] + downSteps)
            else:
                if rightSteps <= leftSteps and rightSteps !=0:
                    return(position[0] - rightSteps,position[1])
                return(position[0] + leftSteps,position[1])
    return position
grid[3][2] = 2
print(getNearestEmptyTile((65,9),grid))