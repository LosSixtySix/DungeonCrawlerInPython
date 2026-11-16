import math
import pygame
import plants
import themes

"""
10x10 pictures for chests and doors, drawn top-down in the "Crypt" style.
Each picture is a list of 10 strings; every character is one pixel:

 .  transparent (the floor shows through)
 k  near-black outline / void        h  shadow (dark, see-through)    H  light shadow
 d  dark base color   m  mid base     c  base color   l  light base    W  brightest base
 g  dim gold          S  lit stone    s  dark stone   n  wood          N  dark wood
 a  faint light (see-through)        b  light (see-through)           w  dust speck (see-through white)

"Base color" is the theme's color for that object (chest, next door or previous door), so the
pictures recolor themselves on every floor.
"""

# The player: the Torchbearer, standing upright and seen from straight above, drawn FACING UP (the top of
# the grid is the front). The other directions are rotations. The clothing is the same cobalt blue on every
# floor (it stood out best against all 15 themes' floors, and sets off the orange flame):
#  c  clothing   C  dark clothing   l  clothing highlight   h  hair   s  skin   n  torch handle
#  f  flame      F  bright flame
PLAYER = [
    ".......F..",
    "......fFf.",
    "...kkkkn..",
    ".kkhhhhsk.",
    "kcchhhhcck",
    "kcchhhhcck",
    "kcckkkkcck",
    ".kcclccck.",
    "..kCCCCk..",
    "...kkkk...",
]
# The game's facing numbers (0 left, 1 right, 2 up, 3 down) -> clockwise quarter turns from "up"
PLAYER_TURNS = {2: 0, 1: 1, 3: 2, 0: 3}
PLAYER_COLOR = (74, 106, 208)  # cobalt blue

# ---------------------------------------------------------------- enemies
# Top-down, FACING DOWN (the bottom of the grid is the front). Each enemy type has fixed colors so it looks
# the same on every floor; only the dark outline ("k") comes from the theme. A shadow is added like the player's.
GOBLIN = [
    "..........",
    "...kkkk...",
    "..kCccCk..",
    ".kcckkcck.",
    ".hhkhhkhh.",
    ".kckHHkck.",
    ".kcckkcch.",
    "..kcccck.S",
    "...kkkk..s",
    "..........",
]
GOBLIN_COLORS = {"c": (62, 52, 40), "C": (42, 35, 27), "h": (79, 96, 56), "H": (51, 64, 42), "e": (200, 176, 64), "s": (106, 110, 118), "S": (154, 160, 168), "w": (74, 52, 36), "x": (168, 158, 136), "b": (90, 76, 56), "B": (64, 54, 42)}

DIRE_RAT = [
    "....tt....",
    ".....t....",
    "...kkkk...",
    "..kFffFk..",
    "..kfllfk..",
    "..kfllfk..",
    "..kffffk..",
    "...effe...",
    "....kk....",
    "....nn....",
]
DIRE_RAT_COLORS = {"f": (78, 70, 64), "F": (52, 48, 44), "l": (106, 96, 90), "t": (94, 74, 68), "e": (176, 42, 32), "n": (106, 74, 68), "g": (74, 84, 52)}

DIRE_MOLE = [
    "...kkkk...",
    "..kMmmMk..",
    ".kmmllmmk.",
    ".kmmllmmk.",
    ".kmmmmmmk.",
    "CkmmmmmmkC",
    "cCkmmmmkCc",
    ".ckmmmmkc.",
    "...kmmk...",
    "....nn....",
]
DIRE_MOLE_COLORS = {"m": (58, 48, 52), "M": (38, 32, 31), "l": (82, 69, 72), "c": (168, 156, 140), "C": (122, 112, 100), "n": (122, 80, 80), "d": (74, 58, 40), "s": (90, 86, 82), "e": (154, 154, 154)}

