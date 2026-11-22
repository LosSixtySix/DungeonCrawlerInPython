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
    "cooking_pot": {"name": "Cooking Pot", "setup": 0, "hp": 0},
    "cauldron": {"name": "Cauldron", "setup": 3, "hp": 140},
    "shrine": {"name": "Shrine of Unmaking", "setup": 4, "hp": 200, "found": "Vaults sealed in gold walls, floor 5 and deeper"},
    "forge": {"name": "Gilded Forge", "setup": 5, "hp": 220, "found": "Vaults on All Gold floors, floor 8 and deeper"},
}
STATIONS = list(STATION_INFO)
TAB_NAMES = {"hand": "By Hand", "workbench": "Workbench", "smelter": "Smelter", "anvil": "Anvil", "jeweler": "Jeweler",
             "alchemist": "Alchemy", "cooking_pot": "Cooking", "cauldron": "Cauldron", "shrine": "Shrine", "forge": "Forge"}


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
    away from Crude and towards Fine and Masterwork. At INT 1 (bonus 0) it's 55% Crude, 45% Common, and no Fine
    or Masterwork at all."""
    b = intelligenceBonus
    return {"Crude": max(5, 55 - 2.5 * b), "Common": 45, "Fine": 2 * b, "Masterwork": 0.75 * b}


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
    "salvage"  takes a crafted item in your pack (target) apart at the station that made it, for some materials
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
        item.recipeId = self.id
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


def meal(name, heal, buffs):
    """makeItem for a meal from the Cooking Pot: a consumable (effect "Meal") that heals a little and gives
    buffs, {effect tag: turns}, for a while after (see PlayerClass.eat). Meals don't roll a quality."""
    def make(b, b2):
        item = items.consumable(name, heal, "Meal")
        item.buffs = dict(buffs)
        return item
    return make


def mealResult(heal, buffs):
    """The short "what it makes" line for a meal recipe, e.g. "Heals 3  Hearty 80t"."""
    return f"Heals {heal}  " + ", ".join(f"{relics.effectName(tag)} {turns}t" for tag, turns in buffs.items())


# The Cooking Pot's meals: (id, name, turns to cook, needs, heal, {buff: turns}, description). Raw Meat comes
# from Dire Rats and Dire Moles. Demise Stew is the one with a drawback: its sickness comes with its powers.
MEALS = [
    ("roast_meat", "Roast Meat", 2, {"meat": 1}, 3, {"hardy": 80},
     "Meat on a stick over the pot's coals. Plain, but it fills you up."),
    ("bloodcap_stew", "Bloodcap Stew", 3, {"meat": 1, "bloodcap": 1}, 4, {"fed_mend": 40},
     "A dark red stew. Your cuts close while it settles."),
    ("hearthmoss_skewers", "Hearthmoss Skewers", 2, {"meat": 1, "hearthmoss": 1}, 3, {"fed_guard": 80},
     "Meat wrapped in warm moss. Blows land softer on a full stomach."),
    ("glowcap_broth", "Glowcap Broth", 2, {"meat": 1, "glowcap": 1}, 2, {"far_sight": 60},
     "A thin broth that makes your eyes glimmer."),
    ("emberroot_chili", "Emberroot Chili", 3, {"meat": 1, "emberroot": 1}, 2, {"fed_strength": 60, "fed_fire": 60},
     "Hot enough to hurt. Your swings hit harder and fire bothers you less."),
    ("shadowfern_wrap", "Shadowfern Wrap", 2, {"meat": 1, "shadowfern": 1}, 2, {"see_enemies": 40},
     "Meat rolled in bitter fern. For a while you feel things moving behind the walls."),
    ("miners_hotpot", "Miner's Hotpot", 4, {"meat": 2, "hearthmoss": 1, "glowcap": 1}, 4, {"fed_dig": 100, "bright": 100},
     "A heavy pot of meat and moss with glowcaps on top. Good for a long dig."),
    ("hunters_feast", "Hunter's Feast", 4, {"meat": 2, "bloodcap": 1, "emberroot": 1}, 5, {"fed_strength": 80, "hardy": 80},
     "Two cuts, seared with emberroot and bloodcap. The best meal the pot makes."),
    ("quickstep_skewers", "Quickstep Skewers", 2, {"meat": 1, "shadowfern": 1, "glowcap": 1}, 2, {"fed_footwork": 60},
     "Light, bitter and bright. You're quicker on your feet: a blow you slip is more likely to miss you entirely."),
    ("demise_stew", "Demise Stew", 3, {"meat": 1, "organizers_demise": 1}, 1,
     {"demise_ward": 60, "fed_thorns": 60, "fed_sick": 60},
     "Meat boiled with Organizer's Demise. Its thorns grow in your blood, and it makes you sick."),
]


