import random

import items

"""
Relics: rare items that can only be found, never crafted. Each one has a relic power, a special effect no
recipe gives. They turn up in chests on deeper floors, in vaults, and now and then from tough enemies.
Relics you don't want can be scrapped into Relic Dust at the Shrine of Unmaking, and the Gilded Forge can
put a relic power on a Masterwork item (reforging) or reroll a relic's power (rekindling).

Effects: every item can carry effect tags. Relics have item.relicPower; crafted gear can have item.enchants
(gold recipes, and the free minor enchantment on Masterwork gear). player.effects() collects them all from
what's equipped, and the game checks them by name, e.g. player.hasEffect("half_swings").
"""

# id -> what the relic is. etype/bonus work like any equipment (a "Light" bonus adds to vision).
RELICS = {
    "burrowers_amulet": {"name": "Burrower's Amulet", "slot": "Neck", "etype": "Unique", "bonus": 0, "power": "burrow"},
    "seal_fragment": {"name": "Seal Fragment", "slot": "Neck", "etype": "Unique", "bonus": 0, "power": "seal_ward"},
    "lantern": {"name": "Lantern of the Deep", "slot": "Hands", "etype": "Light", "bonus": 3, "power": "steady_light"},
    "horned_crown": {"name": "Horned Crown", "slot": "Head", "etype": "Defense", "bonus": 1, "power": "goblin_fear"},
    "mole_claws": {"name": "Mole-King's Claws", "slot": "Gloves", "etype": "WallDamage", "bonus": 1, "power": "half_swings"},
    "hollow_blade": {"name": "Hollow Blade", "slot": "Hands", "etype": "Damage", "bonus": 8, "power": "lifedrinker"},
}

# Relics that can be in a chest: (relic id, first floor, floor types it can appear on or None for any)
CHEST_RELICS = [
    ("burrowers_amulet", 2, None),
    ("seal_fragment", 0, {"All Gold"}),
    ("lantern", 5, None),
    ("hollow_blade", 8, None),
]
RELIC_CHEST_CHANCE = 0.25  # chance that a floor has one relic chest (if any relic can appear there)

# What each effect does, in a few words (shown in the Character window and on item descriptions)
EFFECTS = {
    "burrow": ("Burrow", "Burrow through soft walls"),
    "seal_ward": ("Seal Ward", "The Unsealed don't appear"),
    "steady_light": ("Steady Light", "Your light never flickers"),
    "goblin_fear": ("Dread", "Goblins sometimes flee instead of attacking"),
    "half_swings": ("Mole-King", "Breaking a wall takes half the swings"),
    "lifedrinker": ("Thirst", "Each kill heals 2 HP"),
    "far_sight": ("Far Sight", "+3 vision"),
    "gold_double": ("Greed", "Gold walls pay double"),
    "gold_per_kill": ("Gilded", "+3 gold per kill"),
    "ward": ("Ward", "The first hit on each floor does nothing"),
    "regen": ("Mending", "Heals 1 HP every 20 turns"),
    "see_enemies": ("Void Sight", "Enemies show through walls"),
    "extra_ore": ("Prospector", "+1 ore from every vein"),
    "bright": ("Bright", "+1 vision"),
    "hardy": ("Hardy", "+2 max health"),
    "lucky": ("Lucky", "+1 gold per kill"),
    "keen_eye": ("Keen Eye", "1 in 4 veins give an extra ore"),
}

# Powers the Gilded Forge can give (not Burrow: that one is the Burrower's Amulet's alone)
FORGE_POWERS = ["half_swings", "goblin_fear", "seal_ward", "lifedrinker", "far_sight", "gold_double"]
POWER_TITLES = {"half_swings": "of the Mole-King", "goblin_fear": "of Dread", "seal_ward": "of the Seal",
                "lifedrinker": "of Thirst", "far_sight": "of the Deep", "gold_double": "of Greed"}

# The free minor enchantment a Masterwork craft gets, one of these at random
MINOR_ENCHANTS = ["bright", "hardy", "lucky", "keen_eye"]


def effectName(tag):
    return EFFECTS.get(tag, (tag, ""))[0]


def describe(tags):
    return "; ".join(EFFECTS[t][1] for t in tags if t in EFFECTS)


def make(relicId):
    """A fresh copy of a relic, ready to put in a chest or drop."""
    info = RELICS[relicId]
    scaling = "strength" if info["etype"] in ("Damage", "WallDamage", "Defense") else None
    item = items.equipment(info["etype"], info["name"], info["slot"], info["bonus"], describe([info["power"]]), attributeScaling=scaling)
    item.relic = True
    item.relicId = relicId
    item.relicPower = info["power"]
    item.baseName = info["name"]
    return item


def isRelic(item):
    return getattr(item, "relic", False)


def chestRelics(depth, proportion):
    """The relics a chest on this floor could hold."""
    return [rid for rid, firstFloor, floorTypes in CHEST_RELICS
            if depth >= firstFloor and (floorTypes is None or proportion in floorTypes)]


def givePower(item, power):
    """Turns an item into a relic with this power (the Gilded Forge). It keeps its stats and slot."""
    item.relic = True
    item.relicPower = power
    item.baseName = getattr(item, "baseName", item.name)
    item.name = f"{item.baseName} {POWER_TITLES[power]}"
    item.description = describe([power] + list(getattr(item, "enchants", [])))


def newPower(item):
    """A random forge power, different from the one the item has now."""
    return random.choice([p for p in FORGE_POWERS if p != getattr(item, "relicPower", None)])
