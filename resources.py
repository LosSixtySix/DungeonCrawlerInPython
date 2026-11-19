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
    "rough_jade": ("Rough Jade", "Ore", (60, 160, 96)),
    "rough_peridot": ("Rough Peridot", "Ore", (172, 210, 56)),
    "rough_rose_quartz": ("Rough Rose Quartz", "Ore", (236, 150, 182)),
    "rough_ruby": ("Rough Ruby", "Ore", (214, 48, 72)),
    "rough_amethyst": ("Rough Amethyst", "Ore", (156, 86, 212)),
    "handle": ("Wooden Handle", "Refined", (168, 116, 74)),
    "copper_ingot": ("Copper Ingot", "Refined", (216, 138, 72)),
    "iron_ingot": ("Iron Ingot", "Refined", (154, 160, 168)),
    "silver_ingot": ("Silver Ingot", "Refined", (232, 236, 240)),
    "glass": ("Glass", "Refined", (168, 216, 224)),
    "cut_jade": ("Cut Jade", "Refined", (96, 196, 128)),
    "cut_peridot": ("Cut Peridot", "Refined", (200, 232, 90)),
    "cut_rose_quartz": ("Cut Rose Quartz", "Refined", (248, 184, 208)),
    "cut_ruby": ("Cut Ruby", "Refined", (238, 80, 100)),
    "cut_amethyst": ("Cut Amethyst", "Refined", (186, 130, 240)),
    "relic_dust": ("Relic Dust", "Refined", (184, 154, 232)),
    "bone": ("Bone", "Drops", (216, 207, 184)),
    "scrap": ("Goblin Scrap", "Drops", (106, 110, 118)),
    "hide": ("Hide", "Drops", (122, 98, 80)),
    "mole_claw": ("Mole Claw", "Drops", (184, 171, 152)),
    "void_shard": ("Void Shard", "Drops", (106, 74, 138)),
    "meat": ("Raw Meat", "Drops", (178, 78, 70)),  # what Expansion goblins take from their kills, as food
    "bloodcap": ("Bloodcap", "Plants", (200, 56, 60)),
    "hearthmoss": ("Hearthmoss", "Plants", (104, 170, 76)),
    "glowcap": ("Glowcap", "Plants", (232, 220, 130)),
    "emberroot": ("Emberroot", "Plants", (232, 128, 50)),
    "bloodcap_spores": ("Bloodcap Spores", "Plants", (170, 110, 110)),
    "hearthmoss_spores": ("Hearthmoss Spores", "Plants", (120, 150, 104)),
    "glowcap_spores": ("Glowcap Spores", "Plants", (196, 190, 140)),
    "emberroot_seed": ("Emberroot Seed", "Plants", (176, 120, 80)),
    "shadowfern": ("Shadowfern", "Plants", (78, 128, 86)),
    "shadowfern_spores": ("Shadowfern Spores", "Plants", (96, 120, 96)),
    "organizers_demise": ("Organizer's Demise", "Plants", (176, 96, 184)),
    "organizers_demise_seed": ("Demise Seeds", "Plants", (140, 96, 146)),
}
GROUPS = ["Raw", "Ore", "Refined", "Plants", "Drops"]


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
