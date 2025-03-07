def CheckAdjacency(positionOne,positionTwo):
    if positionOne[0] +1 == positionTwo[0] or positionOne[0] -1 == positionTwo[0]:
        return True
    if positionOne[1] +1 == positionTwo[1] or positionOne[1] -1 == positionTwo[1]:
        return True
    return False
positionOne = (0,2)
positionTwo = (0,1)

print(CheckAdjacency(positionOne,positionTwo))