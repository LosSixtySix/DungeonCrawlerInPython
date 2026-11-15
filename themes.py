import random

"""
Color themes for each floor type. When a new floor is generated it gets a random theme from the list
for its floor type (the "proportion" chosen in createRooms). The theme is saved with the level, so a
floor keeps its colors when you come back to it.

Every color is a hex string here; the Theme class turns them into [r, g, b] lists for pygame and works out
the darker "remembered" colors used for tiles that are out of sight.
"""

THEMES = {
    "Mostly Stone": [
        {"name": "Granite Hall",
         "fog": "#0d0d10",
         "panel": "#131317",
         "font": "#d9b26a",
         "boxLine": "#34363d",
         "select": "#f0d08a",
         "player": "#f0e6cf",
         "marker": "#9c2a1c",
         "enemy": "#d9503a",
         "chest": "#a77ad8",
         "doorNext": "#5cb6d6",
         "doorPrev": "#2f6378",
         "aim": "#7a2a1e",
         "floor": {"Stone": "#4b4d54", "Wood": "#574536", "Sand": "#6e6656", "Gold": "#5a4e2a"},
         "wall": {"Stone": "#80838c", "Wood": "#876a4e", "Sand": "#9e937a", "Gold": "#e6bb3c"}},
        {"name": "Basalt Forge",
         "fog": "#100a08",
         "panel": "#170f0c",
         "font": "#ff9a4a",
         "boxLine": "#4a2c20",
         "select": "#ffd08a",
         "player": "#ffe9c2",
         "marker": "#3a1608",
         "enemy": "#ff5a2a",
         "chest": "#c07ae0",
         "doorNext": "#4fd0d8",
         "doorPrev": "#2a6b70",
         "aim": "#8c2a10",
         "floor": {"Stone": "#3a3330", "Wood": "#4c3222", "Sand": "#5f4c39", "Gold": "#5c4218"},
         "wall": {"Stone": "#6a5c55", "Wood": "#7d5232", "Sand": "#8f7556", "Gold": "#ffb52e"}},
        {"name": "Marble Vault",
         "fog": "#121418",
         "panel": "#171a1f",
         "font": "#cfd8e3",
         "boxLine": "#3a414c",
         "select": "#8fc8ff",
         "player": "#3fc6a0",
         "marker": "#121418",
         "enemy": "#e0485a",
         "chest": "#8a74e8",
         "doorNext": "#3f9de0",
         "doorPrev": "#2c5578",
         "aim": "#7a2a3a",
         "floor": {"Stone": "#7d828a", "Wood": "#6b5544", "Sand": "#8f8770", "Gold": "#7a6a3a"},
         "wall": {"Stone": "#c4c9cf", "Wood": "#9c7c62", "Sand": "#c2b796", "Gold": "#f5d26a"}},
    ],
    "Mostly Sand": [
        {"name": "Sunken Dunes",
         "fog": "#140f09",
         "panel": "#1b140c",
         "font": "#f0c27a",
         "boxLine": "#5a4428",
         "select": "#fff0c8",
         "player": "#e8f4ff",
         "marker": "#2a1a0a",
         "enemy": "#c8342a",
         "chest": "#3f8fb0",
         "doorNext": "#2fb8a8",
         "doorPrev": "#22665e",
         "aim": "#7c2a14",
         "floor": {"Stone": "#6a6052", "Wood": "#6e4a2c", "Sand": "#9a7a4e", "Gold": "#8a6a26"},
         "wall": {"Stone": "#9a8e7c", "Wood": "#a26c3e", "Sand": "#d0ad74", "Gold": "#ffcc3a"}},
        {"name": "Red Canyon",
         "fog": "#160a08",
         "panel": "#1e0f0c",
         "font": "#f2b48a",
         "boxLine": "#5a2e20",
         "select": "#ffd0a8",
         "player": "#f2f0e0",
         "marker": "#3a120a",
         "enemy": "#ff4a6a",
         "chest": "#4aa0c8",
         "doorNext": "#5ad0c0",
         "doorPrev": "#2e6a62",
         "aim": "#5a1a10",
         "floor": {"Stone": "#6e5048", "Wood": "#5e3a26", "Sand": "#9a5a3e", "Gold": "#8a6224"},
         "wall": {"Stone": "#a07868", "Wood": "#8c5a3a", "Sand": "#cc8058", "Gold": "#f6c040"}},
        {"name": "Bleached Ruins",
         "fog": "#17140f",
         "panel": "#1c1813",
         "font": "#efe2c4",
         "boxLine": "#4c4334",
         "select": "#ff9c5a",
         "player": "#2fa88a",
         "marker": "#17140f",
         "enemy": "#d0402c",
         "chest": "#5a6ad8",
         "doorNext": "#2a8fc8",
         "doorPrev": "#1f5070",
         "aim": "#8a3020",
         "floor": {"Stone": "#8c867a", "Wood": "#7a5c40", "Sand": "#b8a582", "Gold": "#988030"},
         "wall": {"Stone": "#bdb5a6", "Wood": "#a8825c", "Sand": "#e6d6b0", "Gold": "#ffd858"}},
    ],
    "Mostly Wood": [
        {"name": "Old Mine Shaft",
         "fog": "#110c08",
         "panel": "#18110b",
         "font": "#e8b060",
         "boxLine": "#4a3420",
         "select": "#ffe0a0",
         "player": "#f6e8c8",
         "marker": "#6a1e10",
         "enemy": "#d84a30",
         "chest": "#7ab0d8",
         "doorNext": "#58c8b8",
         "doorPrev": "#2c665e",
         "aim": "#7a2812",
         "floor": {"Stone": "#4e4a46", "Wood": "#5c3e26", "Sand": "#74603e", "Gold": "#6a5420"},
         "wall": {"Stone": "#7c7670", "Wood": "#946238", "Sand": "#a48a5c", "Gold": "#f0be30"}},
        {"name": "Rotwood Hollow",
         "fog": "#0b0e09",
         "panel": "#10140c",
         "font": "#b8c890",
         "boxLine": "#34402a",
         "select": "#e0f0b0",
         "player": "#ecf0d0",
         "marker": "#283020",
         "enemy": "#c8583a",
         "chest": "#9a7ac8",
         "doorNext": "#6ac0b0",
         "doorPrev": "#3a6a60",
         "aim": "#5c2a1a",
         "floor": {"Stone": "#3e4640", "Wood": "#3e3424", "Sand": "#5a5638", "Gold": "#545024"},
         "wall": {"Stone": "#66706a", "Wood": "#6a5634", "Sand": "#858056", "Gold": "#c8c048"}},
        {"name": "Cedar Depths",
         "fog": "#130a08",
         "panel": "#1a0f0c",
         "font": "#f0c8a0",
         "boxLine": "#5a3020",
         "select": "#ffd8b0",
         "player": "#e0f0ff",
         "marker": "#2a1008",
         "enemy": "#e83a4a",
         "chest": "#4a9ac0",
         "doorNext": "#3ac0c8",
         "doorPrev": "#24646a",
         "aim": "#6a1e14",
         "floor": {"Stone": "#6a5c56", "Wood": "#7a3e2a", "Sand": "#8c7050", "Gold": "#8a6828"},
         "wall": {"Stone": "#9c8c84", "Wood": "#b0603e", "Sand": "#bc9a70", "Gold": "#ffc848"}},
    ],
    "All Gold": [
        {"name": "King's Hoard",
         "fog": "#120a16",
         "panel": "#180e1c",
         "font": "#ffd36a",
         "boxLine": "#4a2e50",
         "select": "#ffffff",
         "player": "#e8f8ff",
         "marker": "#120a16",
         "enemy": "#ff3a5a",
         "chest": "#5ad0ff",
         "doorNext": "#4ad8c0",
         "doorPrev": "#2a6a64",
         "aim": "#6a1a30",
         "floor": {"Stone": "#4a4250", "Wood": "#5a3a2a", "Sand": "#7a6640", "Gold": "#6a4e1a"},
         "wall": {"Stone": "#7a7088", "Wood": "#8a5a3a", "Sand": "#aa9060", "Gold": "#f2c230"}},
        {"name": "Tarnished Gilt",
         "fog": "#0c0f0c",
         "panel": "#111511",
         "font": "#c8b878",
         "boxLine": "#34402e",
         "select": "#e8e0a8",
         "player": "#f0ead0",
         "marker": "#1a201a",
         "enemy": "#d05a40",
         "chest": "#5aa8a0",
         "doorNext": "#6ad0c0",
         "doorPrev": "#346a64",
         "aim": "#5a2a1a",
         "floor": {"Stone": "#3e4a44", "Wood": "#4a3a2a", "Sand": "#5e5a40", "Gold": "#4e4a2a"},
         "wall": {"Stone": "#6a7a70", "Wood": "#7a6048", "Sand": "#8a8460", "Gold": "#b4a24a"}},
        {"name": "Molten Vault",
         "fog": "#160806",
         "panel": "#1c0b08",
         "font": "#ffb84a",
         "boxLine": "#5a2410",
         "select": "#fff0b0",
         "player": "#c8f0ff",
         "marker": "#160806",
         "enemy": "#ff2a6a",
         "chest": "#8a6aff",
         "doorNext": "#3ad0ff",
         "doorPrev": "#20607a",
         "aim": "#7a1a08",
         "floor": {"Stone": "#4a3430", "Wood": "#5a2a18", "Sand": "#7a5030", "Gold": "#7a3a10"},
         "wall": {"Stone": "#7a5a50", "Wood": "#8a4a2a", "Sand": "#aa7a4a", "Gold": "#ffcc33"}},
    ],
    "Mixed": [
        {"name": "Patchwork Depths",
         "fog": "#0e0d10",
         "panel": "#141317",
         "font": "#dcc08a",
         "boxLine": "#36343c",
         "select": "#f6d690",
         "player": "#f2ecd8",
         "marker": "#8a2418",
         "enemy": "#e24a3a",
         "chest": "#a27ae0",
         "doorNext": "#4ab8e0",
         "doorPrev": "#2a6280",
         "aim": "#7a2a20",
         "floor": {"Stone": "#4a4c55", "Wood": "#5e3e26", "Sand": "#8a7a52", "Gold": "#5e5020"},
         "wall": {"Stone": "#7e828e", "Wood": "#9a643a", "Sand": "#c4ac78", "Gold": "#eec236"}},
        {"name": "Twilight Strata",
         "fog": "#0a0b12",
         "panel": "#0f1018",
         "font": "#b8c4e8",
         "boxLine": "#2c3048",
         "select": "#c8d8ff",
         "player": "#f0e0a0",
         "marker": "#0a0b12",
         "enemy": "#ff5a70",
         "chest": "#7ad0b0",
         "doorNext": "#6ab0ff",
         "doorPrev": "#344e80",
         "aim": "#5a2a48",
         "floor": {"Stone": "#3a4058", "Wood": "#4a3440", "Sand": "#5e5a50", "Gold": "#5a4a28"},
         "wall": {"Stone": "#646c8c", "Wood": "#7a5668", "Sand": "#8c8676", "Gold": "#e0b448"}},
        {"name": "Earthen Layers",
         "fog": "#100d0a",
         "panel": "#16120e",
         "font": "#d8c4a0",
         "boxLine": "#3e342a",
         "select": "#f0dca8",
         "player": "#a8e070",
         "marker": "#1a140a",
         "enemy": "#d8442c",
         "chest": "#8a6ac0",
         "doorNext": "#50b0c0",
         "doorPrev": "#2c6270",
         "aim": "#6e2a18",
         "floor": {"Stone": "#555048", "Wood": "#5a3c28", "Sand": "#7e6a48", "Gold": "#6a5426"},
         "wall": {"Stone": "#8a8478", "Wood": "#8e6040", "Sand": "#b49a6c", "Gold": "#d8b040"}},
    ],
}


