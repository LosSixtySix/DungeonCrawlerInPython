import math
import random

import items
import plants
import relics

"""
Every crafting recipe, the crafting stations, and the quality roll for crafted gear.

A recipe is made at a station. "By Hand" needs nothing; the others have to be crafted (or found) first and
are kept in player.stations. The heavy ones (Smelter, Anvil and the two relic stations) also have to be set up
on the floor beside you before you can use them, which takes turns, and packing them up takes as long again.
Crafting takes turns too (enemies move during them), and the materials are only spent when a craft finishes,
so a craft that gets interrupted costs nothing. "gold" in a recipe's needs is the player's gold, the same gold
that pays for leveling up.
"""

# id -> name, turns to set up (and to pack up again, 0 = works anywhere), HP once set up, and for the two
# found-only stations where they turn up. The order is the order of the tabs in the Crafting window.
STATION_INFO = {
    "hand": {"name": "By Hand", "setup": 0, "hp": 0},
    "workbench": {"name": "Workbench", "setup": 0, "hp": 0},
    "smelter": {"name": "Smelter", "setup": 3, "hp": 60},
    "anvil": {"name": "Anvil", "setup": 2, "hp": 120},
    "jeweler": {"name": "Jeweler's Kit", "setup": 0, "hp": 0},
    "alchemist": {"name": "Alchemist's Set", "setup": 0, "hp": 0},
    "cauldron": {"name": "Cauldron", "setup": 3, "hp": 140},
    "shrine": {"name": "Shrine of Unmaking", "setup": 4, "hp": 200, "found": "Vaults sealed in gold walls, floor 5 and deeper"},
    "forge": {"name": "Gilded Forge", "setup": 5, "hp": 220, "found": "Vaults on All Gold floors, floor 8 and deeper"},
}
STATIONS = list(STATION_INFO)
TAB_NAMES = {"hand": "By Hand", "workbench": "Workbench", "smelter": "Smelter", "anvil": "Anvil", "jeweler": "Jeweler",
             "alchemist": "Alchemy", "cauldron": "Cauldron", "shrine": "Shrine", "forge": "Forge"}


class Station():
    """A set-up station standing on the map (tile type 7). Found stations start unclaimed: walk up to one and
    interact to claim it. Enemies that dig can damage a claimed station; at 0 HP it's destroyed."""

    def __init__(self, stationId, claimed=True):
        self.id = stationId
        self.name = STATION_INFO[stationId]["name"]
        self.maxHp = STATION_INFO[stationId]["hp"]
        self.hp = self.maxHp
        self.claimed = claimed


# Quality: (name, stat multiplier). Crude rounds down, the others round to the nearest; every stat is at least 1.
QUALITIES = [("Crude", 0.75), ("Common", 1.0), ("Fine", 1.25), ("Masterwork", 1.5)]


def qualityWeights(intelligenceBonus):
    """Relative chances of each quality. Intelligence (player.attributeBonuses["intelligence"]) moves the odds
    away from Crude and towards Fine and Masterwork."""
    b = intelligenceBonus
    return {"Crude": max(5, 30 - 2 * b), "Common": 45, "Fine": 20 + 2 * b, "Masterwork": 5 + b}


def qualityOdds(intelligenceBonus):
    """[(quality, percent)] for showing in the Crafting window."""
    weights = qualityWeights(intelligenceBonus)
    total = sum(weights.values())
    return [(name, round(weights[name] / total * 100)) for name, _ in QUALITIES]


def rollQuality(intelligenceBonus):
    weights = qualityWeights(intelligenceBonus)
    return random.choices(list(weights), weights=list(weights.values()))[0]


def scaleStat(bonus, quality):
    multiplier = dict(QUALITIES)[quality]
    value = bonus * multiplier
    value = math.floor(value) if quality == "Crude" else math.floor(value + 0.5)
    return max(1, value)