# Goblin Chieftain: the horned helm on a goblin's lean frame, in dark red, with a long blade
GOBLIN_CHIEFTAIN = [
    "..........",
    "...kkkk...",
    "..kfrrfk..",
    ".krrkkrrk.",
    "xxkkIIkkxx",
    ".krkiikrk.",
    ".krrkkrrh.",
    "..krrrrk.I",
    "...kkkk..I",
    ".........I",
]
GOBLIN_CHIEFTAIN_COLORS = {"I": (138, 116, 96), "f": (90, 78, 68), "h": (69, 88, 47), "i": (92, 74, 60), "r": (90, 30, 34), "x": (184, 174, 152)}

# The Unsealed: a void core with four broken pieces of the seal circling it (drawn per animation frame)
UNSEALED_CORE = [
    "..........",
    "....kk....",
    "...kVVk...",
    "..kVvvVk..",
    ".kVvwwvVk.",
    ".kVvwwvVk.",
    "..kVvvVk..",
    "...kVVk...",
    "....kk....",
    "..........",
]
UNSEALED_COLORS = {"v": (20, 14, 24), "V": (42, 30, 50), "y": (138, 106, 42), "Y": (192, 154, 64), "w": (232, 216, 160), "c": (242, 230, 184)}
SHARD_FRAMES = 60          # frames in one full turn of the shards
SHARD_TURN_SECONDS = 6     # how long one full turn takes

# enemy name (as in enemies.py) -> (picture, colors). Enemies not listed are still drawn as a square.
ENEMY_SPRITES = {
    "Goblin": (GOBLIN, GOBLIN_COLORS),
    "Dire Rat": (DIRE_RAT, DIRE_RAT_COLORS),
    "Dire Mole": (DIRE_MOLE, DIRE_MOLE_COLORS),
    "Goblin Chieftan": (GOBLIN_CHIEFTAIN, GOBLIN_CHIEFTAIN_COLORS),   # spelled as in enemies.py
}

# Chest colors are the same on every floor: (body color, stud color). Each chest randomly gets one of
# CHEST_COLORS; CURSED_CHEST_COLOR is kept for cursed chests (not in the game yet).
CHEST_COLORS = {
    "walnut": ((94, 60, 38), (226, 181, 68)),       # dark walnut, gold studs
    "mahogany": ((116, 48, 42), (217, 180, 106)),    # red-brown mahogany, brass studs
    "burntUmber": ((74, 49, 33), (212, 138, 76)),    # near-black umber, copper studs
}
CURSED_CHEST_COLOR = ((155, 47, 52), (214, 172, 94))  # blood crimson, brass studs

# Chest: a reliquary with a peaked lid, lit from the top-left, throwing a shadow down and right
CHEST = [
    "..........",
    ".kkkkkkkk.",
    ".kgllmmgkh",
    ".klllmmmkh",
    ".klllmmmkh",
    ".kcccdddkh",
    ".kcccdddkh",
    ".kgccddgkh",
    ".kkkkkkkkh",
    "..hhhhhhhh",
]

# Door down: each floor's door randomly uses one of these pits. They're holes cut into the floor, so
# they're colored from the floor tile they sit on (see pitRoles):
#  L  the near lip (floor, a little lighter)   a  floor in shadow   b  floor in deep shadow
#  k  the dark bottom of the pit
OPEN_PIT = [
    "..........",
    "..aaaaaa..",
    ".abbbbbba.",
    ".bbkkkkbb.",
    "abkkkkkkba",
    "abkkkkkkba",
    "akkkkkkkka",
    ".kkkkkkkk.",
    ".LkkkkkkL.",
    "..LLLLLL..",
]
COLLAPSED_GRAVE = [
    "...a......",
    "....a..a..",
    "..aabbba..",
    ".abbkkkba.",
    "abkkkkkkb.",
    ".bkkkkkkba",
    ".bkkkkkkb.",
    "..kkkkkk..",
    ".aLkkkL.a.",
    "a...LL....",
]
PIT_STYLES = [OPEN_PIT, COLLAPSED_GRAVE]

