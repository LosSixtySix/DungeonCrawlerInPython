import math

grid = {}
rowLength = 10
for i in range(100):
    grid[i] = [0,0]

def circleVision(position,visionRange) -> set:
    positions = set()
    original = set()
    a = position%rowLength
    b = int((position-a)/rowLength)
    for r in range(0,visionRange+1):
        t = 0
        while t < 2 * math.pi:
            x = (r*math.cos(t)) + a
            y = (r*math.sin(t)) + b
            original.add((round(x),round(y)))
            t += .1
    for p in original:
        positions.add((p[0]+(p[1]*rowLength)))
    return positions
def createARay(startPosition,targetPosition,rowLength):
    sX = startPosition%rowLength
    sY = int((startPosition-sX)/rowLength)

    tX = targetPosition%rowLength
    tY = int((targetPosition-tX)/rowLength)

    angle = math.atan2((tY-sY)/(tX-sX))
    distance = int(math.sqrt(((tX-sX)**2)+((tY-sY)**2)))

    ray = set()
    flatRays = set()
    for r in range(0,distance+1):
        x = (r*math.cos(angle) + sX)
        y = (r*math.sin(angle) + sY)

        ray.add((round(x),round(y)))

    for p in ray:
        flatRays.add(p[0]+(p[1]*rowLength))
    return flatRays

def getCirclePoints(position,range,grid) -> set:
    Lrays = []
    Frays = []
    positions = set()
    h = position%rowLength
    k = int((position-h)/rowLength)
    t = 0
    while t < 2 *math.pi:
        ray = []
        for r in range(0,range+1):
            x = (r*math.cos(t) + h)
            y = (r*math.sin(t) + k)
            point = (round(x),round(y))
            if point not in ray:
                ray.append(point)
        Lrays.append(ray)
        t += .1
    for r in Lrays:
        FRay = []
        for p in r:
            flatened = (p[0]+(p[1]*rowLength))
            if flatened in grid.keys():
                FRay.append(flatened)
        Frays.append(FRay)
    return positions
        

def rayCircleVision(position,visionRange,grid) -> set:
    Lrays = []
    Frays = []
    positions = set()
    h = position%rowLength
    k = int((position-h)/rowLength)
    t = 0
    while t < 2 *math.pi:
        ray = []
        for r in range(0,visionRange+1):
            x = (r*math.cos(t) + h)
            y = (r*math.sin(t) + k)
            point = (round(x),round(y))
            if point not in ray:
                ray.append(point)
        Lrays.append(ray)
        t += .1
    for r in Lrays:
        FRay = []
        for p in r:
            flatened = (p[0]+(p[1]*rowLength))
            if flatened in grid.keys():
                FRay.append(flatened)
        Frays.append(FRay)
    for r in Frays:
        for p in r:
            if grid[p][0] == 0:
                positions.add(p)
            else:
                positions.add(p)
                break
    return positions

def createARayBresenham(startPosition,targetPosition,rowLength):
    sX = startPosition%rowLength
    sY = int((startPosition-sX)/rowLength)

    tX = startPosition%rowLength
    tY = int((startPosition-tX)/rowLength)

    slope = 2 * (tY-sY)
    slopeError = slope - (tX-sX)

    pointsInLineCart = set()

    for x in range(sX,tX+1):
        pointsInLineCart.add((x,sY))

        slopeError = slopeError + slope

        if (slopeError >= 0):
            sY += 1
            slopeError = slopeError -(2*(tX-sX))

    pointsInLineFlat = set()

    for p in pointsInLineCart:
        pointsInLineFlat.add(int(p[0] + (p[1]*rowLength)))

    return pointsInLineFlat


for x in range(1,100):

    print(f"{x}: {int(((x**5 - x**(4.99999999))+100 +x) *2)}")