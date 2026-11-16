import random

import plants
import relics
import resources

"""
Every drop chance in one place. The game rolls drops from these tables, and the in-game Loot Table window
(T) reads the same tables, so what the window says is always what actually happens.

Each line is (material id, chance in percent, (fewest, most)) and is rolled separately, so a kill can give
nothing, one thing, or several. "gold" means gold coins (player.gold), not a pouch material, and
"relic:<id>" is a relic item (see relics.py).
"""

# Keyed by wall.name
WALL_LOOT = {
    "Wood Wall": [("wood", 100, (1, 2))],
    "Stone Wall": [("stone", 100, (1, 1))],
    "Sand Wall": [("sand", 100, (1, 2))],
    "Gold Wall": [("gold", 100, (1, 1))],
    "Coal Vein": [("coal", 100, (2, 3))],
    "Copper Vein": [("copper_ore", 100, (1, 2))],
    "Iron Vein": [("iron_ore", 100, (1, 2))],
    "Silver Vein": [("silver_ore", 100, (1, 1))],
    "Jade Vein": [("rough_jade", 100, (1, 1))],
    "Peridot Vein": [("rough_peridot", 100, (1, 1))],
    "Rose Quartz Vein": [("rough_rose_quartz", 100, (1, 1))],
    "Ruby Vein": [("rough_ruby", 100, (1, 1))],
    "Amethyst Vein": [("rough_amethyst", 100, (1, 1))],
}

# Keyed by enemy.name (as spelled in enemies.py)
ENEMY_LOOT = {
    "Goblin": [("bone", 35, (1, 1)), ("scrap", 25, (1, 1))],
    "Goblin Chieftan": [("scrap", 60, (1, 2)), ("bone", 40, (1, 1)), ("relic:horned_crown", 2, (1, 1))],
    "Dire Rat": [("hide", 40, (1, 1))],
    "Dire Mole": [("mole_claw", 30, (1, 1)), ("stone", 50, (1, 2)), ("relic:mole_claws", 1, (1, 1))],
    "Unsealed": [("void_shard", 50, (1, 1)), ("gold", 100, (10, 20))],
}

# The tabs of the Loot Table window, in order
# Keyed by the plant's name: its herb, and sometimes a seed to plant
PLANT_LOOT = {info["name"]: [(info["herb"], 100, (1, 2)), (info["seed"], plants.SEED_CHANCE, (1, 1))]
              for info in plants.PLANTS.values()}

LOOT_TABS = [("Enemies", ENEMY_LOOT), ("Walls", WALL_LOOT), ("Plants", PLANT_LOOT)]

# Nicer names for the window where the code's names differ
DISPLAY_NAMES = {"Goblin Chieftan": "Goblin Chieftain", "Unsealed": "The Unsealed"}


def displayName(source):
    return DISPLAY_NAMES.get(source, source)


GOLD_COLOR = (226, 181, 68)
RELIC_COLOR = (232, 192, 96)


def isRelicDrop(dropId):
    return dropId.startswith("relic:")


def dropName(dropId):
    if isRelicDrop(dropId):
        return relics.RELICS[dropId[6:]]["name"]
    return resources.materialName(dropId)


def dropColor(dropId):
    if dropId == "gold":
        return GOLD_COLOR
    if isRelicDrop(dropId):
        return RELIC_COLOR
    return resources.MATERIALS[dropId][2]


def roll(table, source):
    """Rolls every line for this source. Returns [(material id, amount), ...] for the lines that hit."""
    drops = []
    for materialId, chance, (fewest, most) in table.get(source, []):
        if random.random() * 100 < chance:
            drops.append((materialId, random.randint(fewest, most)))
    return drops


def discoveryKey(source, materialId=None):
    """What the player's lootFound set stores: a source once it's been killed or broken, and each drop once
    it has dropped. The Loot Table window shows ??? for anything not in the set yet."""
    return source if materialId is None else f"{source}:{materialId}"
