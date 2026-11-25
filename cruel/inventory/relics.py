import random

from cruel.inventory import items

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
    "lantern": {"name": "Lantern of the Deep", "slot": "Hands", "etype": "Light", "bonus": 3, "power": "searing_light"},
    "horned_crown": {"name": "Horned Crown", "slot": "Head", "etype": "Defense", "bonus": 1, "power": "goblin_fear"},
    "mole_claws": {"name": "Mole-King's Claws", "slot": "Gloves", "etype": "WallDamage", "bonus": 1, "power": "half_swings"},
    "hollow_blade": {"name": "Hollow Blade", "slot": "Hands", "etype": "Damage", "bonus": 8, "power": "lifedrinker"},
    "thornward_gloves": {"name": "Thornward Gloves", "slot": "Gloves", "etype": "Unique", "bonus": 0, "power": "demise_ward"},
    "vestigial_hand": {"name": "Discarded Vestigial Hand", "slot": "Back", "etype": "Unique", "bonus": 0, "power": "extra_hand"},
    "lightning_vambraces": {"name": "Lightning Vambraces", "slot": "Gloves", "etype": "Unique", "bonus": 0, "power": "lightning"},
    # Only ever dropped by a Dweller Queen (queen.py; followers.py)
    "pheromone_crown": {"name": "Pheromone Crown", "slot": "Head", "etype": "Defense", "bonus": 2, "power": "pheromones"},
    # Only ever in the chest at the middle of a Scorched Depths floor (not in CHEST_RELICS)
    "molten_blade": {"name": "Molten Blade", "slot": "Hands", "etype": "Damage", "bonus": 6, "power": "molten",
                     "scaling": ("strength", "intelligence")},
    # Only ever in the chest that appears when you kill SEALED_PATTERN_KILLS Unsealed on one floor (not in CHEST_RELICS)
    "sealed_pattern": {"name": "Sealed Pattern", "slot": "Gloves", "etype": "Unique", "bonus": 0, "power": "sealed_pattern"},
}

# Relics that only come by their own path: never in a vault's chest, never sold by the Gray Peddler
PATH_ONLY_RELICS = {"sealed_pattern"}

# Relics that can be in a chest: (relic id, first floor, floor types it can appear on or None for any)
CHEST_RELICS = [
    ("burrowers_amulet", 2, None),
    ("seal_fragment", 0, {"All Gold"}),
    ("lantern", 5, None),
    ("hollow_blade", 8, None),
    ("thornward_gloves", 2, None),
    ("vestigial_hand", 3, None),
    ("lightning_vambraces", 6, None),
]
RELIC_CHEST_CHANCE = 0.25  # chance that a floor has one relic chest (if any relic can appear there)

# What each effect does, in a few words (shown in the Character window and on item descriptions)
LIGHTNING_SPEED = 2  # Lightning Vambraces: added to your speed (actions each turn)
PHEROMONE_SPEED = 0.5  # Pheromone Crown: added to your speed
DARKVISION_RANGE = 12  # Potion Of Darkvision: how far you see without light
MOLTEN_FIRE = 2              # Molten Blade: fire damage added to every hit...
MOLTEN_IGNITE_CHANCE = 0.25  # ...and the chance that hit sets the enemy burning

WARD_RECHARGE_TURNS = 10  # after Ward blocks a hit, the turns until it can block another

# The Sealed Pattern. Kill SEALED_PATTERN_KILLS Unsealed on one floor and the rest die, no more come, and its chest
# appears at the floor's center. Worn, it costs max health but each free hand gives speed and Pitch damage on every hit,
# and the Pitch Bolt hotkey (F) fires a bolt of Pitch. Pitch is a damage type of its own: only an enemy's
# pitchResistance (flat) and pitchResistPercent (0-1) take anything off it.
SEALED_PATTERN_KILLS = 200
SEALED_PATTERN_HEALTH = 15       # max health it takes away (your max health never goes below 1)
SEALED_PATTERN_SPEED = 2         # speed for each free hand
SEALED_PATTERN_PITCH = 5         # Pitch damage added to every hit, for each free hand
PITCH_BOLT_DAMAGE = 5            # the Pitch Bolt's Pitch damage

