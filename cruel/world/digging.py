"""Breaking the floor (Ctrl + interact): you dig at the floor tile you face until it gives way into a hole
(expansion.HOLE), the same kind a Bomb leaves, so you can drop through it to the floor below.

A floor is as tough as the wall of its room: a Stone room's floor has a Stone Wall's HP and hardness, and so on
(a city's floors dig like stone). Each swing does your Wall Damage, capped by the hardness, exactly as on a wall.
How far each tile has been dug is kept per floor in gameManager.floorCracks ({floor: {tile: a Wall standing in for
the floor}}), so a half-dug tile stays half dug while you're away."""
from cruel.world import expansion, plants, wall

CRACK_STAGES = 3  # the floor shows light, medium, then heavy cracks as it's dug (sprites.FLOOR_CRACKS)
FLOOR_WALLS = {"Stone": wall.StoneWall, "Wood": wall.WoodWall, "Sand": wall.SandWall, "Gold": wall.GoldWall,
               "Molten": wall.MoltenWall}


def floorWall(game, spot):
    """A fresh wall with the HP and hardness of this floor tile (its room's wall; Stone for anything else).
    fullHp remembers what it started with, for how cracked it looks."""
    floorType = plants.floorOf(spot, game.rooms)
    standIn = FLOOR_WALLS.get(floorType, wall.StoneWall)()
    standIn.fullHp = standIn.hp
    return standIn


def cracksHere(game):
    """{tile: its wall stand-in} for the floor tiles dug at on this floor but not yet broken through."""
    return game.floorCracks.setdefault(game.level, {})


def crackStages(game):
    """{tile: 0, 1 or 2} for the floor dug at on this floor: how cracked it looks (light, medium, heavy)."""
    return {spot: min(CRACK_STAGES - 1, CRACK_STAGES * (crack.fullHp - crack.hp) // crack.fullHp)
            for spot, crack in cracksHere(game).items()}


def canDig(game, spot):
    """Only bare floor can be dug: not a hole, a door, a plant, an item, a unit or anything else on it."""
    tile = game.grid.get(spot)
    return tile is not None and tile[0] == 0


def digFloor(game, spot):
    """One swing at the floor tile spot. Returns True if you swung (False if there's no bare floor there). When the
    floor runs out of HP it becomes a hole."""
    if not canDig(game, spot):
        return False
    cracks = cracksHere(game)
    if spot not in cracks:
        cracks[spot] = floorWall(game, spot)
    crack = cracks[spot]
    swings = 2 if game.player.hasEffect("half_swings") else 1  # Mole-King's Claws: half the swings, as on walls
    for _ in range(swings):
        if crack.hp > 0:
            crack.takeDamage(game.player.getWallDamage(), game.tileSize)
    if crack.hp <= 0:
        del cracks[spot]
        game.grid[spot] = [expansion.HOLE, game.grid[spot][1]]
    game.change = True
    return True