class Recipe():
    """kind:
    "station"  makes a station (unlocks its tab)        "upgrade"  the Leather Pouch (bigger stacks)
    "material" goes in the pouch                         "item"     gear: rolls a quality
    "potion"   a consumable in your inventory (amount of them), no quality roll
    "plant"    sows a seed (makes = plant kind) on the floor tile you face
    "setup" / "pack"   set a heavy station up beside you, or pack it away again
    "scrap" / "reforge" / "rekindle"   the relic stations' recipes, made for one item in your pack (target)
    For items, makeItem(bonus, bonus2) builds the equipment; bonus (and bonus2 for two-stat gear) are the
    Common-quality stats. enchants are effect tags the item always has (see relics.EFFECTS)."""

    def __init__(self, recipeId, name, station, turns, needs, kind, description, result,
                 makes=None, amount=1, makeItem=None, bonus=0, bonus2=0, enchants=(), target=None):
        self.id = recipeId
        self.name = name
        self.station = station
        self.turns = turns
        self.needs = needs          # material id (or "gold") -> count
        self.kind = kind
        self.description = description
        self.result = result        # short summary of what it makes, for the window
        self.makes = makes          # station id or material id
        self.amount = amount
        self.makeItem = makeItem
        self.bonus = bonus
        self.bonus2 = bonus2
        self.enchants = list(enchants)
        self.target = target        # the item a relic-station recipe works on

    def build(self, quality):
        """The finished item at this quality, named like "Fine Stone Pick" (Common has no prefix). Masterwork
        gear also gets a free minor enchantment."""
        item = self.makeItem(scaleStat(self.bonus, quality), scaleStat(self.bonus2, quality) if self.bonus2 else 0)
        item.quality = quality
        item.baseName = item.name
        item.enchants = list(self.enchants)
        if quality == "Masterwork":
            item.enchants.append(random.choice(relics.MINOR_ENCHANTS))
        if quality != "Common":
            item.name = f"{quality} {item.name}"
        if item.enchants:
            item.description = relics.describe(item.enchants)
        return item


def potion(name, effect, power=0, scaling=None):
    """makeItem for a potion (a consumable). Potions don't roll a quality."""
    return lambda b, b2: items.consumable(name, power, effect, attributeScaling=scaling)


def gear(etype, name, slot, scaling="strength"):
    """makeItem for one-stat gear."""
    return lambda b, b2: items.equipment(etype, name, slot, b, attributeScaling=scaling)


FIRE_FLASK_DAMAGE = 5
SMOKE_TURNS = 5