def gear(etype, name, slot, scaling="strength"):
    """makeItem for one-stat gear."""
    return lambda b, b2: items.equipment(etype, name, slot, b, attributeScaling=scaling)


BACKPACK_SLOTS = 5  # one more row of the Inventory window
POTION_BELT_STACK = 5  # how many of the same potion share an inventory slot while a Potion Belt is worn
FIRE_FLASK_DAMAGE = 5
SMOKE_TURNS = 12  # a Smoke Bomb's cloud lingers this long (it thins out over its last SMOKE_THIN_TURNS)
DEMISE_FLASK_DAMAGE = 5
BOMB_FLASK_DAMAGE = 10
BOMB_WALL_DAMAGE = 20

RECIPES = [
    # ---- By hand
    Recipe("workbench", "Workbench", "hand", 3, {"wood": 6, "stone": 4}, "station",
           "A folding bench you carry with you. Works anywhere.", "Unlocks the Workbench", makes="workbench"),
    Recipe("handle", "Wooden Handle", "hand", 1, {"wood": 2}, "material",
           "Goes into every pick and weapon.", "1 Wooden Handle", makes="handle"),
    Recipe("torch", "Torch", "hand", 1, {"wood": 1, "coal": 1}, "item",
           "Pushes your light out further.", "Hands  Vision +2", bonus=2, makeItem=gear("Light", "Torch", "Hands", None)),
    Recipe("glowrock", "Glowrock", "hand", 1, {"stone": 1, "glowcap": 1}, "potion",
           "A stone rubbed with crushed Glowcap. Set it down and it glows faintly.",
           "Set down: a dim light on its tile and the tiles around it", makeItem=potion("Glowrock", items.GLOW)),

    # ---- Workbench
    Recipe("stone_pick", "Stone Pick", "workbench", 2, {"handle": 1, "stone": 3}, "item",
           "Digs faster than a worn pick.", "Hands  Wall Damage +2", bonus=2, makeItem=gear("WallDamage", "Stone Pick", "Hands")),
    Recipe("club", "Wooden Club", "workbench", 2, {"wood": 4}, "item",
           "Crude, but better than fists.", "Hands  Damage +2", bonus=2, makeItem=gear("Damage", "Wooden Club", "Hands")),
    Recipe("wooden_shield", "Wooden Shield", "workbench", 2, {"wood": 5, "stone": 1}, "item",
           "Blocks a little of every hit.", "Hands  Defense +1", bonus=1, makeItem=gear("Defense", "Wooden Shield", "Hands")),
    Recipe("leather_pouch", "Leather Pouch", "workbench", 2, {"hide": 3}, "upgrade",
           "Stitched to your belt. Carry twice as much of everything.", "Stacks 99 to 199"),
    # A Backpack is a whole row of inventory, whatever its quality (quality only names it, and Masterwork still
    # gets its free enchantment)
    Recipe("backpack", "Backpack", "workbench", 3, {"hide": 6, "wood": 2}, "item",
           "Worn on your back. Another row of inventory; arrow down to reach it.", "Back  Inventory +5",
           makeItem=lambda b, b2: items.equipment("Storage", "Backpack", "Back", BACKPACK_SLOTS)),
    # Like the Backpack, quality only names it: every Potion Belt stacks potions to POTION_BELT_STACK
    Recipe("potion_belt", "Potion Belt", "workbench", 2, {"hide": 4, "bone": 2}, "item",
           f"A leather belt lined with vial loops. Up to {POTION_BELT_STACK} of the same potion share one inventory slot.",
           f"Belt  Potions stack to {POTION_BELT_STACK}",
           makeItem=lambda b, b2: items.equipment("PotionStack", "Potion Belt", "Belt", POTION_BELT_STACK)),
    Recipe("soft_boots", "Soft-Soled Boots", "workbench", 2, {"hide": 4, "wood": 1}, "item",
           "Quiet hide soles. When you slip a blow, it's more likely to miss you entirely.", "Feet  Clean Dodge +10%",
           bonus=10, makeItem=gear("CleanDodge", "Soft-Soled Boots", "Feet", None)),
    Recipe("cooking_pot", "Cooking Pot", "workbench", 3, {"stone": 6, "wood": 3}, "station",
           "A stone pot that sits on a few coals. Cooks meat, alone or with herbs.", "Unlocks the Cooking Pot", makes="cooking_pot"),
    *[Recipe(mealId, name, "cooking_pot", turns, needs, "potion", description, mealResult(heal, buffs),
             makeItem=meal(name, heal, buffs)) for mealId, name, turns, needs, heal, buffs, description in MEALS],
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
    Recipe("charcoal", "Charcoal", "smelter", 1, {"wood": 1}, "material",
           "Wood baked black. Any recipe that needs Coal takes 3 Charcoal in place of each one.", "1 Charcoal",
           makes="charcoal"),
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
    Recipe("ember_amulet", "Ember Ward Amulet", "jeweler", 4, {"silver_ingot": 1, "cut_ruby": 1, "emberroot": 2}, "item",
           "Emberroot ash sealed behind a ruby. Fire slides off you.", "Neck  Fire Resist +3", bonus=3,
           makeItem=gear("FireRes", "Ember Ward Amulet", "Neck", None)),
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

    Recipe("demise_flask", "Demise Flask", "alchemist", 3, {"glass": 1, "organizers_demise": 2}, "potion",
           "Crushed thorns that hum with magic. Organizers caught in it take root.",
           f"Thrown: {DEMISE_FLASK_DAMAGE} magic damage where it lands; Organizers become Plant Organizers",
           makeItem=potion("Demise Flask", "Magic", DEMISE_FLASK_DAMAGE)),

    Recipe("smoke_bomb", "Smoke Bomb", "alchemist", 3, {"glass": 1, "shadowfern": 2, "coal": 1}, "potion",
           "Burning fern and a lot of smoke.", f"Thrown: a smoke cloud for {SMOKE_TURNS} turns", makeItem=potion("Smoke Bomb", "Smoke", SMOKE_TURNS)),

    # ---- Cauldron (has to be set up; stronger brews)
    Recipe("healing", "Healing Potion", "cauldron", 2, {"glass": 1, "bloodcap": 1, "hearthmoss": 1, "coal": 1}, "potion",
           "Simmered slowly over coals.", "Heals 6 (+WIS)", makeItem=potion("Healing Potion", "Heal", 6, "wisdom")),
    Recipe("greater_healing", "Greater Healing Potion", "cauldron", 4, {"glass": 1, "bloodcap": 2, "hearthmoss": 2, "cut_ruby": 1}, "potion",
           "A ruby dissolved into it. It glows.", "Heals 12 (+WIS)", makeItem=potion("Greater Healing Potion", "Heal", 12, "wisdom")),
    Recipe("door_potion_2", "Potion Of Door (x2)", "cauldron", 3, {"glass": 2, "glowcap": 2, "coal": 1}, "potion",
           "Two caps go further in a big pot.", "2 potions that show the way down", amount=2,
           makeItem=potion("Potion Of Door", "DoorLocate")),
    Recipe("fire_flask", "Fire Flask", "cauldron", 3, {"glass": 1, "emberroot": 2, "coal": 1}, "potion",
           "Throw it and everything it splashes burns.", f"Thrown: {FIRE_FLASK_DAMAGE} damage where it lands; sets fires",
           makeItem=potion("Fire Flask", "Fire", FIRE_FLASK_DAMAGE)),
    Recipe("bomb_flask", "Bomb","cauldron", 2,{"hide":1,"emberroot":1,"coal":2}, "potion",
           "Throw it and it explodes.",f"Thrown: {BOMB_FLASK_DAMAGE} damage when it explodes; sets fires, breaks walls",
           makeItem=potion("Bomb","Explosive",BOMB_FLASK_DAMAGE))
]