# Door back up: moonbeam, a soft see-through pool of light from a hole in the ceiling. Its edge fades
# into the floor in the same dot pattern as the dithered light, with a few specks of dust in it.
MOONBEAM = [
    "..........",
    "...aaa.a..",
    "..awbbaaa.",
    ".aabWWba..",
    ".abWWWwba.",
    ".abWWWWba.",
    "..abWWbaa.",
    ".aaawbaa..",
    "..a.aaa...",
    "..........",
]


# ---------------------------------------------------------------- stations
# Set-up crafting stations, top-down, with fixed colors (only the outline "k" follows the theme).
SMELTER = [
    "..........",
    "..kkkkkk..",
    ".kCccccCk.",
    ".kcCkkCck.",
    ".kckffkck.",
    ".kckFfkck.",
    ".kcckkcck.",
    ".kCccccCk.",
    "..kkkkkk..",
    "..........",
]
SMELTER_COLORS = {"c": (150, 96, 64), "C": (108, 66, 44), "f": (255, 132, 40), "F": (255, 220, 120)}

ANVIL = [
    "..........",
    "...kkkkkk.",
    "kkkkiiiiik",
    "kIIiiiiiik",
    "kkkkiiiiik",
    "...kIiiIk.",
    "...kiIIik.",
    "..kkkkkkkk",
    "..knnnnnnk",
    "..kkkkkkkk",
]
ANVIL_COLORS = {"i": (112, 116, 124), "I": (172, 178, 188), "n": (110, 74, 44)}

SHRINE = [
    "..........",
    ".kkkkkkkk.",
    ".kSssssSk.",
    ".ksvvvvsk.",
    ".ksvVVvsk.",
    ".ksvVVvsk.",
    ".ksvvvvsk.",
    ".kSssssSk.",
    ".kkkkkkkk.",
    "..........",
]
SHRINE_COLORS = {"S": (170, 166, 160), "s": (106, 102, 100), "v": (84, 56, 124), "V": (196, 156, 244)}

FORGE = [
    "..........",
    ".kkkkkkkk.",
    ".kGggggGk.",
    ".kgkkkkgk.",
    ".kgkffkgk.",
    ".kgkFfkgk.",
    ".kgkkkkgk.",
    ".kGggggGk.",
    ".kkkkkkkk.",
    "..........",
]
FORGE_COLORS = {"G": (240, 202, 96), "g": (184, 140, 50), "f": (255, 132, 40), "F": (255, 220, 120)}

CAULDRON = [
    "..........",
    "..kkkkkk..",
    ".kIiiiiIk.",
    "kIgGggGgIk",
    "kigggGggik",
    "kIgGgggGIk",
    ".kIiiiiIk.",
    "..kkkkkk..",
    "..kfFFfk..",
    "...kkkk...",
]
CAULDRON_COLORS = {"i": (70, 74, 82), "I": (120, 126, 136), "g": (86, 168, 70), "G": (176, 236, 120),
                   "f": (255, 132, 40), "F": (255, 220, 120)}

# ---------------------------------------------------------------- plants (colors in plants.PLANTS)
PLANT_SPRITES = {  # all seen from above, like the rest of the map
    "bloodcap": [  # a round red cap with pale spots
        "..kkkkkk..",
        ".kcCCwcck.",
        "kcCwccccck",
        "kcCccccwck",
        "kccccwccck",
        "kcwcccccck",
        "kccccwccck",
        ".kcwcccck.",
        "..kkkkkk..",
        "..........",
    ],
    "hearthmoss": [  # a soft, lumpy mat of moss
        "..kkk.kk..",
        ".kcCckCck.",
        "kcCccccCk.",
        "kccsccCcck",
        ".kcCcsccck",
        "kcccCccck.",
        "kCcsccCck.",
        ".kccCcck..",
        "..kk.kkk..",
        "..........",
    ],
    "glowcap": [  # five little glowing caps
        ".kk....kk.",
        "kCck..kCck",
        "kcck..kcck",
        ".kk.kk.kk.",
        "...kCck...",
        "...kcck...",
        ".kk.kk.kk.",
        "kCck..kCck",
        "kcck..kcck",
        ".kk....kk.",
    ],
    "emberroot": [  # a rosette of pointed leaves around a bulb
        "....kk....",
        "...kCck...",
        ".k.kcck.k.",
        "kCkkcckkCk",
        ".kcCssCck.",
        ".kcCssCck.",
        "kCkkcckkCk",
        ".k.kcck.k.",
        "...kCck...",
        "....kk....",
    ],
    "shadowfern": [  # fronds spreading out from a dark middle
        "C...cC...C",
        ".C..cC..C.",
        "..CccCcC..",
        "...cssc...",
        "CccCssCccC",
        "CccCssCccC",
        "...cssc...",
        "..CcCccC..",
        ".C..Cc..C.",
        "C...Cc...C",
    ],
}