EFFECTS = {
    "burrow": ("Burrow", "Burrow through soft walls"),
    "molten": ("Molten", "Immune to fire. Hits deal 2 more fire damage, 1 in 4 sets the enemy burning"),
    "seal_ward": ("Seal Ward", "The Unsealed don't appear"),
    "searing_light": ("Searing Light", "Enemies in your light take 1 damage each turn"),
    "goblin_fear": ("Dread", "Goblins sometimes flee instead of attacking"),
    "half_swings": ("Mole-King", "Breaking a wall takes half the swings"),
    "lifedrinker": ("Thirst", "1 in 4 hits heal 2 HP"),
    "demise_ward": ("Thornward", "Gather Organizer's Demise, and stand in it unharmed"),
    "far_sight": ("Far Sight", "+3 vision"),
    "gold_double": ("Greed", "Gold walls pay double"),
    "gold_per_kill": ("Gilded", "+3 gold per kill"),
    "ward": ("Ward", f"Blocks a hit completely, then is ready again {WARD_RECHARGE_TURNS} turns later"),
    "regen": ("Mending", "Heals 1 HP every 20 turns"),
    "see_enemies": ("Void Sight", "Enemies show through walls"),
    "extra_ore": ("Prospector", "+1 ore from every vein"),
    "bright": ("Bright", "+1 vision"),
    "hardy": ("Hardy", "+2 max health"),
    "lucky": ("Lucky", "+1 gold per kill"),
    "keen_eye": ("Keen Eye", "1 in 4 veins give an extra ore"),
    "extra_hand": ("Third Hand", "Grows another hand slot from your back"),
    "lightning": ("Lightning", f"+{LIGHTNING_SPEED} speed: more actions every turn"),
    "sealed_pattern": ("Sealed Pattern", f"-{SEALED_PATTERN_HEALTH} max health (never below 1). Each free hand: "
                       f"+{SEALED_PATTERN_SPEED} speed and +{SEALED_PATTERN_PITCH} Pitch damage on every hit. "
                       f"Pitch Bolt (F): fire a bolt for {PITCH_BOLT_DAMAGE} Pitch damage"),
    "pheromones": ("Pheromones", f"+{PHEROMONE_SPEED} speed. Every Dweller is hostile to you while you wear it, but now and then one beside you becomes your follower"),
    # Potions you drink that last a number of turns (PlayerClass.potionEffects)
    "darkvision": ("Darkvision", f"See {DARKVISION_RANGE} tiles in the dark, by no light: enemies aren't drawn to it, and walls still block it"),
    # Meals from the Cooking Pot (they last a number of turns; see recipes.MEALS and PlayerClass.buffs)
    "fed_mend": ("Mending", "Heals 1 HP every 5 turns"),
    "fed_guard": ("Sturdy", "+1 Defense"),
    "fed_strength": ("Fire Belly", "+2 damage"),
    "fed_fire": ("Heat-Proof", "+2 Fire Resist"),
    "fed_dig": ("Miner's Fill", "+2 wall damage"),
    "fed_thorns": ("Thorn Blood", "Enemies that hit you take 2 magic damage"),
    "fed_sick": ("Demise Sickness", "Lose 1 HP every 8 turns (never below 1)"),
    "fed_footwork": ("Light Feet", "+20% Clean Dodge"),
}

# A meal's drawbacks: they stay when you eat another meal (only the good part is replaced), and run their turns out
DRAWBACKS = {"fed_sick"}
THORN_DAMAGE = 2  # Demise Stew's Thorn Blood: magic damage to whatever hits you
SICK_TURNS = 8    # Demise Sickness: 1 HP lost this often

# Powers that are the relic itself: the Gilded Forge can't rekindle them away (the Hand would be just a hand)
BOUND_POWERS = {"extra_hand", "molten", "pheromones", "sealed_pattern"}  # (the Molten Blade without its fire is just a blade)

# Powers the Gilded Forge can give (not Burrow: that one is the Burrower's Amulet's alone)
FORGE_POWERS = ["half_swings", "goblin_fear", "seal_ward", "lifedrinker", "far_sight", "gold_double"]
POWER_TITLES = {"half_swings": "of the Mole-King", "goblin_fear": "of Dread", "seal_ward": "of the Seal",
                "lifedrinker": "of Thirst", "far_sight": "of the Deep", "gold_double": "of Greed"}

SEARING_DAMAGE = 1      # Lantern of the Deep: damage each turn to every enemy in your light
THIRST_CHANCE = 0.25    # Hollow Blade (and "of Thirst" gear): chance a hit heals
THIRST_HEAL = 2

# Powers that were changed or renamed: old saves get the new one (see gameManager.updateOldSave)
RENAMED_POWERS = {"steady_light": "searing_light"}

# The free minor enchantment a Masterwork craft gets, one of these at random
MINOR_ENCHANTS = ["bright", "hardy", "lucky", "keen_eye"]


def effectName(tag):
    return EFFECTS.get(tag, (tag, ""))[0]


def describe(tags):
    return "; ".join(EFFECTS[t][1] for t in tags if t in EFFECTS)


def make(relicId):
    """A fresh copy of a relic, ready to put in a chest or drop."""
    info = RELICS[relicId]
    scaling = info.get("scaling") or ("strength" if info["etype"] in ("Damage", "WallDamage", "Defense") else None)
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
