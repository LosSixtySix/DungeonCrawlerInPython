"""
Crafting materials. They live in the player's materials pouch (player.materials), separate from the
10-slot inventory, and stack up to POUCH_LIMIT of each. Gold is not a material: it stays player.gold,
the same gold that pays for leveling up.
"""

POUCH_LIMIT = 99          # how many of each material fit, until the Leather Pouch raises it
BIG_POUCH_LIMIT = 199     # with the Leather Pouch

# id -> (name, group, color). The group decides where it's listed in the Materials window.
MATERIALS = {
    "wood": ("Wood", "Raw", (138, 90, 52)),
    "stone": ("Stone", "Raw", (138, 141, 148)),
    "sand": ("Sand", "Raw", (205, 178, 122)),
    "coal": ("Coal", "Ore", (70, 64, 64)),
    "copper_ore": ("Copper Ore", "Ore", (200, 122, 58)),
    "iron_ore": ("Iron Ore", "Ore", (160, 96, 62)),
    "silver_ore": ("Silver Ore", "Ore", (223, 228, 234)),
    "rough_gem": ("Rough Gem", "Ore", (94, 200, 192)),
    "handle": ("Wooden Handle", "Refined", (168, 116, 74)),
    "copper_ingot": ("Copper Ingot", "Refined", (216, 138, 72)),
    "iron_ingot": ("Iron Ingot", "Refined", (154, 160, 168)),
    "silver_ingot": ("Silver Ingot", "Refined", (232, 236, 240)),
    "glass": ("Glass", "Refined", (168, 216, 224)),
    "cut_gem": ("Cut Gem", "Refined", (122, 224, 216)),
    "relic_dust": ("Relic Dust", "Refined", (184, 154, 232)),
    "bone": ("Bone", "Drops", (216, 207, 184)),
    "scrap": ("Goblin Scrap", "Drops", (106, 110, 118)),
    "hide": ("Hide", "Drops", (122, 98, 80)),
    "mole_claw": ("Mole Claw", "Drops", (184, 171, 152)),
    "void_shard": ("Void Shard", "Drops", (106, 74, 138)),
}
GROUPS = ["Raw", "Ore", "Refined", "Drops"]


def materialName(materialId):
    return "Gold" if materialId == "gold" else MATERIALS[materialId][0]


class MaterialStack():
    """Materials (or gold coins) lying on the floor, e.g. dropped by an enemy. They sit in an item pile with
    normal items; picking one up puts it in the pouch (or adds the gold) instead of the inventory."""

    def __init__(self, materialId, amount):
        self.materialId = materialId
        self.amount = amount
        self.Etype = "Material"

    @property
    def name(self):
        return f"{self.amount} {materialName(self.materialId)}"
