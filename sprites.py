import math
import random
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

# Organizers: a hooded builder carrying a brick, with its pattern stitched on its back ("E", rows 4-6).
# The four kinds share the body; each has its own robe color and emblem.
def organizerPicture(emblem):
    body = [
        "..........",
        "...kkkk...",
        "..kHHHHk..",
        ".kcHffHck.",
        "kcc....cck",
        "kcc....cck",
        "kcc....cck",
        ".kccccccbk",
        "..kkkkkkB.",
        "..........",
    ]
    rows = [list(r) for r in body]
    for y, line in enumerate(emblem):
        for x, ch in enumerate(line):
            rows[4 + y][3 + x] = "E" if ch == "E" else "c"
    return ["".join(r) for r in rows]


ORGANIZER_EMBLEMS = {  # 4 wide, 3 tall
    "spiral": ["EEEE", "cEcE", "EEcE"],
    "circle": ["cEEc", "EccE", "cEEc"],
    "square": ["EEEE", "EccE", "EEEE"],
    "plant": ["ccEE", "cEEc", "Eccc"],
}
ORGANIZER_ROBES = {  # robe, hood, emblem
    "spiral": ((52, 112, 120), (32, 70, 76), (220, 206, 150)),
    "circle": ((70, 66, 140), (44, 40, 92), (220, 206, 150)),
    "square": ((140, 74, 48), (90, 46, 30), (220, 206, 150)),
    "plant": ((70, 108, 54), (44, 70, 34), (196, 112, 200)),
}


def organizerColors(pattern):
    robe, hood, emblem = ORGANIZER_ROBES[pattern]
    return {"c": robe, "H": hood, "E": emblem, "f": (40, 32, 30), "b": (168, 92, 64), "B": (120, 64, 44)}


# Goblin Builder: the Goblin with a mallet where its blade would be
GOBLIN_BUILDER = [
    "..........",
    "...kkkk...",
    "..kCccCk..",
    ".kcckkcck.",
    ".hhkhhkhh.",
    ".kckHHkcMM",
    ".kcckkchMM",
    "..kcccck.w",
    "...kkkk..w",
    "..........",
]
GOBLIN_BUILDER_COLORS = {**GOBLIN_COLORS, "M": (150, 154, 162), "w": (110, 80, 52)}

# Goblin Farmer, from above: a wide straw hat (banded in its faction's cloth) hides its head, ears and hands poke out
# under the brim, and it carries a hoe.
GOBLIN_FARMER = [
    "...kkkk...",
    ".kkyyyykk.",
    ".kyYYYYyk.",
    "kyYbbbbYyk",
    "kyYbYYbYyk",
    ".kyYYYYyk.",
    ".hkkyykkhw",
    "..kcccck.w",
    "...kccck.w",
    "........MM",
]
GOBLIN_FARMER_COLORS = {**GOBLIN_COLORS, "y": (186, 152, 80), "Y": (222, 192, 118), "b": (62, 52, 40),
                        "M": (150, 154, 162), "w": (110, 80, 52)}

# Expansion factions: the Goblin, Goblin Chieftain and Goblin Builder pictures in each faction's colors (only cloth
# and armor change). Ids match expansion.LOOKS.
EXPANSION_LOOKS = {
    "warpaint": {"goblin": {"c": (150, 38, 34), "C": (96, 22, 22)}, "chief": {"r": (36, 34, 40), "f": (150, 38, 34), "i": (96, 22, 22)}, "mallet": (150, 154, 162)},
    "ashen": {"goblin": {"c": (176, 170, 156), "C": (124, 118, 106)}, "chief": {"r": (198, 192, 176), "f": (120, 112, 100), "i": (150, 142, 128)}, "mallet": (120, 124, 132)},
    "ochre": {"goblin": {"c": (176, 132, 40), "C": (120, 88, 26)}, "chief": {"r": (40, 62, 120), "f": (176, 132, 40), "i": (26, 40, 82)}, "mallet": (150, 154, 162)},
    "nightcult": {"goblin": {"c": (92, 52, 140), "C": (60, 32, 96)}, "chief": {"r": (52, 30, 72), "f": (120, 80, 170), "i": (70, 40, 100)}, "mallet": (150, 154, 162)},
    "tidewater": {"goblin": {"c": (40, 132, 130), "C": (24, 88, 86)}, "chief": {"r": (22, 70, 66), "f": (40, 132, 130), "i": (16, 48, 46)}, "mallet": (150, 154, 162)},
    "ember": {"goblin": {"c": (214, 104, 30), "C": (150, 66, 18)}, "chief": {"r": (70, 66, 64), "f": (214, 104, 30), "i": (44, 42, 40)}, "mallet": (150, 154, 162)},
    # an abandoned camp (expansion.NEUTRAL_LOOK): weathered, lichen-grey cloth and mortar. No faction is given it.
    "abandoned": {"goblin": {"c": (98, 104, 86), "C": (66, 72, 58)}, "chief": {"r": (58, 62, 52), "f": (98, 104, 86), "i": (40, 44, 36)}, "mallet": (120, 124, 132)},
}