SCRAP_GOLD, REFORGE_GOLD, REKINDLE_GOLD = 40, 150, 100

# Herbs that go into fire potions and fire gear. Plants of those kinds are used to heat and barely catch fire.
FIRE_RECIPES = ("fire_flask", "ember_amulet")
FIRE_HERBS = {m for r in RECIPES if r.id in FIRE_RECIPES for m in r.needs
              if any(info["herb"] == m for info in plants.PLANTS.values())}



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


# Taking things apart: any item made from a recipe (gear or a potion) can be broken down at the station that
# makes it, for a share of what it cost. Each material's share is rounded up or down at random, so on average
# you get exactly the percent. Intelligence raises the percent.
SALVAGE_BASE = 25        # percent back with 1 Intelligence
SALVAGE_PER_INT = 0.5    # more percent per point of Intelligence above 1
SALVAGE_MOST = 75        # never more than this
RECIPES_BY_ID = {r.id: r for r in RECIPES}

# Found gear (chests, goblin drops, your starting pick) was never crafted, so it has no recipe to take apart by.
# These stand in for one: what it's worth in materials, taken apart at the Workbench for the usual salvage share.
# They're only in RECIPES_BY_ID, so they never show up as something to make.
FOUND_SALVAGE = {  # item name -> (turns, materials it's worth)
    "Worn Pick-Axe": (2, {"scrap": 2, "handle": 1}),
    "Rusty Sword": (2, {"scrap": 4, "handle": 1}),
    "Pick-Axe": (2, {"scrap": 4, "handle": 1}),
    "Simple Shield": (2, {"wood": 5, "scrap": 2}),
    "Sword": (4, {"iron_ingot": 3, "handle": 1}),
    "Steel Pick-Axe": (4, {"iron_ingot": 3, "handle": 1}),
    "Tear Sheild": (4, {"iron_ingot": 3, "wood": 2}),
    "War Pick": (4, {"iron_ingot": 2, "copper_ingot": 1, "handle": 1}),
}
for _name, (_turns, _needs) in FOUND_SALVAGE.items():
    _found = Recipe("found_" + _name.lower().replace(" ", "_").replace("-", "_"), _name, "workbench", _turns, _needs,
                    "found", "Found gear.", "")
    RECIPES_BY_ID[_found.id] = _found


