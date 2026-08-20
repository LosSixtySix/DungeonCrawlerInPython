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

print(rayCircleVision(25,2,grid))