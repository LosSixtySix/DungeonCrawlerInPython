WIDTH = 720
HEIGHT = 720

grid = [[0 for i in range(int(WIDTH/10))] for j in range(int(HEIGHT/10))]
ItemsGrid = grid

def convertToItemGrid(itemsGrid):
    for x in range(len(itemsGrid)):
        for y in range(len(itemsGrid[x])):
            itemsGrid[x][y] = [itemsGrid[x][y]]

convertToItemGrid(ItemsGrid)

def addItem(itemsGrid, position, item):
    x = position[0]
    y = position[1]

    if itemsGrid[x][y][0] != 2:
        itemsGrid[x][y][0] = 3
        itemsGrid[x][y].append(item)

def getItemsFromGrid(itemsGrid,position):
    x = position[0]
    y = position[1]

    if itemsGrid[x][y][0] == 3:
        return itemsGrid[x][y]
    return "None"


addItem(ItemsGrid,(0,1),4)

print(getItemsFromGrid(ItemsGrid,(0,0)))