STATION_SPRITES = {"smelter": (SMELTER, SMELTER_COLORS), "anvil": (ANVIL, ANVIL_COLORS),
                   "shrine": (SHRINE, SHRINE_COLORS), "forge": (FORGE, FORGE_COLORS),
                   "cauldron": (CAULDRON, CAULDRON_COLORS)}


def roles(colors, base):
    mix = themes.mix
    black, white = [0, 0, 0], [255, 255, 255]
    return {
        "k": mix(colors["fog"], black, 0.5),
        "d": mix(base, black, 0.6), "m": mix(base, black, 0.35), "c": base,
        "l": mix(base, white, 0.25), "W": mix(base, white, 0.55),
        "g": mix(colors["wallGold"], black, 0.2),
        "S": mix(colors["wallStone"], white, 0.08), "s": mix(colors["wallStone"], black, 0.3),
        "n": colors["wallWood"], "N": mix(colors["wallWood"], black, 0.4),
        "h": (0, 0, 0, 115), "H": (0, 0, 0, 64),
        "a": (*mix(base, white, 0.2), 130), "b": (*mix(base, white, 0.35), 200), "w": (255, 255, 255, 230),
    }


def chestRoles(colors, base, stud):
    """Chests ignore the floor's theme (apart from the dark outline) so they look the same on every floor."""
    palette = roles(colors, list(base))
    palette["g"] = list(stud)
    return palette


def playerRoles(colors):
    mix = themes.mix
    base = list(PLAYER_COLOR)
    return {"k": mix(colors["fog"], [0, 0, 0], 0.5), "c": mix(base, [0, 0, 0], 0.22), "C": mix(base, [0, 0, 0], 0.5),
            "l": base, "h": (58, 42, 32), "s": (201, 160, 122), "n": (122, 82, 50), "f": (255, 160, 60), "F": (255, 236, 160)}


def rotateClockwise(rows, turns):
    for _ in range(turns):
        rows = ["".join(column) for column in zip(*rows[::-1])]
    return rows


def makeShadowed(rows, palette, tileSize):
    """A picture with a shadow one pixel down and to the right of it (wherever that lands on the floor)."""
    surface = pygame.Surface((10, 10), pygame.SRCALPHA)
    for y in range(9):
        for x in range(9):
            if rows[y][x] != "." and rows[y + 1][x + 1] == ".":
                surface.set_at((x + 1, y + 1), (0, 0, 0, 115))
    for y, row in enumerate(rows):
        for x, ch in enumerate(row):
            if ch != ".":
                surface.set_at((x, y), palette[ch])
    if tileSize != 10:
        surface = pygame.transform.scale(surface, (tileSize, tileSize))
    return surface


def makePlayer(colors, facing, tileSize):
    """The player facing one direction, with its shadow."""
    return makeShadowed(rotateClockwise(PLAYER, PLAYER_TURNS[facing]), playerRoles(colors), tileSize)


def enemyRoles(colors, fixedColors):
    palette = dict(fixedColors)
    palette["k"] = themes.mix(colors["fog"], [0, 0, 0], 0.5)
    return palette


