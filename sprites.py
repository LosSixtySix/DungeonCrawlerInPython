import pygame
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
#  k  the dark bottom of the pit              d  dim door glow     c  door glow (door color)
OPEN_PIT = [
    "..........",
    "..aaaaaa..",
    ".abbbbbba.",
    ".bbkkkkbb.",
    "abkkkkkkba",
    "abkkddkkba",
    "akkkcckkka",
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
    ".bkkdkkkba",
    ".bkkckkkb.",
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


def pitRoles(floor, door):
    mix = themes.mix
    return {"L": mix(floor, [255, 255, 255], 0.12), "a": mix(floor, [0, 0, 0], 0.3), "b": mix(floor, [0, 0, 0], 0.55),
            "k": mix(floor, [0, 0, 0], 0.82), "d": mix(door, [0, 0, 0], 0.45), "c": door}


def makePit(style, floor, door, tileSize):
    """One pit picture for a given floor color (pits blend into whatever room they're in)."""
    return makeSurface(PIT_STYLES[style], pitRoles(floor, door), tileSize)


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
        "chest": makeSurface(CHEST, roles(colors, colors["chest"]), tileSize),
        "doorUp": makeSurface(MOONBEAM, roles(colors, colors["doorPrev"]), tileSize),
    }


def pitStyleFor(position):
    """Which pit a door uses. Worked out from the door's position, so it looks random from floor to
    floor but stays the same every time you see that door (and after loading a save)."""
    return ((position * 2654435761) >> 8) % len(PIT_STYLES)
