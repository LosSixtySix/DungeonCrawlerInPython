import random

from cruel.inventory import items
from cruel.inventory import recipes
from cruel.inventory import resources
from cruel.world import peddler

"""
The Metropolis's shops. Each merchant (enemies.DwellerMerchant) keeps one kind of shop (SHOP_KINDS) and a stock
rolled from what that kind sells: finished things (gear, potions, meals) and lots of materials. Never relics: only
the Gray Peddler sells those, and never stations.

Trading uses the Peddler's shop window (gameManager's shop section) with the shop's name as its title. A shop only
buys its own kind of thing: items made by the recipes it sells, and the materials it deals in. It pays the
Peddler's quarter for items, but better for its materials: MATERIALS_PER_GOLD instead of his 11.

A hostile merchant doesn't trade (it's fled). A dead merchant's stock stays in its shop, in a city chest where it
stood (leaveStock): taking from it is stealing, if anyone sees.
"""

MATERIALS_PER_GOLD = 6      # a shop buys its own materials at this many for 1 gold
STOCK_SIZE = (6, 9)

# id: name, recipes it sells (and buys back), {material id: how many to a lot} it sells (and buys), and other
# materials it buys but doesn't sell
SHOP_KINDS = {
    "ore": {"name": "Ore Exchange", "recipes": [],
            "materials": {"coal": 5, "copper_ore": 5, "iron_ore": 5, "silver_ore": 3, "copper_ingot": 2, "iron_ingot": 2, "silver_ingot": 2},
            "alsoBuys": ["scrap"]},
    "gems": {"name": "Gem Cutter",
             "recipes": ["silver_amulet", "jade_amulet", "rose_amulet", "sight_amulet", "ember_amulet", "gilded_amulet"],
             "materials": {"rough_jade": 2, "rough_peridot": 2, "rough_rose_quartz": 2, "rough_ruby": 2, "rough_amethyst": 2,
                           "cut_jade": 1, "cut_peridot": 1, "cut_rose_quartz": 1, "cut_ruby": 1, "cut_amethyst": 1},
             "alsoBuys": []},
    "food": {"name": "Grocer", "recipes": [meal[0] for meal in recipes.MEALS],
             "materials": {"bloodcap": 3, "hearthmoss": 3, "glowcap": 3, "emberroot": 3, "shadowfern": 3, "meat": 3, "dew": 2,
                           "bloodcap_spores": 2, "hearthmoss_spores": 2, "glowcap_spores": 2, "emberroot_seed": 2, "shadowfern_spores": 2},
             "alsoBuys": []},
    "weapons": {"name": "Weaponsmith", "recipes": ["club", "iron_sword", "war_pick", "gilded_sword"], "materials": {}, "alsoBuys": []},
    "tools": {"name": "Toolmaker",
              "recipes": ["stone_pick", "copper_pick", "iron_pick", "gilded_pick", "digging_gauntlets", "torch", "backpack", "potion_belt"],
              "materials": {}, "alsoBuys": []},
    "armor": {"name": "Armorer",
              "recipes": ["wooden_shield", "iron_helm", "chainmail", "iron_greaves", "hide_boots", "soft_boots", "warded_chainmail"],
              "materials": {}, "alsoBuys": []},
    "potions": {"name": "Apothecary",
                "recipes": ["minor_healing", "healing", "greater_healing", "door_potion", "fire_flask", "bomb_flask", "smoke_bomb", "demise_flask"],
                "materials": {"glass": 2}, "alsoBuys": []},
    "builder": {"name": "Builder's Yard", "recipes": [],
                "materials": {"wood": 10, "stone": 10, "sand": 10, "handle": 3, "charcoal": 6}, "alsoBuys": []},
}


def shopName(kind):
    return SHOP_KINDS[kind]["name"]


# ---------------------------------------------------------------- stock

def materialLot(materialId, amount):
    """A lot of a material for sale: PRICE_MULTIPLIER times what it's worth, like everything the Peddler sells."""
    price = max(peddler.LEAST_PRICE, round(peddler.PRICE_MULTIPLIER * peddler.materialWorth(materialId) * amount))
    return peddler.Ware("material", price, materialId=materialId, amount=amount)


def rollStock(kind):
    """A shop's stock: STOCK_SIZE things picked from what its kind sells (gear can come up more than once, each
    rolled at its own quality)."""
    kindDetails = SHOP_KINDS[kind]
    choices = [("recipe", recipeId) for recipeId in kindDetails["recipes"]] + [("material", materialId) for materialId in kindDetails["materials"]]
    stock = []
    for what, which in random.choices(choices, k=random.randint(*STOCK_SIZE)):
        if what == "recipe":
            stock.append(peddler.wareFrom(recipes.RECIPES_BY_ID[which]))
        else:
            stock.append(materialLot(which, kindDetails["materials"][which]))
    return stock


# ---------------------------------------------------------------- who trades, and what they buy

def isMerchant(enemy):
    return getattr(enemy, "dweller", False) and getattr(enemy, "role", None) == "merchant"


def isTrader(enemy):
    """Will this one trade with you: the calm Gray Peddler, or a merchant that isn't hostile?"""
    return peddler.isCalm(enemy) or (isMerchant(enemy) and not enemy.hostile)


def traderName(enemy):
    """The shop window's title: "The Gray Peddler", or the shop's name."""
    return shopName(enemy.shopKind) if isMerchant(enemy) else enemy.name


def materialsPerGold(enemy):
    return MATERIALS_PER_GOLD if isMerchant(enemy) else peddler.MATERIALS_PER_GOLD


def buysItem(enemy, item):
    """Will this trader buy item? The Peddler buys anything; a shop only what its own recipes make."""
    if not isMerchant(enemy):
        return True
    recipe = recipes.recipeFor(item)
    return recipe is not None and recipe.id in SHOP_KINDS[enemy.shopKind]["recipes"]


def buysMaterial(enemy, materialId):
    """Will this trader buy this material? The Peddler buys any; a shop only the materials it deals in."""
    if not isMerchant(enemy):
        return True
    kindDetails = SHOP_KINDS[enemy.shopKind]
    return materialId in kindDetails["materials"] or materialId in kindDetails["alsoBuys"]


# ---------------------------------------------------------------- a merchant dies

def leaveStock(game, merchant, position):
    """A merchant died at position: its stock stays in the shop, in a city chest there (taking from it is
    stealing). Lots of materials go in as material stacks."""
    things = []
    for ware in merchant.wares:
        if ware.item is not None:
            things.append(ware.item)
        elif ware.kind == "material":
            things.append(resources.MaterialStack(ware.materialId, ware.amount))
    if things:
        game.grid[position] = [3, game.grid[position][1], items.CityChest(things)]
    merchant.wares = []
