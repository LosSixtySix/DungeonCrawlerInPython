"""Ropes: tie a Rope (a pouch material made from Fibrous Cloth) to a hole and it becomes a way down and back up.

Face a hole (expansion.HOLE) and press interact with a Rope in your pouch: the hole becomes a ROPED_HOLE. Stand on
it and press Enter to climb down (no fall damage). Where you land on the floor below lies the rope's end, a
HANGING_ROPE; stand on it and press Enter to climb back up to the roped hole. Ropes are tied from above only: the
floor below has no hole in it to tie to.

A rope can't be tied on the Scorched Depths (the floor below takes its place, so there'd be nothing to climb back
to) or on a city's works floor (you'd fall out past the city).

Tiles: [ROPED_HOLE, visibility, RopeTop] and [HANGING_ROPE, visibility, RopeBottom]."""
from cruel.world import mineshafts

ROPED_HOLE = 17    # grid tile type of a hole with a rope tied to it: stand on it, Enter climbs down
HANGING_ROPE = 18  # grid tile type of a rope's end on the floor below a roped hole: stand on it, Enter climbs up
ROPE = "rope"      # the pouch material
NO_ROPE_MESSAGE = "Could use a rope..."


class RopeTop:
    """The rope tied to a hole. bottom: the tile its end lies on, on the floor below (None until you first climb
    down)."""

    def __init__(self):
        self.bottom = None


class RopeBottom:
    """The rope's end on the floor below. hole: the roped hole's tile on the floor above."""

    def __init__(self, hole):
        self.hole = hole


def canTieHere(game):
    """Ropes stay tied only where the floor below keeps a way back up (not the Scorched Depths, not a works
    floor)."""
    from cruel.core.gamemanager import SCORCHED
    return game.proportion != SCORCHED and not mineshafts.onSideFloor(game)


def tieRope(game, holeSpot):
    """You pressed interact facing the hole at holeSpot. With a Rope in your pouch (and a floor a rope can stay
    tied on) it's tied there; with none you're told you could use one. Returns True if a rope was tied."""
    if not game.player.hasMaterials({ROPE: 1}):
        game.addPopup(NO_ROPE_MESSAGE, holeSpot)
        return False
    if not canTieHere(game):
        return False
    game.player.spendMaterials({ROPE: 1})
    game.grid[holeSpot] = [ROPED_HOLE, game.grid[holeSpot][1], RopeTop()]
    game.change = True
    return True


def ropeEndIsAt(floorGrid, spot, holeSpot):
    """Is the end of the rope from holeSpot lying at spot on this (saved) floor grid?"""
    tile = floorGrid.get(spot) if spot is not None else None
    return tile is not None and tile[0] == HANGING_ROPE and tile[2].hole == holeSpot


def climbDown(game):
    """Enter on a roped hole: down the rope to the floor below, with no fall damage. The first time, the rope's
    end is laid where you land; after that you climb down onto it."""
    holeSpot = game.playerPositionFlat
    ropeTop = game.currentLocation[2]
    below = game.level + 1
    floorBelow = game.levelGrids[below] if below < len(game.levelGrids) else None
    if floorBelow is not None and ropeEndIsAt(floorBelow[0], ropeTop.bottom, holeSpot):
        game.changeLevel(below, arriveAt=ropeTop.bottom)
        return
    game.descend()  # the way a fall goes, without the fall
    if game.currentLocation[0] == 0:  # (only bare floor takes the rope's end)
        game.currentLocation = [HANGING_ROPE, game.currentLocation[1], RopeBottom(holeSpot)]
        ropeTop.bottom = game.playerPositionFlat


def canClimbUp(game):
    """The floor above is still there (not across the start of a new track) and the rope is still tied to it."""
    above = game.level - 1
    if above < 0 or game.level in game.trackStarts or mineshafts.onSideFloor(game) or game.levelGrids[above] is None:
        return False
    tile = game.levelGrids[above][0].get(game.currentLocation[2].hole)
    return tile is not None and tile[0] == ROPED_HOLE


def climbUp(game):
    """Enter on a rope's end: up the rope to the roped hole on the floor above."""
    if canClimbUp(game):
        game.changeLevel(game.level - 1, arriveAt=game.currentLocation[2].hole)


def climb(game):
    """Enter while standing on a rope: down it from a roped hole, up it from its end. Returns True if you're on
    one."""
    if game.currentLocation[0] == ROPED_HOLE:
        climbDown(game)
    elif game.currentLocation[0] == HANGING_ROPE:
        climbUp(game)
    else:
        return False
    return True

