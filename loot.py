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

# Keyed by wall.name: the material each wall gives. Every wall rolls its amount from WALL_AMOUNTS.
WALL_LOOT = {
    "Wood Wall": "wood",
    "Stone Wall": "stone",
    "Sand Wall": "sand",
    "Gold Wall": "gold",
    "Coal Vein": "coal",
    "Copper Vein": "copper_ore",
    "Iron Vein": "iron_ore",
    "Silver Vein": "silver_ore",
    "Jade Vein": "rough_jade",
    "Peridot Vein": "rough_peridot",
    "Rose Quartz Vein": "rough_rose_quartz",
    "Ruby Vein": "rough_ruby",
    "Amethyst Vein": "rough_amethyst",
}

# A broken wall gives 0, 1 or 2 of its material, at these percent chances (with 1 Wisdom). Ore and gem veins
# give one more: 1, 2 or 3 at the same chances.
WALL_AMOUNTS = (80, 15, 5)
WISDOM_LUCK = 5         # each Wisdom point above 1 takes this many percent off getting nothing...
LEAST_NOTHING = 20      # ...down to this. What's taken off goes to 1 and 2 in their 15:5 ratio.


def isVein(source):
    return source.endswith(" Vein")


FIXED_WALLS = {"Gold Wall": 1}  # walls that always give exactly this many, whatever the roll


def wallRange(source):
    """(fewest, most) a wall can give: 0-2, 1-3 for an ore or gem vein, or a fixed amount (FIXED_WALLS)."""
    if source in FIXED_WALLS:
        return (FIXED_WALLS[source], FIXED_WALLS[source])
    return (1, 3) if isVein(source) else (0, 2)


def wallOdds(wisdom):
    """Percent chances of a broken wall giving its least, middle and most amount for this much Wisdom."""
    nothing, one, two = WALL_AMOUNTS
    less = min(nothing - LEAST_NOTHING, max(0, wisdom - 1) * WISDOM_LUCK)
    return (nothing - less, one + less * one / (one + two), two + less * two / (one + two))


def rollWall(source, wisdom):
    """[(material id, amount)] from breaking this wall: empty for nothing."""
    materialId = WALL_LOOT.get(source)
    if materialId is None:
        return []
    if source in FIXED_WALLS:
        return [(materialId, FIXED_WALLS[source])]
    least, middle, _ = wallOdds(wisdom)
    r = random.random() * 100
    amount = wallRange(source)[0] + (0 if r < least else 1 if r < least + middle else 2)
    return [(materialId, amount)] if amount else []

# Keyed by enemy.name (as spelled in enemies.py)
ENEMY_LOOT = {
    "Goblin": [("bone", 35, (1, 1)), ("scrap", 25, (1, 1))],
    "Goblin Chieftan": [("scrap", 60, (1, 2)), ("bone", 40, (1, 1)), ("relic:horned_crown", 2, (1, 1))],
    "Dire Rat": [("hide", 40, (1, 1)), ("meat", 50, (1, 1))],
    "Dire Mole": [("mole_claw", 30, (1, 1)), ("stone", 50, (1, 2)), ("meat", 40, (1, 1)), ("relic:mole_claws", 1, (1, 1))],
    "Unsealed": [("void_shard", 50, (1, 1)), ("gold", 100, (10, 20))],
    "Spiral Organizer": [("stone", 60, (1, 3)), ("bone", 20, (1, 1))],
    "Circle Organizer": [("sand", 60, (1, 3)), ("bone", 20, (1, 1))],
    "Square Organizer": [("wood", 60, (1, 3)), ("bone", 20, (1, 1))],
    "Plant Organizer": [("organizers_demise_seed", 60, (1, 2)), ("wood", 40, (1, 2)), ("relic:thornward_gloves", 8, (1, 1))],
}

# The tabs of the Loot Table window, in order
# Picking a plant (plants.Plant.pick) uses it up: in its harvest stage it gives its herb, in its seed stage its
# seeds, before it's ripe nothing. Keyed "<plant name> (harvest)" and "<plant name> (seeds)" (plantSource).
PLANT_LOOT = {f"{info['name']} ({'harvest' if stage == 'harvest' else 'seeds'})": [(info[part], 100, (1, 2))]
              for info in plants.PLANTS.values() for stage, part in (("harvest", "herb"), ("seed", "seed"))}

# Planted plants give PLANTED_BONUS more at both the fewest and the most (same keys, their own table).
PLANTED_BONUS = 1
CROP_LOOT = {source: [(m, chance, (low + PLANTED_BONUS, high + PLANTED_BONUS)) for m, chance, (low, high) in lines]
             for source, lines in PLANT_LOOT.items()}


def plantSource(plant, stage):
    """The PLANT_LOOT / CROP_LOOT key for picking this plant in this ripe stage."""
    return f"{plant.name} ({'harvest' if stage == 'harvest' else 'seeds'})"


def rollPick(plant, stage):
    """What picking this plant in this ripe stage gives (more for a planted one)."""
    return roll(CROP_LOOT if plant.planted else PLANT_LOOT, plantSource(plant, stage))


LOOT_TABS = [("Enemies", ENEMY_LOOT), ("Walls", WALL_LOOT), ("Plants", PLANT_LOOT), ("Crops", CROP_LOOT)]

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