RECIPES = [
    # ---- By hand
    Recipe("workbench", "Workbench", "hand", 3, {"wood": 6, "stone": 4}, "station",
           "A folding bench you carry with you. Works anywhere.", "Unlocks the Workbench", makes="workbench"),
    Recipe("handle", "Wooden Handle", "hand", 1, {"wood": 2}, "material",
           "Goes into every pick and weapon.", "1 Wooden Handle", makes="handle"),
    Recipe("torch", "Torch", "hand", 1, {"wood": 1, "coal": 1}, "item",
           "Pushes your light out further.", "Hands  Vision +2", bonus=2, makeItem=gear("Light", "Torch", "Hands", None)),

    # ---- Workbench
    Recipe("stone_pick", "Stone Pick", "workbench", 2, {"handle": 1, "stone": 3}, "item",
           "Digs faster than a worn pick.", "Hands  Wall Damage +2", bonus=2, makeItem=gear("WallDamage", "Stone Pick", "Hands")),
    Recipe("club", "Wooden Club", "workbench", 2, {"wood": 4}, "item",
           "Crude, but better than fists.", "Hands  Damage +2", bonus=2, makeItem=gear("Damage", "Wooden Club", "Hands")),
    Recipe("wooden_shield", "Wooden Shield", "workbench", 2, {"wood": 5, "stone": 1}, "item",
           "Blocks a little of every hit.", "Hands  Defense +1", bonus=1, makeItem=gear("Defense", "Wooden Shield", "Hands")),
    Recipe("leather_pouch", "Leather Pouch", "workbench", 2, {"hide": 3}, "upgrade",
           "Stitched to your belt. Carry twice as much of everything.", "Stacks 99 to 199"),
    Recipe("smelter", "Portable Smelter", "workbench", 4, {"stone": 10, "sand": 4, "copper_ore": 2}, "station",
           "A clay furnace small enough to carry. Set it up beside you to use it.", "Unlocks the Smelter", makes="smelter"),
    Recipe("alchemist", "Alchemist's Set", "workbench", 3, {"glass": 2, "wood": 3, "stone": 2}, "station",
           "Vials, a mortar and a little burner. Works anywhere.", "Unlocks the Alchemist's Set", makes="alchemist"),

    # ---- Smelter (every smelt burns a Coal)
    Recipe("copper_ingot", "Copper Ingot", "smelter", 2, {"copper_ore": 2, "coal": 1}, "material",
           "Soft metal for early tools.", "1 Copper Ingot", makes="copper_ingot"),
    Recipe("iron_ingot", "Iron Ingot", "smelter", 2, {"iron_ore": 2, "coal": 1}, "material",
           "The backbone of most gear.", "1 Iron Ingot", makes="iron_ingot"),
    Recipe("scrap_melt", "Melt Scrap", "smelter", 2, {"scrap": 2, "coal": 1}, "material",
           "Goblin junk back into ore.", "1 Iron Ore", makes="iron_ore"),
    Recipe("silver_ingot", "Silver Ingot", "smelter", 2, {"silver_ore": 2, "coal": 1}, "material",
           "For jewelry.", "1 Silver Ingot", makes="silver_ingot"),
    Recipe("glass", "Glass", "smelter", 2, {"sand": 2, "coal": 1}, "material",
           "For lenses.", "1 Glass", makes="glass"),
    Recipe("anvil", "Anvil", "smelter", 5, {"iron_ingot": 6, "stone": 4}, "station",
           "Cast in one piece. Heavy, but it folds into your pack.", "Unlocks the Anvil", makes="anvil"),

    # ---- Anvil
    Recipe("copper_pick", "Copper Pick", "anvil", 3, {"handle": 1, "copper_ingot": 2}, "item",
           "Mines Coal and Copper veins at full speed.", "Hands  Wall Damage +3", bonus=3, makeItem=gear("WallDamage", "Copper Pick", "Hands")),
    Recipe("iron_pick", "Iron Pick", "anvil", 3, {"handle": 1, "iron_ingot": 3}, "item",
           "Mines most walls at full speed and finds extra ore.", "Hands  Wall Damage +5", bonus=5, enchants=["extra_ore"],
           makeItem=gear("WallDamage", "Iron Pick", "Hands")),
    Recipe("iron_sword", "Iron Sword", "anvil", 3, {"handle": 1, "iron_ingot": 3}, "item",
           "A real weapon at last.", "Hands  Damage +5", bonus=5, makeItem=gear("Damage", "Iron Sword", "Hands")),
    Recipe("war_pick", "War Pick", "anvil", 4, {"handle": 1, "iron_ingot": 2, "copper_ingot": 1}, "item",
           "Fights and digs.", "Hands  Damage +4  Wall +2", bonus=4, bonus2=2,
           makeItem=lambda b, b2: items.dualEquipment("DaWa", "War Pick", "Hands", b, b2, attributeScaling="strength")),
    Recipe("iron_helm", "Iron Helm", "anvil", 3, {"iron_ingot": 3}, "item",
           "First thing in the Head slot.", "Head  Defense +2", bonus=2, makeItem=gear("Defense", "Iron Helm", "Head")),
    Recipe("chainmail", "Chainmail", "anvil", 5, {"iron_ingot": 5}, "item",
           "Hundreds of tiny rings.", "Chest  Defense +3", bonus=3, makeItem=gear("Defense", "Chainmail", "Chest")),
    Recipe("iron_greaves", "Iron Greaves", "anvil", 4, {"iron_ingot": 4}, "item",
           "Shins of iron.", "Legs  Defense +2", bonus=2, makeItem=gear("Defense", "Iron Greaves", "Legs")),
    Recipe("hide_boots", "Hide Boots", "anvil", 2, {"hide": 2, "iron_ingot": 1}, "item",
           "Iron toes, soft soles.", "Feet  Defense +1", bonus=1, makeItem=gear("Defense", "Hide Boots", "Feet")),
    Recipe("digging_gauntlets", "Digging Gauntlets", "anvil", 3, {"iron_ingot": 2, "hide": 1, "mole_claw": 1}, "item",
           "Stacks with your pick.", "Gloves  Wall Damage +2", bonus=2, makeItem=gear("WallDamage", "Digging Gauntlets", "Gloves")),
    Recipe("gilded_pick", "Gilded Pick", "anvil", 4, {"handle": 1, "iron_ingot": 3, "gold": 35}, "item",
           "Slowly pays for itself.", "Hands  Wall Damage +5", bonus=5, enchants=["gold_double"],
           makeItem=gear("WallDamage", "Gilded Pick", "Hands")),
    Recipe("gilded_sword", "Gilded Iron Sword", "anvil", 4, {"handle": 1, "iron_ingot": 3, "gold": 40}, "item",
           "Gold worked into the blade.", "Hands  Damage +5", bonus=5, enchants=["gold_per_kill"],
           makeItem=gear("Damage", "Gilded Iron Sword", "Hands")),
    Recipe("warded_chainmail", "Warded Chainmail", "anvil", 6, {"iron_ingot": 5, "gold": 50}, "item",
           "Gold runes woven through the rings.", "Chest  Defense +3", bonus=3, enchants=["ward"],
           makeItem=gear("Defense", "Warded Chainmail", "Chest")),
    Recipe("jeweler", "Jeweler's Kit", "anvil", 3, {"silver_ingot": 2, "glass": 1, "wood": 2}, "station",
           "Fine tools and a lens. Works anywhere.", "Unlocks the Jeweler's Kit", makes="jeweler"),
    Recipe("cauldron", "Cauldron", "anvil", 4, {"iron_ingot": 5, "copper_ingot": 2}, "station",
           "A heavy iron pot. It has to be set up, but it brews stronger potions.", "Unlocks the Cauldron", makes="cauldron"),

    # ---- Jeweler's Kit
    *[Recipe(f"cut_{gem}", f"Cut {name}", "jeweler", 2, {f"rough_{gem}": 1}, "material",
             "Facets bring out the light.", f"1 Cut {name}", makes=f"cut_{gem}")
      for gem, name in (("jade", "Jade"), ("peridot", "Peridot"), ("rose_quartz", "Rose Quartz"),
                        ("ruby", "Ruby"), ("amethyst", "Amethyst"))],
    Recipe("silver_amulet", "Silver Amulet", "jeweler", 3, {"silver_ingot": 2}, "item",
           "A plain silver chain.", "Neck  Health +3", bonus=3, makeItem=gear("Health", "Silver Amulet", "Neck", None)),
    Recipe("jade_amulet", "Jade Amulet", "jeweler", 4, {"silver_ingot": 1, "cut_jade": 1}, "item",
           "Cool green stone that turns a blade.", "Neck  Defense +1", bonus=1,
           makeItem=gear("Defense", "Jade Amulet", "Neck", None)),
    Recipe("rose_amulet", "Rose Quartz Amulet", "jeweler", 4, {"silver_ingot": 1, "cut_rose_quartz": 1}, "item",
           "Coins seem to find you.", "Neck  Health +4", bonus=4, enchants=["lucky"],
           makeItem=gear("Health", "Rose Quartz Amulet", "Neck", None)),
    Recipe("sight_amulet", "Amulet of Sight", "jeweler", 4, {"silver_ingot": 1, "glass": 1, "cut_peridot": 1}, "item",
           "A peridot lens set in silver.", "Neck  Vision +1", bonus=1, makeItem=gear("Light", "Amulet of Sight", "Neck", None)),
    Recipe("gilded_amulet", "Gilded Amulet", "jeweler", 5, {"silver_ingot": 1, "cut_ruby": 1, "gold": 60}, "item",
           "Warm to the touch.", "Neck  Health +6", bonus=6, enchants=["regen"], makeItem=gear("Health", "Gilded Amulet", "Neck", None)),
    Recipe("void_amulet", "Void Amulet", "jeweler", 6, {"void_shard": 3, "cut_amethyst": 2, "gold": 80}, "item",
           "It hums when something is near.", "Neck  Health +8", bonus=8, enchants=["see_enemies"],
           makeItem=gear("Health", "Void Amulet", "Neck", None)),

    # ---- Planting (By Hand): a seed on the floor tile you face
    *[Recipe(f"plant_{kind}", f"Plant {info['name']}", "hand", 1, {info["seed"]: 1}, "plant",
             f"Sow it on the floor tile you're facing. {plants.plantDescription(kind)}; planted ones never wither. "
             "Plants spread like the Game of Life: an empty tile with 3 of a kind around it sprouts one.",
             f"1 {info['name']} (yours)", makes=kind)
      for kind, info in plants.PLANTS.items()],

    # ---- Alchemist's Set (works anywhere; small brews)
    Recipe("minor_healing", "Minor Healing Potion", "alchemist", 2, {"glass": 1, "hearthmoss": 1}, "potion",
           "Moss steeped in a vial. A thin green tonic.", "Heals 3 (+WIS)", makeItem=potion("Minor Healing Potion", "Heal", 3, "wisdom")),
    Recipe("door_potion", "Potion Of Door", "alchemist", 3, {"glass": 1, "glowcap": 2}, "potion",
           "Glowcaps lean toward the way down.", "Shows the way to the next floor", makeItem=potion("Potion Of Door", "DoorLocate")),

    Recipe("smoke_bomb", "Smoke Bomb", "alchemist", 3, {"glass": 1, "shadowfern": 2, "coal": 1}, "potion",
           "Burning fern and a lot of smoke.", f"Hides you for {SMOKE_TURNS} turns", makeItem=potion("Smoke Bomb", "Smoke", SMOKE_TURNS)),

    # ---- Cauldron (has to be set up; stronger brews)
    Recipe("healing", "Healing Potion", "cauldron", 2, {"glass": 1, "bloodcap": 1, "hearthmoss": 1, "coal": 1}, "potion",
           "Simmered slowly over coals.", "Heals 6 (+WIS)", makeItem=potion("Healing Potion", "Heal", 6, "wisdom")),
    Recipe("greater_healing", "Greater Healing Potion", "cauldron", 4, {"glass": 1, "bloodcap": 2, "hearthmoss": 2, "cut_ruby": 1}, "potion",
           "A ruby dissolved into it. It glows.", "Heals 12 (+WIS)", makeItem=potion("Greater Healing Potion", "Heal", 12, "wisdom")),
    Recipe("door_potion_2", "Potion Of Door (x2)", "cauldron", 3, {"glass": 2, "glowcap": 2, "coal": 1}, "potion",
           "Two caps go further in a big pot.", "2 potions that show the way down", amount=2,
           makeItem=potion("Potion Of Door", "DoorLocate")),
    Recipe("fire_flask", "Fire Flask", "cauldron", 3, {"glass": 1, "emberroot": 2, "coal": 1}, "potion",
           "Throw it and everything in your light burns.", f"{FIRE_FLASK_DAMAGE} damage to every enemy in your light",
           makeItem=potion("Fire Flask", "Fire", FIRE_FLASK_DAMAGE)),
]