def salvagePercent(intelligence):
    return min(SALVAGE_MOST, SALVAGE_BASE + SALVAGE_PER_INT * max(0, intelligence - 1))


def recipeFor(item):
    """The recipe an item was made from, or None. Found gear uses its FOUND_SALVAGE stand-in. Items made before
    recipes were recorded on them are matched by name."""
    recipe = RECIPES_BY_ID.get(getattr(item, "recipeId", None))
    if recipe is not None:
        return recipe
    if not hasattr(item, "baseName") and item.name in FOUND_SALVAGE:  # (crafted gear always has a baseName)
        return RECIPES_BY_ID["found_" + item.name.lower().replace(" ", "_").replace("-", "_")]
    name = getattr(item, "baseName", item.name)
    return next((r for r in RECIPES if r.kind in ("item", "potion") and r.name == name), None)


def salvageShares(recipe, percent):
    """{material id (or "gold"): average amount back} for taking apart one thing made by this recipe."""
    return {m: n / recipe.amount * percent / 100 for m, n in recipe.needs.items()}


def rollSalvage(recipe, percent):
    back = {}
    for m, share in salvageShares(recipe, percent).items():
        n = int(share) + (1 if random.random() < share % 1 else 0)
        if n:
            back[m] = n
    return back


def salvageRecipes(station, inventory):
    """A Take Apart recipe for each item in your pack that was made at this station."""
    out = []
    for item in inventory:
        if relics.isRelic(item) or getattr(item, "effect", None) == "Meal":  # a meal can't be uncooked
            continue
        made = recipeFor(item)
        if made is None or made.station != station or not made.needs:
            continue
        out.append(Recipe("salvage", f"Take apart {item.name}", station, max(1, made.turns // 2), {}, "salvage",
                          "Breaks it down for some of what went into it. The item is lost.", "Some of its materials",
                          makes=made.id, target=item))
    return out


def relicStationRecipes(station, inventory):
    """The Shrine's and the Forge's recipes, one for each item in your pack they can work on."""
    out = []
    for item in inventory:
        if station == "shrine" and relics.isRelic(item):
            out.append(Recipe("scrap", f"Scrap {item.name}", "shrine", 6, {"gold": SCRAP_GOLD}, "scrap",
                              f"Destroys the relic for its dust. {SCRAP_GOLD} gold of fuel.", "3 Relic Dust, maybe a Void Shard",
                              target=item))
        elif station == "forge" and relics.isRelic(item) and item.relicPower not in relics.BOUND_POWERS:
            out.append(Recipe("rekindle", f"Rekindle {item.name}", "forge", 8, {"relic_dust": 2, "gold": REKINDLE_GOLD}, "rekindle",
                              f"Burns away its relic power for a different one. {REKINDLE_GOLD} gold of fuel.", "A new relic power",
                              target=item))
        elif station == "forge" and getattr(item, "quality", None) == "Masterwork":
            out.append(Recipe("reforge", f"Reforge {item.name}", "forge", 10, {"relic_dust": 3, "void_shard": 2, "gold": REFORGE_GOLD},
                              "reforge", f"Keeps its stats and slot, and adds a random relic power. {REFORGE_GOLD} gold of fuel.",
                              "A relic", target=item))
    return out
