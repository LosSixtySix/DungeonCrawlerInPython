import random

from cruel.world import plants

"""
A Dwellers' farmhouse, on a city's farm floor (mineshafts.py lays out the first; the farmers build more,
dwellerbuilding.py): a round room where the growers grow the crops the Dew Grubs eat. Like a goblin farming hut,
but round, with its beds in four plots round a storage chest in the middle, and a cross of paths from its two doors
(one on the side facing the shaft, one on the far side, like every Dweller building) to the chest.

The room is the tiles within sqrt(INSIDE_SQUARED) of its middle (7 across); its walls are every tile just round
that, so the building is round, 9 across. Each plot is a "boat" (BOAT): five crop tiles in a triangle, one in each
quarter of the room. A boat is a still life in the Game of Life the plants spread by (plants.py): no empty tile round
it has three of it beside it, so a full plot of one crop never sprouts more by itself. (Nothing wild sprouts inside
a farmhouse anyway: dwellerfarming.fieldTiles.)

A farmhouse grows one crop, and its floor is laid in the floor that crop grows on (floorFor).
"""

HALF = 4                    # a farmhouse's box is (2 * HALF + 1) tiles across
INSIDE_SQUARED = 14         # the room: tiles within this (squared) of the middle
BOAT = [(0, 0), (1, 0), (0, 1), (2, 1), (1, 2)]  # a plot: the Game of Life's boat (a still life), its point outward
FARM_KINDS = [kind for kind, info in plants.PLANTS.items() if info.get("wild", True) and not info.get("conway")]


def offsets():
    """(inside, walls, beds) as (column, row) offsets from the middle."""
    inside = {(column, row) for row in range(-HALF, HALF + 1) for column in range(-HALF, HALF + 1)
              if column * column + row * row <= INSIDE_SQUARED}
    walls = {(column, row) for row in range(-HALF, HALF + 1) for column in range(-HALF, HALF + 1)
             if (column, row) not in inside and any((column + stepColumn, row + stepRow) in inside
                                                     for stepColumn in (-1, 0, 1) for stepRow in (-1, 0, 1))}
    beds = [(signColumn * (1 + column), signRow * (1 + row)) for signColumn in (-1, 1) for signRow in (-1, 1)
            for column, row in BOAT]
    return inside, walls, beds


def shape(rowLength, middleColumn, middleRow, toward):
    """A farmhouse with its middle at (middleColumn, middleRow), its door on the side facing toward (a (column, row)):
    {"box", "walls", "inside", "door", "outside", "backDoor", "backOutside", "beds", "chest", "middle"} in spots."""
    inside, walls, beds = offsets()
    towardColumn, towardRow = toward
    if abs(towardColumn - middleColumn) > abs(towardRow - middleRow):
        sign = -1 if towardColumn < middleColumn else 1
        door, outside = (sign * HALF, 0), (sign * (HALF + 1), 0)
        backDoor, backOutside = (-sign * HALF, 0), (-sign * (HALF + 1), 0)
    else:
        sign = -1 if towardRow < middleRow else 1
        door, outside = (0, sign * HALF), (0, sign * (HALF + 1))
        backDoor, backOutside = (0, -sign * HALF), (0, -sign * (HALF + 1))

    def spot(offset):
        return middleColumn + offset[0] + (middleRow + offset[1]) * rowLength
    box = {spot((column, row)) for row in range(-HALF, HALF + 1) for column in range(-HALF, HALF + 1)}
    return {"box": box, "walls": {spot(offset) for offset in walls - {door, backDoor}},
            "inside": frozenset(spot(offset) for offset in inside), "door": spot(door), "outside": spot(outside),
            "backDoor": spot(backDoor), "backOutside": spot(backOutside), "beds": [spot(offset) for offset in beds],
            "chest": spot((0, 0)), "middle": spot((0, 0))}


def floorFor(kind):
    """The floor a farmhouse growing kind is laid in."""
    return plants.PLANTS[kind]["floors"][0]


def layFloor(rooms, tiles, kind):
    """Lays tiles in kind's floor (they leave whatever room they were in)."""
    floor = floorFor(kind)
    for room in rooms.values():
        room.difference_update(tiles)
    rooms.setdefault(floor, set()).update(tiles)


def pickCrop(existing=None):
    """A crop for a new farmhouse: of the crops already grown (existing: {tile: kind}), the one with the fewest
    tiles (the farmers have its seeds); a random one for the first."""
    if existing:
        counts = {}
        for kind in existing.values():
            counts[kind] = counts.get(kind, 0) + 1
        return min(counts, key=lambda kind: (counts[kind], kind))
    return random.choice(FARM_KINDS)