SCRAP_GOLD, REFORGE_GOLD, REKINDLE_GOLD = 40, 150, 100



def forStation(station):
    return [r for r in RECIPES if r.station == station]


def stationRecipe(station):
    """The recipe that makes a station, or None for "hand" and the found-only stations."""
    return next((r for r in RECIPES if r.kind == "station" and r.makes == station), None)


def setupRecipe(station):
    info = STATION_INFO[station]
    return Recipe("setup_" + station, f"Set up {info['name']}", station, info["setup"], {}, "setup",
                  f"Placed on the floor beside you. You must stand next to it to use it. Enemies that dig can damage it ({info['hp']} HP).",
                  "Ready to use")


def packRecipe(station):
    info = STATION_INFO[station]
    return Recipe("pack_" + station, f"Pack up {info['name']}", station, info["setup"], {}, "pack",
                  "Folds it back into your pack, repaired. Leave it standing and it stays on this floor.", "Back in your pack")


def relicStationRecipes(station, inventory):
    """The Shrine's and the Forge's recipes, one for each item in your pack they can work on."""
    out = []
    for item in inventory:
        if station == "shrine" and relics.isRelic(item):
            out.append(Recipe("scrap", f"Scrap {item.name}", "shrine", 6, {"gold": SCRAP_GOLD}, "scrap",
                              f"Destroys the relic for its dust. {SCRAP_GOLD} gold of fuel.", "3 Relic Dust, maybe a Void Shard",
                              target=item))
        elif station == "forge" and relics.isRelic(item):
            out.append(Recipe("rekindle", f"Rekindle {item.name}", "forge", 8, {"relic_dust": 2, "gold": REKINDLE_GOLD}, "rekindle",
                              f"Burns away its relic power for a different one. {REKINDLE_GOLD} gold of fuel.", "A new relic power",
                              target=item))
        elif station == "forge" and getattr(item, "quality", None) == "Masterwork":
            out.append(Recipe("reforge", f"Reforge {item.name}", "forge", 10, {"relic_dust": 3, "void_shard": 2, "gold": REFORGE_GOLD},
                              "reforge", f"Keeps its stats and slot, and adds a random relic power. {REFORGE_GOLD} gold of fuel.",
                              "A relic", target=item))
    return out