def factionPictures(look):
    """{enemy name: (picture, colors)} for one faction look."""
    colors = EXPANSION_LOOKS[look]
    return {
        "Goblin": (GOBLIN, {**GOBLIN_COLORS, **colors["goblin"]}),
        "Goblin Chieftan": (GOBLIN_CHIEFTAIN, {**GOBLIN_CHIEFTAIN_COLORS, **colors["chief"]}),
        "Goblin Builder": (GOBLIN_BUILDER, {**GOBLIN_BUILDER_COLORS, **colors["goblin"], "M": colors["mallet"]}),
        "Goblin Farmer": (GOBLIN_FARMER, {**GOBLIN_FARMER_COLORS, **colors["goblin"], "b": colors["goblin"]["c"],
                                          "M": colors["mallet"]}),
    }


# Camp pieces, top down. Spawner: a goblin den seen from above, a dark pit ringed with sharpened stakes, eyes
# glinting inside. Bonfire: a ring of stones round crossed logs, the fire's bright core in the middle (two frames).
SPAWNER = ["..w.WW.w..", ".WwkkkkwW.", ".wkddddkw.", "WkddDDddkW", "WkdDgDgdkW", "wkdDDDDdkw", "WkddDDddkW", ".wkddddkw.", ".WwkkkkwW.", "..w.WW.w.."]
SPAWNER_COLORS = {"w": (126, 90, 54), "W": (86, 60, 38), "d": (24, 18, 14), "D": (54, 26, 20), "g": (232, 192, 72)}
BONFIRE = [
    ["...SsSs...", ".sSkkkkSs.", ".SkwrrwkS.", "SkwrYYrwkS", "skrYyyYrks", "SkrYyyYrkS", "skwrYYrwks", ".SkwrrwkS.", ".sSkkkkSs.", "...sSsS..."],
    ["...SsSs...", ".sSkkkkSs.", ".SkwrYwkS.", "SkwYYyrwkS", "skrYyyYrks", "SkrYyYYrkS", "skwrYrrwks", ".SkwrrwkS.", ".sSkkkkSs.", "...sSsS..."],
]
BONFIRE_COLORS = {"S": (146, 148, 156), "s": (100, 102, 110), "w": (112, 76, 44), "r": (196, 48, 28), "Y": (240, 128, 40), "y": (255, 222, 120)}
BONFIRE_FRAME_MS = 180

# Warcamp chest, top down: a rough plank crate with two iron bands, a strap of the faction's cloth across the middle.
# (A floor chest is a lidded box with studs; this one is plainly goblin-made.)
CAMP_CHEST = [
    "..........",
    ".kkkkkkkk.",
    ".kpbppbpk.",
    ".kPbPPbPk.",
    ".kcccccck.",
    ".kCccccCk.",
    ".kpbppbpk.",
    ".kPbPPbPk.",
    ".kkkkkkkk.",
    "..........",
]
CAMP_CHEST_COLORS = {"p": (150, 118, 78), "P": (112, 84, 52), "b": (88, 90, 98)}


def campChestColors(look):
    cloth = EXPANSION_LOOKS[look]["goblin"]
    return {**CAMP_CHEST_COLORS, "c": cloth["c"], "C": cloth["C"]}