def unsealedFrame(colors, frame):
    """The Unsealed with its four seal shards turned to this frame's angle around the core."""
    angle = frame / SHARD_FRAMES * 2 * math.pi
    rows = [list(r) for r in UNSEALED_CORE]
    for shard in range(4):
        a = angle + shard * math.pi / 2 + math.pi / 4
        # each shard: a dim trailing pixel and a bright leading one, laid along its orbit
        for offset, ch in ((-0.3, "y"), (0.0, "Y")):
            x = min(9, max(0, int(4.5 + 4.4 * math.cos(a + offset))))
            y = min(9, max(0, int(4.5 + 4.4 * math.sin(a + offset))))
            rows[y][x] = ch
    return ["".join(r) for r in rows]


def pitRoles(floor):
    mix = themes.mix
    return {"L": mix(floor, [255, 255, 255], 0.12), "a": mix(floor, [0, 0, 0], 0.3), "b": mix(floor, [0, 0, 0], 0.55),
            "k": mix(floor, [0, 0, 0], 0.82)}


def makePit(style, floor, tileSize):
    """One pit picture for a given floor color (pits blend into whatever room they're in)."""
    return makeSurface(PIT_STYLES[style], pitRoles(floor), tileSize)


def makeSurface(rows, palette, tileSize):
    surface = pygame.Surface((10, 10), pygame.SRCALPHA)
    for y, row in enumerate(rows):
        for x, ch in enumerate(row):
            if ch != ".":
                surface.set_at((x, y), palette[ch])
    if tileSize != 10:
        surface = pygame.transform.scale(surface, (tileSize, tileSize))
    return surface


def buildSprites(colors, tileSize):
    """All the chest/door pictures for one theme, as transparent Surfaces ready to blit."""
    return {
        "chests": [makeSurface(CHEST, chestRoles(colors, base, stud), tileSize) for base, stud in CHEST_COLORS.values()],
        "cursedChest": makeSurface(CHEST, chestRoles(colors, *CURSED_CHEST_COLOR), tileSize),
        "player": {facing: makePlayer(colors, facing, tileSize) for facing in PLAYER_TURNS},
        "enemies": {name: makeShadowed(rows, enemyRoles(colors, fixed), tileSize) for name, (rows, fixed) in ENEMY_SPRITES.items()},
        "unsealed": [makeShadowed(unsealedFrame(colors, f), enemyRoles(colors, UNSEALED_COLORS), tileSize) for f in range(SHARD_FRAMES)],
        "doorUp": makeSurface(MOONBEAM, roles(colors, colors["doorPrev"]), tileSize),
        "stations": {sid: makeShadowed(rows, enemyRoles(colors, fixed), tileSize) for sid, (rows, fixed) in STATION_SPRITES.items()},
        "plants": {kind: makeShadowed(rows, enemyRoles(colors, plants.PLANTS[kind]["colors"]), tileSize) for kind, rows in PLANT_SPRITES.items()},
    }


def chestColorFor(position):
    """Which of the CHEST_COLORS a chest uses: random-looking, but always the same for a given spot."""
    h = (position + 0x9E3779B9) & 0xFFFFFFFF   # scramble the position so nearby chests don't follow a pattern
    h = ((h ^ (h >> 16)) * 0x45D9F3B) & 0xFFFFFFFF
    h = ((h ^ (h >> 16)) * 0x45D9F3B) & 0xFFFFFFFF
    return (h ^ (h >> 16)) % len(CHEST_COLORS)


def shardFrameFor(seconds):
    """Which Unsealed frame to show at this moment."""
    return int(seconds / SHARD_TURN_SECONDS * SHARD_FRAMES) % SHARD_FRAMES


def pitStyleFor(position):
    """Which pit a door uses. Worked out from the door's position, so it looks random from floor to
    floor but stays the same every time you see that door (and after loading a save)."""
    return ((position * 2654435761) >> 8) % len(PIT_STYLES)