def hexToRGB(h):
    return [int(h[i:i + 2], 16) for i in (1, 3, 5)]


def mix(a, b, amount):
    """Moves color a toward color b. amount=0 gives a, amount=1 gives b."""
    return [round(x + (y - x) * amount) for x, y in zip(a, b)]


def desaturate(c, amount):
    gray = 0.3 * c[0] + 0.59 * c[1] + 0.11 * c[2]
    return [round(x + (gray - x) * amount) for x in c]


def remembered(color, fog):
    """The color a tile is drawn in once it is out of sight: pulled toward the fog and greyed out."""
    return desaturate(mix(color, fog, 0.45), 0.35)


class Theme():
    def __init__(self, floorType, data):
        self.name = data["name"]
        self.floorType = floorType
        fog = hexToRGB(data["fog"])

        # One flat dictionary of [r, g, b] lists. The color picker edits these lists in place.
        self.colors = {}
        for key in ["fog", "panel", "font", "boxLine", "select", "player", "marker", "enemy", "chest", "doorNext", "doorPrev", "aim"]:
            self.colors[key] = hexToRGB(data[key])
        self.colors["memChest"] = remembered(self.colors["chest"], fog)
        # Dimmer text for hints and "OFF" values: the text color pulled toward the panel color.
        self.colors["muted"] = mix(self.colors["font"], self.colors["panel"], 0.45)
        for room in ["Stone", "Wood", "Sand", "Gold"]:
            floor = hexToRGB(data["floor"][room])
            wall = hexToRGB(data["wall"][room])
            self.colors[f"floor{room}"] = floor
            self.colors[f"wall{room}"] = wall
            self.colors[f"memFloor{room}"] = remembered(floor, fog)
            self.colors[f"memWall{room}"] = remembered(wall, fog)


def randomTheme(floorType) -> Theme:
    options = THEMES.get(floorType, THEMES["Mixed"])
    return Theme(floorType, random.choice(options))