# enemy name (as in enemies.py) -> (picture, colors). Enemies not listed are still drawn as a square.
ENEMY_SPRITES = {
    "Goblin": (GOBLIN, GOBLIN_COLORS),
    "Dire Rat": (DIRE_RAT, DIRE_RAT_COLORS),
    "Dire Mole": (DIRE_MOLE, DIRE_MOLE_COLORS),
    "Goblin Chieftan": (GOBLIN_CHIEFTAIN, GOBLIN_CHIEFTAIN_COLORS),   # spelled as in enemies.py
    "Goblin Builder": (GOBLIN_BUILDER, GOBLIN_BUILDER_COLORS),
    "Goblin Farmer": (GOBLIN_FARMER, GOBLIN_FARMER_COLORS),
    **{f"{pattern.capitalize()} Organizer": (organizerPicture(emblem), organizerColors(pattern))
       for pattern, emblem in ORGANIZER_EMBLEMS.items()},
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

# Item piles: loose items on the floor, which you can walk over. Each pile gets one of these at random.
# Fixed colors like the enemies; "k" is the theme's outline and "h" a see-through shadow.
PILE_SPRITES = [
    ([  # a burlap loot sack, tied at the neck
        "....kk....",
        "...klck...",
        "...kyyk...",
        "..kclcck..",
        ".kcllccck.",
        ".kclcccdkh",
        ".kccccddkh",
        ".kcccdddkh",
        "..kkkkkkh.",
        "...hhhhh..",
    ], {"c": (150, 118, 78), "l": (190, 158, 110), "d": (104, 80, 52), "y": (220, 196, 136)}),
    ([  # a sword stuck in a heap of gold
        "......k...",
        ".....kik..",
        ".....kik..",
        "....kgggk.",
        ".....knk..",
        "...kkGgkk.",
        "..kGgGggdk",
        ".kGgggdddk",
        ".kkkkkkkkh",
        "..hhhhhhhh",
    ], {"i": (206, 212, 220), "g": (214, 164, 56), "G": (248, 218, 118), "d": (150, 108, 34), "n": (122, 82, 50)}),
    ([  # a coin, a gem and a potion lying loose
        "..........",
        ".kk.......",
        "kGgk...kk.",
        ".kk...kpPk",
        "......kppk",
        "..kk...kk.",
        ".kWek.....",
        ".keEk..kk.",
        "..kk..kGgk",
        ".......kk.",
    ], {"G": (248, 218, 118), "g": (214, 164, 56), "p": (176, 44, 52), "P": (232, 110, 110),
        "W": (200, 238, 250), "e": (96, 172, 222), "E": (52, 110, 170)}),
    ([  # a cloth bundle tied with red cord, set on its corner
        "....kk....",
        "...kWlk...",
        "..kllyck..",
        ".kllcyyck.",
        "kllcyccyck",
        ".kcycccdkh",
        "..kycddkh.",
        "...kddkh..",
        "....kkh...",
        ".....h....",
    ], {"W": (214, 206, 186), "l": (176, 166, 146), "c": (138, 128, 110), "d": (98, 90, 78), "y": (150, 64, 52)}),
]


# A Glowrock set down on the floor: a small pebble in the middle of the tile, lit from inside (top-down)
GLOWROCK = [
    "..........",
    "..........",
    "..........",
    "....kk....",
    "...kYGk...",
    "...kGgk...",
    "....kk....",
    "..........",
    "..........",
    "..........",
]
GLOWROCK_COLORS = {"Y": (255, 250, 200), "G": (232, 220, 130), "g": (168, 150, 78)}


def pileRoles(colors, fixedColors):
    palette = enemyRoles(colors, fixedColors)
    palette["h"] = (0, 0, 0, 115)
    return palette


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
    "organizers_demise": [  # a knot of purple thorns
        "k...kk...k",
        ".k.kCck.k.",
        "..kcCcck..",
        ".kcCsscCk.",
        "kCcsCCscCk",
        "kCcsCCscCk",
        ".kcCsscCk.",
        "..kccCck..",
        ".k.kcCk.k.",
        "k...kk...k",
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

# A planted plant's early stages (plants.Plant.stage), in its kind's colors, seen from above: a sprout of two leaves,
# then a young rosette. Ripe, it's drawn as its full sprite; gone to seed, with SEED_PODS on top.
SPROUT = [
    "..........",
    "..........",
    "..........",
    "..kk..kk..",
    ".kCckkcCk.",
    "..kcCCck..",
    "...kkkk...",
    "..........",
    "..........",
    "..........",
]
YOUNG_PLANT = [
    "..........",
    "..........",
    "...kkkk...",
    "..kcCCck..",
    ".kcCccCck.",
    ".kcCccCck.",
    "..kcCCck..",
    "...kkkk...",
    "..........",
    "..........",
]
SEED_PODS = [  # pale pods dotted over a plant gone to seed
    "..........",
    ".pP....Pp.",
    ".Pp....pP.",
    "..........",
    "....pP....",
    "....Pp....",
    "..........",
    "..........",
    ".pP....Pp.",
    ".Pp....pP.",
]
SEED_POD_COLORS = {"p": (150, 118, 64), "P": (240, 222, 160)}

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


def holeRows(openSides, variant):
    """A hole in the floor, top down (expansion.HOLE): black depth, with a broken lip of floor and its shadow along
    each side that isn't more hole (openSides: the sides, of "nesw", where the next tile is a hole too, so holes
    run together into one ragged pit). variant picks the raggedness, so neighboring holes don't match."""
    rng = random.Random(variant * 7919 + sum(ord(c) for c in openSides))
    rows = [["k"] * 10 for _ in range(10)]
    for side in "nesw":
        if side in openSides:
            continue
        for along in range(10):
            depth = rng.choice((1, 1, 2, 2, 3))
            for into in range(depth + 1):
                ch = "f" if into < depth - 1 else ("a" if into == depth - 1 else "b")
                x, y = {"n": (along, into), "s": (along, 9 - into), "w": (into, along), "e": (9 - into, along)}[side]
                if rows[y][x] in ("k", "b") or ch == "f":
                    rows[y][x] = ch
    for _ in range(rng.randint(1, 3)):  # bits of broken floor down in the dark
        x, y = rng.randint(2, 7), rng.randint(2, 7)
        if rows[y][x] == "k":
            rows[y][x] = "b"
    return ["".join(r) for r in rows]


def makeHole(openSides, variant, floor, tileSize):
    roles_ = {**pitRoles(floor), "f": floor}
    return makeSurface(holeRows(openSides, variant), roles_, tileSize)


# The Fire Giant: 20x20, top-down, facing up. It covers 2x2 tiles; each tile draws its own quarter.
FIRE_GIANT = [
    "....................",
    "....................",
    "....................",
    "....................",
    "........kkkk........",
    ".kkkkk.kffffk.......",
    ".kRrrkkfMyyMfkkkkkk.",
    ".kkRrkkfyMMyfkkRRRk.",
    ".kkRkkkkfMMfkkkkRkk.",
    "kRRrrRRRkffkRRRrrRRk",
    "kMmRRrmRRkkRRmrRRmRk",
    "kRRmmRRrRRRRrRRmmRMk",
    "kRRRRmRRrRRrRRmRRRRk",
    ".kRmRmmRRRRRRmRRmRk.",
    "..kRRmRmmMMmmRRmmk..",
    "...kRRRRmMMmRMRRk...",
    "....kRMRRmmRRRRk....",
    ".....kkRRmmRRkk.....",
    ".......kkkkkk.......",
    "....................",
]
FIRE_GIANT_COLORS = {"r": (58, 38, 34), "R": (90, 58, 48), "m": (232, 96, 28), "M": (255, 174, 58), "y": (255, 226, 122), "f": (255, 122, 26)}
GIANT_SPRITES = {"Fire Giant": (FIRE_GIANT, FIRE_GIANT_COLORS)}


# Enemies turn to face the way they last moved (enemy.facing, the same numbers as the player's direction:
# 0 left, 1 right, 2 up, 3 down). ENEMY_FACING is the way each picture is drawn; anything not listed is drawn
# facing down. Organizers and the Unsealed are round and never turn.
FACINGS = (0, 1, 2, 3)
ENEMY_FACING = {"Fire Giant": 2}


def turns(name):
    return "Organizer" not in name


def baseFacing(name):
    return ENEMY_FACING.get(name, 3)


def facingRows(rows, name, facing):
    """The picture for name turned to face facing."""
    if not turns(name):
        return rows
    return rotateClockwise(rows, (PLAYER_TURNS[facing] - PLAYER_TURNS[baseFacing(name)]) % 4)


def makeGiantQuarters(rows, palette, tileSize):
    """A picture bigger than one tile (n x n pixels for n/10 tiles a side), shadowed like makeShadowed, cut into
    one picture per tile: [top-left, top-right, ..., bottom-right], reading across."""
    n = len(rows)
    surface = pygame.Surface((n, n), pygame.SRCALPHA)
    for y in range(n - 1):
        for x in range(n - 1):
            if rows[y][x] != "." and rows[y + 1][x + 1] == ".":
                surface.set_at((x + 1, y + 1), (0, 0, 0, 115))
    for y, row in enumerate(rows):
        for x, ch in enumerate(row):
            if ch != ".":
                surface.set_at((x, y), palette[ch])
    tiles = n // 10
    surface = pygame.transform.scale(surface, (tileSize * tiles, tileSize * tiles))
    return [surface.subsurface(pygame.Rect(qx * tileSize, qy * tileSize, tileSize, tileSize)).copy()
            for qy in range(tiles) for qx in range(tiles)]


SCORCHED_DOOR_GLOW = (214, 84, 22)  # the lava the Scorched door's pit is drawn over


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
        "piles": [makeSurface(rows, pileRoles(colors, fixed), tileSize) for rows, fixed in PILE_SPRITES],
        "glowrock": makeShadowed(GLOWROCK, enemyRoles(colors, GLOWROCK_COLORS), tileSize),
        "player": {facing: makePlayer(colors, facing, tileSize) for facing in PLAYER_TURNS},
        "enemies": {name: {f: makeShadowed(facingRows(rows, name, f), enemyRoles(colors, fixed), tileSize) for f in FACINGS}
                    for name, (rows, fixed) in ENEMY_SPRITES.items()},
        "giants": {name: {f: makeGiantQuarters(facingRows(rows, name, f), enemyRoles(colors, fixed), tileSize) for f in FACINGS}
                   for name, (rows, fixed) in GIANT_SPRITES.items()},
        "unsealed": [makeShadowed(unsealedFrame(colors, f), enemyRoles(colors, UNSEALED_COLORS), tileSize) for f in range(SHARD_FRAMES)],
        "doorUp": makeSurface(MOONBEAM, roles(colors, colors["doorPrev"]), tileSize),
        "stations": {sid: makeShadowed(rows, enemyRoles(colors, fixed), tileSize) for sid, (rows, fixed) in STATION_SPRITES.items()},
        "plants": {kind: makeShadowed(rows, enemyRoles(colors, plants.PLANTS[kind]["colors"]), tileSize) for kind, rows in PLANT_SPRITES.items()},
        "sprouts": {kind: makeShadowed(SPROUT, enemyRoles(colors, plants.PLANTS[kind]["colors"]), tileSize) for kind in PLANT_SPRITES},
        "youngPlants": {kind: makeShadowed(YOUNG_PLANT, enemyRoles(colors, plants.PLANTS[kind]["colors"]), tileSize) for kind in PLANT_SPRITES},
        "seedPods": makeSurface(SEED_PODS, SEED_POD_COLORS, tileSize),
        "factions": {(name, look): {f: makeShadowed(facingRows(rows, name, f), enemyRoles(colors, fixed), tileSize) for f in FACINGS}
                     for look in EXPANSION_LOOKS for name, (rows, fixed) in factionPictures(look).items()},
        "spawner": makeShadowed(SPAWNER, enemyRoles(colors, SPAWNER_COLORS), tileSize),
        "campChests": {look: makeShadowed(CAMP_CHEST, enemyRoles(colors, campChestColors(look)), tileSize) for look in EXPANSION_LOOKS},
        "bonfire": [makeShadowed(rows, enemyRoles(colors, BONFIRE_COLORS), tileSize) for rows in BONFIRE],
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
