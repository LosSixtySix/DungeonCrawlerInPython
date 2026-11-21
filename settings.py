import json
import pygame
import paths

"""
Player settings that should survive between runs: the hotkeys, where each window was dragged to, the display
(resolution, fullscreen or windowed), the sound (volumes and mute) and the map's zoom.
They are stored as JSON (plain text you can open and read), separate from the pickled save game,
because they belong to the player rather than to one run of the dungeon.
"""

SETTINGS_FILE = paths.savePath("settings.json")

# (action, label shown in the Hotkeys menu, default key). The order here is the order in the menu.
HOTKEY_ACTIONS = [
    ("move_up", "Move Up", pygame.K_w),
    ("move_down", "Move Down", pygame.K_s),
    ("move_left", "Move Left", pygame.K_a),
    ("move_right", "Move Right", pygame.K_d),
    ("interact", "Interact", pygame.K_e),
    ("cycle", "Cycle Windows", pygame.K_TAB),
    ("character", "Character", pygame.K_c),
    ("room", "Room Info", pygame.K_r),
    ("equipment", "Equipment", pygame.K_u),
    ("inventory", "Inventory", pygame.K_i),
    ("level_up", "Level Up", pygame.K_l),
    ("materials", "Pouch", pygame.K_p),
    ("map", "Map", pygame.K_m),
    ("loot_table", "Loot Table", pygame.K_t),
    ("crafting", "Crafting", pygame.K_k),
    ("aim", "Aim (hold)", pygame.K_LCTRL),
    ("rotate", "Rotate (hold)", pygame.K_LALT),
]
DEFAULT_HOTKEYS = {action: key for action, _, key in HOTKEY_ACTIONS}

# Defaults that changed: (action, old default, new default). Saved settings from before HOTKEY_VERSION still on the
# old default get the new one, once; a key you picked yourself is left alone.
HOTKEY_VERSION = 2
MOVED_DEFAULTS = [("materials", pygame.K_m, pygame.K_p)]  # version 2: Pouch moved to P (the Color Picker hotkey is gone)
ACTION_LABELS = {action: label for action, label, _ in HOTKEY_ACTIONS}

# Keys that always do the same thing, so you can never lock yourself out of the menus.
FIXED_KEYS = [("Enter", "Confirm"), ("Esc", "Back / Pause"), ("Arrow Keys", "Move"), ("Mouse", "Drag a window by its title")]
MAP_ZOOMS = [1, 2, 3, 4]  # Ctrl + mouse wheel steps through these (whole numbers keep the pixel art crisp)
VOLUME_STEP = 1  # Left/Right on the Sound page changes a volume by this much (0 to 100); hold the key to keep going
LIGHT_STYLES = ["sway", "flicker"]  # the order the pause menu cycles through them

RESERVED_KEYS = {pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_ESCAPE, pygame.K_UP, pygame.K_DOWN, pygame.K_LEFT, pygame.K_RIGHT,
                 pygame.K_BACKQUOTE}  # ~ opens the developer console


class Settings():
    def __init__(self, fileName=SETTINGS_FILE):
        self.fileName = fileName
        self.hotkeys = dict(DEFAULT_HOTKEYS)
        self.windowPositions = {}  # window id -> [x, y] of its top-left corner, only for windows the player moved
        self.lightStyle = "sway"   # how the light animates: "sway" or "flicker"
        self.resolution = None     # [width, height] of the game, or None to match the desktop
        self.fullscreen = True     # False: a normal window
        self.masterVolume = 80     # 0-100: everything the game plays
        self.musicVolume = 70      # 0-100: the music, on top of the master volume
        self.effectsVolume = 80    # 0-100: sound effects (the bomb going off), on top of the master volume
        self.muted = False
        self.mapZoom = 1           # one of MAP_ZOOMS: how far the map is zoomed in around you
        self.load()

    def load(self):
        try:
            with open(self.fileName, "r") as f:
                data = json.load(f)
        except (FileNotFoundError, ValueError):
            return
        for action, key in data.get("hotkeys", {}).items():
            if action in self.hotkeys and isinstance(key, int):
                self.hotkeys[action] = key
        if data.get("hotkeyVersion", 1) < HOTKEY_VERSION:
            for action, old, new in MOVED_DEFAULTS:
                taken = any(k == new for a, k in self.hotkeys.items() if a != action)
                if self.hotkeys.get(action) == old and not taken:
                    self.hotkeys[action] = new
        for windowId, pos in data.get("windowPositions", {}).items():
            if isinstance(pos, list) and len(pos) == 2:
                self.windowPositions[windowId] = pos
        if data.get("lightStyle") in LIGHT_STYLES:
            self.lightStyle = data["lightStyle"]
        resolution = data.get("resolution")
        if isinstance(resolution, list) and len(resolution) == 2 and all(isinstance(n, int) and n > 0 for n in resolution):
            self.resolution = resolution
        if isinstance(data.get("fullscreen"), bool):
            self.fullscreen = data["fullscreen"]
        for name in ("masterVolume", "musicVolume", "effectsVolume"):
            volume = data.get(name)
            if isinstance(volume, int) and not isinstance(volume, bool):
                setattr(self, name, max(0, min(100, volume)))
        if isinstance(data.get("muted"), bool):
            self.muted = data["muted"]
        if data.get("mapZoom") in MAP_ZOOMS:
            self.mapZoom = data["mapZoom"]

    def save(self):
        with open(self.fileName, "w") as f:
            json.dump({"hotkeys": self.hotkeys, "hotkeyVersion": HOTKEY_VERSION, "windowPositions": self.windowPositions, "lightStyle": self.lightStyle,
                       "resolution": self.resolution, "fullscreen": self.fullscreen, "masterVolume": self.masterVolume,
                       "musicVolume": self.musicVolume, "effectsVolume": self.effectsVolume, "muted": self.muted, "mapZoom": self.mapZoom}, f, indent=2)

    def keyName(self, key):
        name = pygame.key.name(key)
        return name.title() if name else f"Key {key}"

    def nameFor(self, action):
        return self.keyName(self.hotkeys[action])

    def rebind(self, action, key):
        """Binds key to action. If another action already used that key, the two swap keys.
        Returns (worked, message to show the player)."""
        if key in RESERVED_KEYS:
            return False, f"{self.keyName(key)} is a fixed key. Pick another"
        other = next((a for a, k in self.hotkeys.items() if k == key and a != action), None)
        if other is not None:
            self.hotkeys[other] = self.hotkeys[action]
            message = f"Swapped with {ACTION_LABELS[other]}"
        else:
            message = f"{ACTION_LABELS[action]} is now {self.keyName(key)}"
        self.hotkeys[action] = key
        self.save()
        return True, message

    def resetHotkeys(self):
        self.hotkeys = dict(DEFAULT_HOTKEYS)
        self.save()

    def resetWindows(self):
        self.windowPositions = {}
        self.save()
