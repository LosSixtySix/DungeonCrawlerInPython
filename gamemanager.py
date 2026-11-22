import pygame
import random as rand
import connectingEmptyRooms as CER
import playerClass as pc
import items
import enemies
import wall
import copy
import math
import os
import paths
import EventDispatcher as ED
import themes
import attempts
import events
import loot
import resources
import recipes
import relics
import plants
import organizers
import expansion
import devconsole
import updater
import sound
import titlefog
from version import VERSION
from settings import Settings, HOTKEY_ACTIONS, FIXED_KEYS, LIGHT_STYLES, VOLUME_STEP, MAP_ZOOMS
from renderer import renderer as rend, SWAY_FPS, FIRE_LIGHT_RADIUS
import pickle

"""
The Grid is a 2D grid that has been flattened into a dictionary of unique points. Position i maps to
x = i % rowLength, y = i // rowLength.

Each entry in the grid is a list [what is there, visibility, (optional object)]
What is there:
0 -> nothing          [0,int]
1 -> player           [1,int]
2 -> wall             [2,int,wall]
3 -> chest/items      [3,int,[item*]]
4 -> next door        [4,int]
5 -> enemy            [5,int,enemy]
6 -> previous door    [6,int]

visibility:
0 -> not visible
1 -> in vision range
2 -> memorized

Hot keys are listed (and can be changed) in the pause menu under Hotkeys; the defaults live in settings.py.
Fixed keys: Enter = confirm, Esc = close focused window / pause menu, arrow keys = move.
Windows (Character, Room, Equipment, Inventory, Level Up, Items Here) open with their hotkey. Several can be
open at once; only the focused one takes arrow keys and Enter. Cycle Windows (Tab) moves focus on release,
and holding it while pressing Move Left / Move Right moves focus that way. Holding it and pressing Move Up hands
control back to the game, leaving every window open. Drag a window by its title bar.
"""

MENU_OPTIONS_FILE = paths.savePath("menuOpts.txt")

# Frame rate cap, and how much the splash messages fade per frame
FPS = 60
# Each message starts at 255 and loses this much every frame: 255 / step / FPS = seconds on screen
FADE_STEPS = {"escapeMessage": 1, "floorLevelMessage": 1.5, "brokenSealMessage": 1.5, "eventMessage": 1.5}
# The title fades in as the exact reverse of the "Escape" message fading out: same speed (about 4 seconds)
TITLE_FADE_STEP = FADE_STEPS["escapeMessage"]
KEY_REPEAT_DELAY = 250     # ms before a held key starts repeating
KEY_REPEAT_INTERVAL = 90   # ms between repeats (about 11 a second)
SAVE_FILE = paths.savePath("savegame.pkl")
POUCH_FULL_MESSAGES = 3  # how many times "pouch full" shows for one material before it goes quiet (see give)
SAVE_VERSION = 2  # 2: the map now fills the whole screen, so saves from the old smaller map can't load

# Windows, in the order Tab cycles through them (after the "map" stop)
WINDOW_ORDER = ["character", "room", "equipment", "inventory", "materials", "crafting", "levelup", "items", "loot"]
WINDOW_TITLES = {"character": "Character", "room": "Room", "equipment": "Equipment", "materials": "Pouch", "loot": "Loot Table",
                 "inventory": "Inventory", "levelup": "Level Up", "items": "Items Here", "crafting": "Crafting"}
WINDOW_HOTKEY = {"character": "character", "room": "room", "equipment": "equipment", "materials": "materials", "loot": "loot_table",
                 "inventory": "inventory", "levelup": "level_up", "items": "interact", "crafting": "crafting"}
LIST_WINDOWS = {"equipment", "inventory", "levelup", "items", "loot", "crafting"}  # windows that take arrows/Enter when focused

PAUSE_ROWS = [("toggle", "Save on Exit"), ("toggle", "Generate Room"), ("toggle", "Mini HUD"),
              ("toggle", "Animated Light"), ("choice", "Light Style"), ("page", "Hotkeys"), ("action", "Reset Windows"), ("action", "Quit to Title"),
              ("action", "Quit to Desktop")]
HOTKEYS_PER_COLUMN = 9
MIN_RESOLUTION = (1024, 720)  # smaller screens don't leave room for the windows
WINDOW_SIZES = [(1280, 720), (1366, 768), (1600, 900), (1920, 1080), (2560, 1440)]  # offered in windowed mode when they fit
POPUP_SECONDS = 1.2  # how long a "+2 Wood" popup takes to rise and fade
POPUP_GAP = 450      # ms between two different popups on the same tile, so they don't draw over each other
INVENTORY_COLUMNS = 5
# Remembered tiles fade: one more than FORGET_DISTANCE tiles from you gets a little darker every turn, and after
# FORGET_TURNS turns it's black again (forgotten: unseen, as if you'd never been there). Seeing it again brings it
# back. Doors aren't forgotten. Close by (within FORGET_DISTANCE), a fading tile holds where it is.
# On top of that, remembered tiles darken with distance from you: (distance / FORGET_DISTANCE) ** FORGET_CURVE,
# so nearby ones look about the same and they're black at FORGET_DISTANCE. Doors darken only to DOOR_SHADE_MOST.
FORGET_DISTANCE = 10
FORGET_TURNS = 50
FORGET_CURVE = 2  # higher keeps nearby remembered tiles bright for longer before the falloff
DOOR_SHADE_MOST = 0.45  # doors are never forgotten: they take the same falloff, but never get darker than this
# Each new floor picks one of these as its chance that any given tile starts as a wall (0.15 open to 0.75 dense)
WALL_DENSITIES = [round(0.15 + 0.05 * step, 2) for step in range(13)]
INVENTORY_ROWS = 2  # rows the Inventory window shows; a Backpack's row is reached by arrowing down (it scrolls)
EQUIP_ACTIONS = 1       # actions to put one item on or take one off (a swap is both); faster with more speed
CRAFT_TURN_MS = 150  # while crafting, one turn passes this often, so you can watch enemies move in
CRAFT_MORE = 5       # Shift+Enter crafts up to this many in a row
# A Glowrock set on the floor lights the tiles around it, fading out to GLOW_RADIUS tiles away. Brightness is 0..1
# (1 is the middle of your own light): GLOW_BRIGHTNESS on the rock's tile, a third less beside it, nothing at the edge. Your
# own light adds on top of it (see renderer.tileLighting).
GLOW_RADIUS = 2.5
GLOW_BRIGHTNESS = 0.5
THROWN_EFFECTS = {"Fire", "Smoke", "Magic","Explosive"}  # potions you aim and throw instead of drinking
THROW_RANGE = 8      # how far (in tiles) a potion can be thrown
FLIGHT_TURNS = [(3, 0), (6, 1), (THROW_RANGE, 2)]  # (up to this distance, turns in the air): close throws land at once
BLAST_RADIUS = {"Fire": 2, "Smoke": 2, "Magic": 2,"Explosive":3}  # a thrown potion reaches tiles within this circle of its landing spot
POCKET_CHANCE = 0.5  # chance an enemy that breaks a wall keeps its materials (you get some back when you kill it)
CARRIED_SHARE = 0.10  # share of an enemy's pocketed materials you get back at 1 Wisdom...
CARRIED_SHARE_PER_WISDOM = 0.005  # ...plus this much for each Wisdom point above 1 (+0.5% each)
SPILLED_SHARE = 0.4  # when you didn't make the kill: share of its pocketed materials that spills on the ground...
KILLER_SHARE = 0.3   # ...and share the enemy that killed it pockets (lost if nothing did, e.g. Demise). The rest is lost
BURN_CHANCE = 0.5    # chance fire damage sets the target burning
BURN_TURNS = 3       # how long burning lasts
BURN_DAMAGE = 1      # fire damage burning deals each turn (Fire Resist takes off it like any fire)
FLOOR_BREAK_CHANCE = 0.25  # a Bomb's chance to break the floor in its whole blast circle (see collapseFloor)
# The Scorched Depths (a side floor): breaking the Seal on an All Gold floor with the Molten Vault theme opens a
# Scorched door somewhere on that floor (the door down stays too). It leads to a Scorched Depths floor with no way
# back up; its door down starts a new track at the next floor number, with no way back up from there either.
SCORCHED = "Scorched Depths"
SCORCHED_DOOR = 12          # grid tile type for the Scorched door
SCORCHED_THEME = "Molten Vault"  # the only All Gold theme whose Seal opens a Scorched door
SCORCHED_WALL_SHARE = 0.18  # share of a Scorched Depths floor that's wall, in blobs so the ground stays open
MOLTEN_FLOOR_DAMAGE = 1     # fire damage each turn you stand on Molten floor
MOLTEN_WALL_DAMAGE = 2      # fire damage when you break a Molten wall
FALL_DAMAGE = 3            # damage you, or anything else, take falling through a hole to the floor below
DEMISE_DAMAGE = 5    # magic damage Organizer's Demise deals each turn to anything (but an Organizer) standing in it
GROUND_FIRE_CHANCE = 0.25  # chance each floor tile a Fire Flask splashes catches fire
GROUND_FIRE_TURNS = 3      # how long burning ground lasts
PLANT_CATCH = 0.6          # chance a plant catches fire (from a flask, or each turn from a burning plant beside it)
FIREPROOF_CATCH = 0.1      # the same for plants used in fire recipes (recipes.FIRE_HERBS): they barely burn
PLANT_FIRE_TURNS = 4       # a burning plant burns this long, then it's gone
EXPLOSION_MS = 450         # how long a landing potion's burst animation plays
ANIM_FPS = 15              # flames and bursts animate at this rate
SPURT_MS = 280             # a blood spurt's specks fly this long
FLECK_MS = 300             # wall flecks fly this long
DOOR_RADIUS = 15           # on the first floor the door down is at most this many tiles from where you start
DOOR_RADIUS_GROWTH = 10    # and each floor deeper it can be this much further, until it can be anywhere
DOOR_SENSE = 1             # you sense the door down (even through walls) this many tiles away...
DOOR_SENSE_WISDOM = 3      # ...plus 1 tile for every this many Wisdom points above 1...
DOOR_SENSE_MOST = 10       # ...up to this many
LOW_HEALTH = 0.3           # at or below this share of max HP, you and enemies bleed onto the floor
DRIP = 0.35                # blood left on a tile you step off while at low health (1 = a full puddle)
POOL = 0.25                # blood added each turn under someone at low health who stays put
SPILL = 0.3                # what a full tile spills into a floor tile next to it
HIT_SPECK = 0.04           # every hit leaves a faint speck on the floor
BLOOD_DRY = 1 / 150       # blood dries away by this much a turn (a full puddle lasts 150 turns)


SEE_THROUGH = (0, 9, expansion.CAMP)  # tile types sight passes over (plants depend on the plant)
_RAYS = {}


def rayOffsets(reach, start=0):
    """The vision rays out to reach: one every 0.1 radians, each a list of (dx, dy) steps from the center, nearest
    first and without repeats. Worked out once per reach (they're the same for every tile)."""
    key = (reach, start)
    if key not in _RAYS:
        rays, t = [], 0
        while t < 2 * math.pi:
            ray = []
            for r in range(start, reach + 1):
                point = (round(r * math.cos(t)), round(r * math.sin(t)))
                if point not in ray:
                    ray.append(point)
            rays.append(ray)
            t += .1
        _RAYS[key] = rays
    return _RAYS[key]


class gameManager():
    def __init__(self):
        pygame.init()

        pygame.display.set_icon(pygame.image.load(paths.resourcePath("icon.png")))  # made by makeIcon.py
        pygame.display.set_caption("CRUEL")
        self.clock = pygame.time.Clock()

        self.settings = Settings()
        self.sound = sound.Sound(self.settings)  # music and sound effects (see sound.py)
        self.titleFog = titlefog.TitleFog()      # the fog rolling across the title screen
        self.painter = None
        self.applyDisplay()

        self.menuOptions = {"Generate Room": True, "Save on Exit": False, "Mini HUD": True, "Animated Light": True}
        self.loadMenuOptions(MENU_OPTIONS_FILE)

        # Holding a key repeats it (after KEY_REPEAT_DELAY ms, every KEY_REPEAT_INTERVAL ms), but only for keys
        # where that makes sense: see isRepeatable. keysHeld tells a repeat apart from a fresh press.
        pygame.key.set_repeat(KEY_REPEAT_DELAY, KEY_REPEAT_INTERVAL)
        self.keysHeld = set()
        self.rebinding = None  # checked for every held key, so it must exist on the title screen too (resetSession sets it again)

        self.EventDispatcher = ED.EventDispatcher()
        self.SubscribeToEvents()

        self.running = True
        self.windowRects = {}
        self.windowDrawOrder = []
        self.drag = None
        self.peaceful = False  # developer console /peaceful: enemies ignore you and never attack
        self.autoPlay = None   # developer console /play: {"ms", "next"} while turns pass on their own
        self.console = devconsole.DevConsole(self)
        self.updater = updater.Updater()  # checks for a newer build in the background
        self.goToTitle()

    # ----------------------------------------------------------------- display

    def desktopSize(self):
        return tuple(pygame.display.get_desktop_sizes()[0])

    def displaySize(self):
        """The resolution from the settings, or the desktop's when none was picked."""
        return tuple(self.settings.resolution) if self.settings.resolution else self.desktopSize()

    def resolutionChoices(self, fullscreen):
        """Resolutions the Display page cycles through, biggest first. Fullscreen can use any mode the monitor
        supports; a window can't be bigger than the desktop."""
        desktop = self.desktopSize()
        modes = pygame.display.list_modes()
        sizes = {tuple(m) for m in modes if m[0] >= MIN_RESOLUTION[0] and m[1] >= MIN_RESOLUTION[1]} if modes != -1 else set()
        sizes.add(desktop)
        if not fullscreen:
            sizes |= {size for size in WINDOW_SIZES if size[0] < desktop[0] and size[1] < desktop[1]}
            sizes = {size for size in sizes if size[0] <= desktop[0] and size[1] <= desktop[1]}
        return sorted(sizes, reverse=True)

    def applyDisplay(self):
        """(Re)opens the game window with the resolution and mode from the settings. The map fills the screen,
        so this also sets the map size. Only done before a run starts (at launch or from the title screen)."""
        size = self.displaySize()
        if self.painter is not None:
            # Already open: SDL won't switch an open fullscreen window to a new resolution, so close the display
            # and open it fresh. That forgets the icon, caption and key repeat, so they're set again.
            pygame.display.quit()
            pygame.display.init()
            pygame.display.set_icon(pygame.image.load(paths.resourcePath("icon.png")))
            pygame.display.set_caption("CRUEL")
            pygame.key.set_repeat(KEY_REPEAT_DELAY, KEY_REPEAT_INTERVAL)
            self.keysHeld.clear()
        if self.settings.fullscreen:
            self.win = pygame.display.set_mode(size, pygame.FULLSCREEN)
        else:
            os.environ["SDL_VIDEO_CENTERED"] = "1"
            self.win = pygame.display.set_mode(size)
        theme = self.painter.theme if self.painter is not None else None
        self.painter: rend = rend(self.win)
        self.tileSize = self.painter.setTileSize(10)
        if theme is not None:
            self.painter.setTheme(theme)
        self.rowLength = self.painter.rowLength
        self.numberOfSpots = self.painter.rowLength * self.painter.columnLength

    # ------------------------------------------------------------------ scenes

    def goToTitle(self, message=""):
        self.scene = "title"
        if self.console.open:
            self.console.toggle()
        self.titleMessage = message
        self.titleSel = 0
        self.titlePage = "main"  # "main", "settings", "display" or "sound": the title stays, only the buttons change
        self.sound.stopGameTheme()
        self.sound.playMenuTheme()  # keeps playing if it already was (e.g. back from the Attempts list)
        self.titleFade = 0  # 0 -> 255: "CRUEL" fades in, then the menu appears. Any key or click skips it.
        self.painter.setTheme(themes.randomTheme(rand.choice(list(themes.THEMES))))
        self.change = True

    def skipTitleFade(self) -> bool:
        """Finishes the title fade-in early. Returns True if it was still fading (so the key/click is used up)."""
        if self.scene == "title" and self.titleFade < 255:
            self.titleFade = 255
            self.change = True
            return True
        return False

    def titleOptions(self):
        if self.titlePage == "settings":
            return ["Display Settings", "Sound Settings", "Main Menu"]
        if self.titlePage == "sound":
            return [f"Master Volume:  {self.settings.masterVolume}%", f"Music Volume:  {self.settings.musicVolume}%",
                    f"Effects Volume:  {self.settings.effectsVolume}%", f"Mute:  {'On' if self.settings.muted else 'Off'}", "Back"]
        if self.titlePage == "display":
            w, h = self.pendingDisplay["resolution"]
            mode = "Fullscreen" if self.pendingDisplay["fullscreen"] else "Windowed"
            return [f"Resolution:  {w} x {h}", f"Mode:  {mode}", "Apply", "Back"]
        options = ["Continue"] if os.path.exists(SAVE_FILE) else []
        options += ["New Game", "Attempts", "Settings"]
        if self.updater.latest:
            options.append(f"Update to v{self.updater.latest}")
        return options + ["Quit"]

    def titleView(self):
        """(heading, hint, note) for the title screen page that's showing."""
        if self.titlePage == "settings":
            return "Settings", "Up/Down  choose      Enter  select      Esc  back", ""
        if self.titlePage == "display":
            note = "A saved run only continues at the resolution it was started in" if os.path.exists(SAVE_FILE) else ""
            return "Display Settings", "Up/Down  choose      Left/Right  change      Enter  select      Esc  back", note
        if self.titlePage == "sound":
            return "Sound Settings", "Up/Down  choose      Left/Right  change      Enter  select      Esc  back", self.sound.problem
        note = f"v{VERSION}  -  update available" if self.updater.latest else f"v{VERSION}"
        return "", "Up/Down  choose      Enter  select", note

    def openTitlePage(self, page, sel=0):
        self.titlePage = page
        self.titleSel = sel
        self.titleMessage = ""
        if page == "display":
            self.pendingDisplay = {"resolution": self.displaySize(), "fullscreen": self.settings.fullscreen}

    def openAttempts(self):
        self.scene = "attempts"
        self.attemptList = attempts.deepestFirst(attempts.load())
        self.attemptScroll = 0
        self.change = True

    def endAttempt(self):
        """Permadeath: record how deep this run got, delete the save, and go back to the title screen."""
        attempts.record(self.deepest, self.player.gold)
        try:
            os.remove(SAVE_FILE)
        except FileNotFoundError:
            pass
        self.goToTitle()

    def newGame(self):
        self.player: pc.PlayerClass = pc.PlayerClass()

        self.level = 0
        self.deepest = 0  # deepest floor reached this run, for the Attempts list
        self.levelGrids = []
        self.doorPositions = []
        self.motherlodes = set()  # floors that rolled a Motherlode (see wall.MOTHERLODE_CHANCE)
        self.forcedOreFloor = None  # developer console /orefloor: (floor type, motherlode) for the next new floor
        self.forcedTheme = None  # developer console /moltenvault: the theme the next floor of that type gets
        if os.environ.get("CRUEL_TEST_MOLTEN_VAULT"):  # testing the Scorched Depths route: floor 1 is a Molten Vault
            self.forceMoltenVault()
        self.camps = {}  # floor -> its Expansion camp state (expansion.camp)
        self.floorEvents = {}  # floor -> its event ({"id", "turnsLeft", "active"}, see events.py), if it has one
        self.fallen = {}  # floor -> [(position, tile)]: what fell into it through a hole, put there when you arrive
        self.memoryFade = {}  # floor -> {tile: turns it has been fading} (see stepForgetting)
        self.scorchedDoors = {}  # floor -> where its Scorched door is (one per Molten Vault floor at most)
        self.trackStarts = set()  # floors with no door back up (the Scorched Depths, and the floor below it)
        self.enemyOccupiedItemSpaces = {}

        playerposx, playerposy = self.painter.getCenterCartesian()
        self.playerPositionFlat = playerposx + (playerposy * self.rowLength)

        self.grid, self.EnemyPositions, self.rooms, self.proportion, self.nodes = self.generateNewLevel(True)
        self.setTheme(self.newFloorTheme())
        self.PlaceNextLevelDoor()

        self.currentLocation = copy.copy(self.grid[self.playerPositionFlat])

        self.goldWallCount = 0
        self.addUnsealed = False

        self.resetSession()
        self.messageBools["escapeMessage"] = True

    def continueGame(self) -> bool:
        if not self.loadGame():
            return False
        self.resetSession()
        self.messageBools["floorLevelMessage"] = True
        return True

    def resetSession(self):
        """State that only matters while the game is running. Reset for a new game and after loading a save."""
        self.scene = "playing"
        self.sound.stopMenuTheme()  # the menu music fades out as the run starts
        self.sound.playGameTheme()  # and the quiet in-game music comes in
        self.enemyMove = False

        self.picker = {"ChangingColor": False, "ColorSelected": False}
        self.pickerIndex = 0
        self.selectedColor = "fog"
        self.colorIndex = 0

        self.swap = None  # an equipment swap waiting for Enter (see startSwap)
        self.inventoryScroll = 0  # the Inventory window's top row (see scrollInventory)
        self.smoke = {}       # thrown Smoke Bomb clouds: {map position: turns left}
        self.throwing = None  # inventory index of the potion being aimed, or None
        self.throwArea = None # tiles the aimed potion would reach where it lands
        self.inFlight = []    # thrown potions still in the air: {"effect", "power", "path", "landing", "turns", "flight"}
        self.fires = {}       # burning tiles (ground or plants): {map position: turns left}
        self.freshFires = set()  # fires lit this turn: they don't hurt anyone standing in them until next turn
        self.explosions = []  # landing bursts still playing: [landing, radius, effect, start ms]
        self.animStep = -1    # which step of the flame/burst animation was last drawn
        self.blood = {}       # blood on the floor: {map position: amount, 0 to 1}
        self.bloodDry = {}
        self.spurts = []      # blood spurts playing: [map position, start ms, seed]
        self.flecks = []      # wall flecks playing: [wall position, start ms, seed, (dx, dy) toward the hitter, colors]
        self.playerBloodSpot = None  # where you were last turn (a drip when you move, a pool when you don't)
        self.currentPosition = "Floor"
        self.currentAimSpot = None
        self.aimLine = None

        self.messageBools = {"escapeMessage": False, "floorLevelMessage": False, "brokenSealMessage": False,
                             "eventMessage": False}
        self.painter.fade = 255

        self.rotate = False
        self.aim = False
        self.roomItems = None

        self.openWindows = []
        self.focus = "map"
        self.windowSel = {windowId: 0 for windowId in WINDOW_ORDER}
        self.cycleHeld = False
        self.cycleUsed = False
        self.drag = None

        self.pausePage = None  # None, "journal" or "hotkeys"
        self.pauseSel = 0
        self.hotkeySel = 0
        self.rebinding = None  # action waiting for a new key
        self.hotkeyMessage = ""

        self.turnCount = 0        # turns passed (the Gilded Amulet heals every 20)
        self.craftTab = 0         # which station tab the Crafting window shows (index into recipes.STATIONS)
        self.crafting = None      # the craft in progress: {"recipe", "times", "done", "turn", "next"}, or None
        self.craftMessage = ""    # the last crafting result, shown at the bottom of the Crafting window

        self.popups = []          # rising "+2 Wood" texts: [text, map position, start time in ms]
        self.lightStep = -1       # which step of the swaying light was last drawn
        self.lightChange = False  # True when the light moved but nothing else changed

        self.change = True
        self.setLookPosition()

    def SubscribeToEvents(self):
        self.EventDispatcher.subscribe(pygame.QUIT, self.onQuit)
        self.EventDispatcher.subscribe(pygame.MOUSEWHEEL, self.onMouseWheel)
        self.EventDispatcher.subscribe(pygame.KEYDOWN, self.onKeyDown)
        self.EventDispatcher.subscribe(pygame.KEYUP, self.onKeyUp)
        self.EventDispatcher.subscribe(pygame.MOUSEBUTTONDOWN, self.onMouseDown)
        self.EventDispatcher.subscribe(pygame.MOUSEMOTION, self.onMouseMotion)
        self.EventDispatcher.subscribe(pygame.MOUSEBUTTONUP, self.onMouseUp)
        self.EventDispatcher.subscribe(pygame.WINDOWFOCUSLOST, self.onFocusLost)
        self.EventDispatcher.subscribe(pygame.TEXTINPUT, self.onTextInput)

    # ------------------------------------------------------------------ keys

    def isAction(self, key, action):
        return key == self.settings.hotkeys[action]

    def direction(self, key):
        """(dx, dy, facing) for a movement key (the bound keys or the arrow keys), otherwise None."""
        if key == pygame.K_LEFT or self.isAction(key, "move_left"):
            return -1, 0, 0
        if key == pygame.K_RIGHT or self.isAction(key, "move_right"):
            return 1, 0, 1
        if key == pygame.K_UP or self.isAction(key, "move_up"):
            return 0, -1, 2
        if key == pygame.K_DOWN or self.isAction(key, "move_down"):
            return 0, 1, 3
        return None

    def isRepeatable(self, key):
        """Keys that keep acting while held: moving (and moving through menus) and Interact (digging/attacking).
        Toggles like Esc, Enter, Tab and the window hotkeys only act once per press."""
        return self.direction(key) is not None or self.isAction(key, "interact")

    def onFocusLost(self, event):
        self.keysHeld.clear()  # we won't get the key-up events while the window is in the background

    def onTextInput(self, event):
        self.console.onTextInput(event)

    def onKeyDown(self, event):
        key = event.key
        repeat = key in self.keysHeld
        self.keysHeld.add(key)
        # ~ opens the developer console; while it's open every key goes to it (held Backspace still repeats)
        if self.scene == "playing" and self.rebinding is None and (self.console.open or key == pygame.K_BACKQUOTE):
            if repeat and key in (pygame.K_BACKQUOTE, pygame.K_ESCAPE, pygame.K_RETURN, pygame.K_KP_ENTER):
                return
            if self.console.open:
                self.console.onKey(event)
            else:
                self.console.toggle()
            return
        if repeat and (self.rebinding is not None or not self.isRepeatable(key)):
            return  # a held key repeating: ignored unless it's one that should repeat
        self.change = True
        if self.scene == "title":
            return self.onTitleKey(key)
        if self.scene == "attempts":
            return self.onAttemptsKey(key)
        if self.rebinding is not None:
            return self.onRebindKey(key)
        if self.pausePage is not None:
            return self.onPauseKey(key)
        if self.crafting is not None:  # busy crafting: Esc stops it, every other key waits
            if key == pygame.K_ESCAPE:
                self.stopCrafting(f"Stopped making {self.crafting['recipe'].name}")
            return
        if getattr(self, "autoPlay", None) is not None:  # watching (/play): Esc stops it, every other key waits
            if key == pygame.K_ESCAPE:
                self.autoPlay = None
                self.console.write("good", "Stopped: your turn again")
            return
        if self.throwing is not None:  # aiming a throw: arrows move the target, Enter throws, Esc puts it away
            return self.onThrowKey(key)

        if key == pygame.K_ESCAPE:
            return self.onEscape()
        if self.isAction(key, "cycle"):
            self.cycleHeld = True
            self.cycleUsed = False
            return
        move = self.direction(key)
        if self.cycleHeld and move is not None and move[1] == 0:
            self.cycleFocus(move[0])
            self.cycleUsed = True
            return
        if self.cycleHeld and move is not None and move[1] == -1:  # Tab + Up: back to the game, windows stay open
            self.focus = "map"
            self.cycleUsed = True
            return
        for windowId in WINDOW_ORDER:
            if windowId != "items" and self.isAction(key, WINDOW_HOTKEY[windowId]):
                return self.onWindowHotkey(windowId)
        if key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            if event.mod & (pygame.KMOD_CTRL | pygame.KMOD_ALT) and self.focus in ("inventory", "equipment")                     and not self.pickerActive():
                return self.dropFocusedItem()
            if self.focus == "crafting" and not self.pickerActive():
                return self.startCrafting(CRAFT_MORE if event.mod & pygame.KMOD_SHIFT else 1)
            return self.onEnter()
        if self.isAction(key, "interact"):
            if not self.pickerActive():
                self.onInteract()
            return
        if move is not None:
            self.onDirectionKey(*move)

    def onKeyUp(self, event):
        self.keysHeld.discard(event.key)
        if self.scene != "playing":
            return
        if self.isAction(event.key, "cycle"):
            if self.cycleHeld and not self.cycleUsed and self.pausePage is None:
                self.cycleFocus(1)
                self.change = True
            self.cycleHeld = False
        if self.isAction(event.key, "aim") and self.throwing is None:
            self.currentAimSpot = None
            self.aimLine = None
            self.change = True

    def onEscape(self):
        if self.pickerActive():
            self.picker = {"ChangingColor": False, "ColorSelected": False}
        elif self.swapActive():
            self.cancelSwap()
        elif self.focus in self.openWindows:
            self.closeWindow(self.focus)
        else:
            self.pausePage = "journal"
            self.pauseSel = 0

    # ----------------------------------------------------------- title screen

    def onTitleKey(self, key):
        if self.skipTitleFade():
            return
        options = self.titleOptions()
        move = self.direction(key)
        if move is not None and move[0] == 0:
            self.titleSel = max(0, min(len(options) - 1, self.titleSel + move[1]))
            return
        if self.titlePage == "settings":
            return self.onSettingsKey(key, options[self.titleSel])
        if self.titlePage == "display":
            return self.onDisplayKey(key, move)
        if self.titlePage == "sound":
            return self.onSoundKey(key, move)
        if key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            choice = options[self.titleSel]
            if choice == "Continue":
                if not self.continueGame():
                    self.titleMessage = self.saveProblem()
                    self.titleSel = 0
            elif choice == "New Game":
                self.newGame()
            elif choice == "Attempts":
                self.openAttempts()
            elif choice == "Settings":
                self.openTitlePage("settings")
            elif choice.startswith("Update to"):
                self.startUpdate()
            else:
                self.onQuit(None)
        elif key == pygame.K_ESCAPE:
            self.onQuit(None)

    def startUpdate(self):
        """Hand over to the installer (see updater.py), which waits for the game to close, then updates and restarts it."""
        problem = self.updater.startUpdate()
        if problem:
            self.titleMessage = problem
        else:
            self.onQuit(None)

    def onSettingsKey(self, key, choice):
        enter = key in (pygame.K_RETURN, pygame.K_KP_ENTER)
        if key == pygame.K_ESCAPE or (enter and choice == "Main Menu"):
            self.openTitlePage("main")
            self.titleSel = self.titleOptions().index("Settings")  # back on the button you came from
        elif enter and choice == "Display Settings":
            self.openTitlePage("display")
        elif enter and choice == "Sound Settings":
            self.openTitlePage("sound")

    def onSoundKey(self, key, move):
        """Rows: Master Volume, Music Volume, Effects Volume, Mute, Back. Left/Right changes a volume (Enter flips Mute), and it's
        heard and saved right away."""
        enter = key in (pygame.K_RETURN, pygame.K_KP_ENTER)
        step = move[0] if move is not None else 0
        if key == pygame.K_ESCAPE or (enter and self.titleSel == 4):
            self.openTitlePage("settings", 1)  # back on the Sound Settings button
            return
        if self.titleSel in (0, 1, 2) and step:
            name = ("masterVolume", "musicVolume", "effectsVolume")[self.titleSel]
            setattr(self.settings, name, max(0, min(100, getattr(self.settings, name) + step * VOLUME_STEP)))
            if self.titleSel == 2:
                self.sound.playExplosion(sample=True)  # so you can hear how loud effects are
        elif self.titleSel == 3 and (step or enter):
            self.settings.muted = not self.settings.muted
        else:
            return
        self.settings.save()
        self.sound.applyVolume()

    def onDisplayKey(self, key, move):
        """Rows: Resolution, Mode, Apply, Back. Left/Right (or Enter) changes a value; nothing happens until Apply."""
        enter = key in (pygame.K_RETURN, pygame.K_KP_ENTER)
        step = move[0] if move is not None else (1 if enter else 0)
        pending = self.pendingDisplay
        if key == pygame.K_ESCAPE or (enter and self.titleSel == 3):
            self.openTitlePage("settings")
        elif self.titleSel == 0 and step:
            choices = self.resolutionChoices(pending["fullscreen"])
            index = choices.index(pending["resolution"]) if pending["resolution"] in choices else 0
            # Right goes up a size, Left goes down (the list is biggest first); it wraps around at either end
            pending["resolution"] = choices[(index - step) % len(choices)]
        elif self.titleSel == 1 and step:
            pending["fullscreen"] = not pending["fullscreen"]
            choices = self.resolutionChoices(pending["fullscreen"])
            if pending["resolution"] not in choices:  # e.g. a size only fullscreen offers: use the closest that fits
                w, h = pending["resolution"]
                pending["resolution"] = min(choices, key=lambda size: abs(size[0] - w) + abs(size[1] - h))
        elif self.titleSel == 2 and enter:
            if pending["resolution"] == self.displaySize() and pending["fullscreen"] == self.settings.fullscreen:
                self.titleMessage = "Nothing to change"
                return
            self.settings.resolution = None if pending["resolution"] == self.desktopSize() else list(pending["resolution"])
            self.settings.fullscreen = pending["fullscreen"]
            self.settings.save()
            self.applyDisplay()
            self.titleMessage = "Display settings applied"

    def saveProblem(self):
        """Why the save didn't load, for the title screen."""
        try:
            with open(SAVE_FILE, "rb") as f:
                data = pickle.load(f)
            size = data.get("screenSize")
            if data.get("version") == SAVE_VERSION and size and tuple(size) != self.displaySize():
                return f"That save was made at {size[0]} x {size[1]}. Switch to it in Settings > Display to continue"
        except Exception:
            pass
        return "That save could not be loaded"

    def onAttemptsKey(self, key):
        move = self.direction(key)
        if move is not None and move[0] == 0:
            lastStart = max(0, len(self.attemptList) - self.painter.attemptRowsThatFit())
            self.attemptScroll = max(0, min(lastStart, self.attemptScroll + move[1]))
        elif key in (pygame.K_ESCAPE, pygame.K_RETURN, pygame.K_KP_ENTER):
            self.scene = "title"

    # ------------------------------------------------------------- pause menu

    def onPauseKey(self, key):
        move = self.direction(key)
        if self.pausePage == "journal":
            if move is not None and move[0] == 0:
                self.pauseSel = max(0, min(len(PAUSE_ROWS) - 1, self.pauseSel + move[1]))
            elif key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                self.onPauseRow(PAUSE_ROWS[self.pauseSel])
            elif key == pygame.K_ESCAPE:
                self.pausePage = None
        else:  # hotkeys page
            last = len(HOTKEY_ACTIONS)  # the extra row after the actions is "Reset to Defaults"
            if move is not None:
                step = move[1] if move[0] == 0 else move[0] * HOTKEYS_PER_COLUMN
                if 0 <= self.hotkeySel + step <= last:
                    self.hotkeySel += step
            elif key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                if self.hotkeySel == last:
                    self.settings.resetHotkeys()
                    self.hotkeyMessage = "Hotkeys reset to the defaults"
                else:
                    self.rebinding = HOTKEY_ACTIONS[self.hotkeySel][0]
                    self.hotkeyMessage = ""
            elif key == pygame.K_ESCAPE:
                self.pausePage = "journal"
                self.hotkeyMessage = ""

    def onPauseRow(self, row):
        kind, label = row
        if kind == "toggle":
            self.menuOptions[label] = not self.menuOptions[label]
        elif label == "Light Style":
            styles = LIGHT_STYLES
            self.settings.lightStyle = styles[(styles.index(self.settings.lightStyle) + 1) % len(styles)]
            self.settings.save()
        elif label == "Hotkeys":
            self.pausePage = "hotkeys"
            self.hotkeySel = 0
        elif label == "Reset Windows":
            self.settings.resetWindows()
            self.painter.autoPlaced = {}  # every window finds its usual spot again
        elif label == "Quit to Title":
            if self.menuOptions["Save on Exit"]:
                self.saveGame()
            self.goToTitle()
        elif label == "Quit to Desktop":
            self.onQuit(None)  # saves the game first when Save on Exit is on

    def onRebindKey(self, key):
        if key == pygame.K_ESCAPE:
            self.rebinding = None
            self.hotkeyMessage = "Cancelled"
            return
        worked, self.hotkeyMessage = self.settings.rebind(self.rebinding, key)
        if worked:
            self.rebinding = None

    # ---------------------------------------------------------------- windows

    def openWindow(self, windowId):
        if windowId == "items" and self.takePileGold():  # the pile was only gold: nothing left to show
            return
        if windowId not in self.openWindows:
            self.openWindows.append(windowId)
            self.openWindows.sort(key=WINDOW_ORDER.index)
            self.openOrder = [w for w in getattr(self, "openOrder", []) if w != windowId] + [windowId]
            self.windowSel[windowId] = 0
        self.focus = windowId

    def closeWindow(self, windowId):
        if windowId not in self.openWindows:
            return
        self.openWindows.remove(windowId)
        if self.focus == windowId:
            self.focus = "map"  # closing a window always hands control back to the game, not another window

    def onWindowHotkey(self, windowId):
        if windowId not in self.openWindows:
            self.openWindow(windowId)
        elif self.focus != windowId:
            self.focus = windowId
        else:
            self.closeWindow(windowId)

    def cycleFocus(self, step):
        stops = ["map"] + self.openWindows
        if len(stops) == 1:
            return
        index = stops.index(self.focus) if self.focus in stops else 0
        self.focus = stops[(index + step) % len(stops)]

    def moveSelection(self, dx, dy):
        windowId = self.focus
        if windowId == "loot":
            self.windowSel["loot"] = max(0, min(len(loot.LOOT_TABS) - 1, self.windowSel["loot"] + dx))
            return
        if windowId == "crafting":
            if dx:
                tab = max(0, min(len(recipes.STATIONS) - 1, self.craftTab + dx))
                if tab != self.craftTab:
                    self.craftTab, self.windowSel["crafting"] = tab, 0
            else:
                last = max(0, len(self.craftRecipes()) - 1)
                self.windowSel["crafting"] = max(0, min(last, self.windowSel["crafting"] + dy))
            return
        if windowId == "inventory":
            index = self.windowSel["inventory"] + dx + dy * INVENTORY_COLUMNS
            if 0 <= index < self.player.inventoryLimit:
                self.windowSel["inventory"] = index
            self.scrollInventory()
            return
        if windowId == "equipment" and self.swapActive():
            keys = list(self.player.equipment.keys())
            slots = self.swap["slots"]
            current = keys[self.windowSel["equipment"]]
            at = slots.index(current) if current in slots else 0
            self.windowSel["equipment"] = keys.index(slots[max(0, min(len(slots) - 1, at + dy))])
            return
        count = {"equipment": len(self.player.equipment), "levelup": len(self.player.attributes),
                 "items": len(self.roomItems) if self.roomItems else 0}[windowId]
        self.windowSel[windowId] = max(0, min(count - 1, self.windowSel[windowId] + dy))

    def onWindowEnter(self, windowId):
        index = self.windowSel[windowId]
        if windowId == "inventory":
            if index < len(self.player.inventory):
                item = self.player.inventory[index]
                if item.Etype == "Consume" and item.effect in THROWN_EFFECTS:
                    self.startThrow(index)
                elif items.isGlowrock(item):
                    self.dropFocusedItem()  # set it down at your feet, where it glows
                elif item.Etype == "Consume":
                    self.useConsumable(index)
                elif self.player.slotsFor(item) and self.player.freeSlotFor(item) is None:
                    self.startSwap(index)
                else:
                    before = len(self.player.inventory)
                    self.player.equipItem(index)
                    if len(self.player.inventory) < before:
                        self.spendActions(EQUIP_ACTIONS)
                        self.fitSelections()
        elif windowId == "equipment":
            slot = list(self.player.equipment.keys())[index]
            if self.swapActive():
                if slot in self.swap["slots"]:
                    old = self.player.equipment[slot]
                    if self.player.sheds(old) and not self.roomToSpill():
                        return
                    self.spill(self.player.swapEquip(self.swap["index"], slot))
                    self.spendActions(2 * EQUIP_ACTIONS)  # taking one off and putting one on
                    self.swap = None
                    self.focus = "inventory" if "inventory" in self.openWindows else "equipment"
                    self.fitSelections()
            elif self.player.equipment[slot] != "None":
                if self.player.sheds(self.player.equipment[slot]) and not self.roomToSpill():
                    return
                problem, spilled = self.player.unEquipItem(slot)
                self.spill(spilled)
                if problem:
                    self.addPopup(problem, self.playerPositionFlat)
                else:
                    self.spendActions(EQUIP_ACTIONS)
                    self.fitSelections()
        elif windowId == "levelup":
            self.player.levelUp(list(self.player.attributes.keys())[index])
        elif windowId == "items":
            self.onPickUpItem()
        elif windowId == "crafting":
            self.startCrafting(1)

    # ---------------------------------------------------------------- dropping
    # Ctrl+Enter (or Alt+Enter) on an item in the Inventory or Equipment window drops it in a pile at your feet
    # (or the nearest tile with room, see placeItems), where it can be picked up again. It's a free action.

    def dropFocusedItem(self):
        player = self.player
        if self.focus == "inventory":
            index = self.windowSel["inventory"]
            if index >= len(player.inventory):
                return
            take = lambda: (player.takeOne(index), [])  # one potion off a stack
        else:
            if self.swapActive():
                return
            slot = list(player.equipment)[self.windowSel["equipment"]]
            if player.equipment[slot] == "None":
                return
            take = lambda: player.takeOff(slot)
        if not any(self.roomFor(self.groundAt(p)) for p in self.spillOrder(self.playerPositionFlat)):
            self.addPopup("No room to drop it", self.playerPositionFlat)
            return
        item, spilled = take()  # dropping a Backpack or Vestigial Hand spills what it held too
        self.fitSelections()
        spot = self.placeItems(self.playerPositionFlat, [item] + spilled)[0]
        if spilled:
            self.addPopup(f"{len(spilled)} spilled", self.playerPositionFlat)
        self.addPopup(f"Dropped {item.name}", spot)
        self.change = True

    # -------------------------------------------------------------- item piles
    # Loose items on the floor are piles (tile type 9, an items.ItemPile), not chests (type 3): you and enemies
    # walk over them, and each holds at most items.PILE_LIMIT. Anything more spills onto the nearest tiles with room.

    def groundAt(self, position):
        """What's lying on a tile, also under you or an enemy: e.g. [0, visibility] or [9, visibility, pile]."""
        if position == self.playerPositionFlat:
            return self.currentLocation
        tile = self.grid[position]
        if tile[0] == 5:
            return self.enemyOccupiedItemSpaces.get(position, [0, tile[1]])
        return tile

    def setGround(self, position, ground):
        """Changes what's lying on a tile (under you or an enemy if one is standing there)."""
        if position == self.playerPositionFlat:
            self.currentLocation = ground
            self.grid[position] = [1, self.grid[position][1]] + ground[2:]
        elif self.grid[position][0] == 5:
            if ground[0] == 0:
                self.enemyOccupiedItemSpaces.pop(position, None)
            else:
                self.enemyOccupiedItemSpaces[position] = ground
        else:
            self.grid[position] = ground

    def goldRoomFor(self, ground):
        """How much more gold fits on this ground: piles keep gold in its own slot, up to items.PILE_GOLD_LIMIT."""
        if ground[0] == 0:
            return items.PILE_GOLD_LIMIT
        if ground[0] == 9:
            return max(0, items.PILE_GOLD_LIMIT - getattr(ground[2], "gold", 0))
        return 0

    def takePileGold(self):
        """Opening Items Here on a pile takes its gold straight to you. True if that emptied the pile."""
        spot = self.itemsSpot()
        if spot is None:
            return False
        ground = self.groundAt(spot)
        if ground[0] != 9 or not getattr(ground[2], "gold", 0):
            return False
        self.give("gold", ground[2].gold, spot)
        ground[2].gold = 0
        if ground[2].items:
            return False
        self.setGround(spot, [0, ground[1]])
        self.roomItems = None
        self.change = True
        return True

    def roomFor(self, ground):
        """How many more items fit on this ground: a full pile's worth on bare floor, nothing on anything else."""
        if ground[0] == 0:
            return items.PILE_LIMIT
        if ground[0] == 9:
            return max(0, items.PILE_LIMIT - len(ground[2].items))
        return 0

    def spillOrder(self, origin):
        """origin, then the tiles around it nearest first, spreading only over open ground (floor, piles, and
        tiles you or an enemy stand on), so spilled items never end up behind a wall."""
        order, seen, ring = [], {origin}, [origin]
        while ring and len(order) < 80:
            order += ring
            nextRing = []
            for position in ring:
                for n in self.neighbors(position):
                    if n not in seen and self.grid[n][0] in (0, 1, 5, 9):
                        seen.add(n)
                        nextRing.append(n)
            rand.shuffle(nextRing)  # so spills scatter instead of always heading the same way
            ring = nextRing
        return order

    def placeItems(self, origin, things, gold=0):
        """Lays things (and gold) on the floor at origin in piles of at most PILE_LIMIT items and PILE_GOLD_LIMIT
        gold; the rest spill onto the nearest tiles with room. Returns the tiles that got something. If nowhere
        nearby has room, the last pile takes the rest rather than lose them (and if there's no room at all,
        nothing is placed)."""
        left = list(things)
        placed = []
        for position in self.spillOrder(origin):
            if not left and not gold:
                break
            ground = self.groundAt(position)
            room = self.roomFor(ground) if left else 0
            goldRoom = min(gold, self.goldRoomFor(ground))
            if not room and not goldRoom:
                continue
            if ground[0] == 0:
                ground = [9, ground[1], items.ItemPile()]
            pile = ground[2]
            pile.items.extend(left[:room])
            left = left[room:]
            pile.gold = getattr(pile, "gold", 0) + goldRoom
            gold -= goldRoom
            self.setGround(position, ground)
            placed.append(position)
        if placed and (left or gold):
            pile = self.groundAt(placed[-1])[2]
            pile.items.extend(left)
            pile.gold += gold
        self.change = True
        return placed

    def roomToSpill(self):
        """True if there's ground nearby to spill things onto (popup if not)."""
        if any(self.roomFor(self.groundAt(p)) for p in self.spillOrder(self.playerPositionFlat)):
            return True
        self.addPopup("No room to spill onto", self.playerPositionFlat)
        return False

    def spill(self, things):
        """Puts what came out of a Backpack's row or a Third Hand (and the Backpack or Hand itself, if the
        inventory had no room for it) on the ground at your feet."""
        if things:
            self.placeItems(self.playerPositionFlat, things)
            self.addPopup(f"{len(things)} spilled" if len(things) > 1 else f"{things[0].name} spilled", self.playerPositionFlat)

    def scrollInventory(self):
        """Scrolls the Inventory window just enough to keep the selected slot in view."""
        rows = max(1, -(-self.player.inventoryLimit // INVENTORY_COLUMNS))
        row = self.windowSel["inventory"] // INVENTORY_COLUMNS
        top = getattr(self, "inventoryScroll", 0)
        top = min(top, row)
        top = max(top, row - INVENTORY_ROWS + 1)
        self.inventoryScroll = max(0, min(top, rows - INVENTORY_ROWS))

    def fitSelections(self):
        """After slots come or go (a Backpack, a Vestigial Hand), keeps the windows' selections on real slots."""
        self.windowSel["inventory"] = min(self.windowSel["inventory"], self.player.inventoryLimit - 1)
        self.windowSel["equipment"] = min(self.windowSel["equipment"], len(self.player.equipment) - 1)
        self.scrollInventory()

    # --------------------------------------------------------- equipment swap
    # Equipping with every fitting slot full opens the Equipment window on that slot; Enter swaps the item in
    # (the old one takes its place in the inventory), Esc cancels. Arrows only move between the slots it fits.

    def spendActions(self, actions):
        """Spends your actions (moving, attacking, equipping...). Each time this turn's actions run out, the
        world takes its turn. More speed (from DEX) now and then gives you an extra action before it does."""
        for _ in range(actions):
            if self.player.spendAction():
                self.enemyTurn()
        self.change = True

    def startSwap(self, inventoryIndex):
        item = self.player.inventory[inventoryIndex]
        slots = self.player.slotsFor(item)
        self.swap = {"index": inventoryIndex, "item": item, "slots": slots}
        self.openWindow("equipment")
        self.windowSel["equipment"] = list(self.player.equipment.keys()).index(slots[0])

    def swapActive(self):
        """True while a swap is waiting. It's dropped if the Equipment window lost focus or the item moved."""
        swap = self.swap
        if swap is None:
            return False
        inventory = self.player.inventory
        if self.focus != "equipment" or swap["index"] >= len(inventory) or inventory[swap["index"]] is not swap["item"]:
            self.swap = None
            return False
        return True

    def cancelSwap(self):
        self.swap = None
        self.focus = "inventory" if "inventory" in self.openWindows else "map"

    # -------------------------------------------------------------- crafting

    def craftStation(self):
        return recipes.STATIONS[self.craftTab]

    def stationOwned(self, station):
        return station == "hand" or station in self.player.stations

    def neighbors(self, i):
        """The up to four tiles beside a tile (no wrapping around the map's edges)."""
        out = []
        for j in (i - 1, i + 1, i - self.rowLength, i + self.rowLength):
            if j in self.grid and (abs(j - i) != 1 or self.sameRow(i, j)):
                out.append(j)
        return out

    def stationState(self, station):
        """"ready", "locked" (not owned), "packed" (needs setting up), "away" (set up on this floor but not next
        to you) or "elsewhere" (set up on another floor)."""
        if not self.stationOwned(station):
            return "locked"
        if recipes.STATION_INFO[station]["setup"] == 0:
            return "ready"
        placed = self.player.stationPlaced.get(station)
        if placed is None:
            return "packed"
        level, position = placed
        if level != self.level:
            return "elsewhere"
        return "ready" if position in self.neighbors(self.playerPositionFlat) else "away"

    def craftRecipes(self):
        """The rows on the open tab: recipes, plus Set up / Pack up for the heavy stations."""
        station = self.craftStation()
        state = self.stationState(station)
        if state == "locked":
            return []
        inventory = self.player.inventory
        rows = recipes.forStation(station) + recipes.relicStationRecipes(station, inventory) +             recipes.salvageRecipes(station, inventory)
        if recipes.STATION_INFO[station]["setup"]:
            if state == "packed":
                rows.insert(0, recipes.setupRecipe(station))
            elif state == "ready":
                rows.append(recipes.packRecipe(station))
        return rows

    def selectedRecipe(self):
        recipeList = self.craftRecipes()
        index = min(self.windowSel["crafting"], len(recipeList) - 1)
        return recipeList[index] if index >= 0 else None

    def freeSpotBesidePlayer(self):
        """Where a station would be set up: the tile you face if it's empty floor, otherwise any empty floor beside you."""
        spots = [self.PlayerLookPosition] + self.neighbors(self.playerPositionFlat)
        for spot in spots:
            if spot in self.grid and self.grid[spot][0] == 0 and spot in self.neighbors(self.playerPositionFlat):
                return spot
        return None

    def craftProblem(self, recipe):
        """Why this recipe can't be made right now, or None if it can."""
        player = self.player
        name = recipes.STATION_INFO[recipe.station]["name"]
        state = self.stationState(recipe.station)
        if recipe.kind == "setup":
            return None if self.freeSpotBesidePlayer() is not None else "no empty floor beside you"
        if state == "locked":
            return f"you don't have a {name}"
        if state == "packed":
            return f"set up the {name} first"
        if state == "away":
            return f"stand next to your {name}"
        if state == "elsewhere":
            return f"your {name} is on floor {player.stationPlaced[recipe.station][0]}"
        if recipe.kind == "pack":
            return None
        if recipe.kind == "station" and recipe.makes in player.stations:
            return "already made"
        if recipe.kind == "upgrade" and player.pouchLimit >= resources.BIG_POUCH_LIMIT:
            return "already made"
        if recipe.target is not None and not any(item is recipe.target for item in player.inventory):
            return "it's not in your pack any more"
        if player.gold < recipe.needs.get("gold", 0):
            return "not enough gold"
        if not player.hasMaterials(recipe.needs):
            return "not enough materials"
        if recipe.kind == "item" and len(player.inventory) >= player.inventoryLimit:
            return "inventory is full"
        if recipe.kind == "plant":
            look = self.PlayerLookPosition
            if look not in self.grid or self.grid[look][0] != 0:
                return "face an empty floor tile"
            floors = plants.PLANTS[recipe.makes]["floors"]
            if plants.floorOf(look, self.rooms) not in floors:
                return f"it only grows on {floors[0]} or {floors[1]} floors"
        if recipe.kind == "potion" and player.roomFor(recipe.makeItem(0, 0)) < recipe.amount:
            return "not enough room in your inventory"
        return None

    def salvagePercent(self):
        return recipes.salvagePercent(self.player.attributes["intelligence"])

    def craftableCount(self, recipe):
        """How many times the pouch (and gold) could pay for this recipe."""
        if not recipe.needs:
            return 1
        return min(self.player.have(m) // n for m, n in recipe.needs.items())

    def startCrafting(self, times):
        recipe = self.selectedRecipe()
        if recipe is None or self.crafting is not None:
            return
        problem = self.craftProblem(recipe)
        if problem:
            self.craftMessage = f"Can't: {problem}"
            return
        if recipe.kind not in ("material", "item", "potion"):
            times = 1
        self.crafting = {"recipe": recipe, "times": times, "done": 0, "turn": 0,
                         "next": pygame.time.get_ticks() + CRAFT_TURN_MS}
        self.craftMessage = ""

    def stopCrafting(self, message):
        self.crafting = None
        self.craftMessage = message
        self.change = True

    def stepAutoPlay(self, now):
        """Developer console /play: one turn passes every autoPlay["ms"] without you doing anything, so you can watch
        the floor play out. Not while the pause menu is open or you're crafting (that has its own turns)."""
        play = getattr(self, "autoPlay", None)
        if play is None or self.pausePage is not None or self.crafting is not None or now < play["next"]:
            return
        play["next"] = now + play["ms"]
        self.enemyTurn()
        self.change = True

    def stepCrafting(self, now):
        """Called every frame: while crafting, one turn passes every CRAFT_TURN_MS (enemies move each turn).
        Getting hurt stops the craft. Materials are only spent when an item finishes."""
        craft = self.crafting
        if craft is None or now < craft["next"]:
            return
        recipe = craft["recipe"]
        craft["next"] = now + CRAFT_TURN_MS
        healthBefore = self.player.getCurrentHealth()
        self.enemyTurn()
        self.change = True
        if self.player.getCurrentHealth() < healthBefore:
            self.stopCrafting(f"You were hit! {recipe.name} wasn't finished")
            return
        craft["turn"] += 1
        if craft["turn"] < recipe.turns:
            return
        problem = self.craftProblem(recipe)  # things can change while you work (a station destroyed, a spot taken)
        if problem:
            self.stopCrafting(f"Can't finish: {problem}")
            return
        self.finishCraft(recipe)
        craft["done"] += 1
        craft["turn"] = 0
        if craft["done"] >= craft["times"]:
            self.crafting = None
            return
        problem = self.craftProblem(recipe)
        if problem:
            self.stopCrafting(f"Made {craft['done']} of {craft['times']}: {problem}")

    def finishCraft(self, recipe):
        player = self.player
        kind = recipe.kind
        if kind == "setup":
            spot = self.freeSpotBesidePlayer()
            self.grid[spot] = [7, 1, recipes.Station(recipe.station)]
            player.stationPlaced[recipe.station] = (self.level, spot)
            message = popup = f"{recipes.STATION_INFO[recipe.station]['name']} set up"
            self.craftMessage = message
            self.addPopup(popup, spot)
            return
        if kind == "pack":
            spot = player.stationPlaced.pop(recipe.station)[1]
            self.grid[spot] = [0, self.grid[spot][1]]
            self.craftMessage = f"{recipes.STATION_INFO[recipe.station]['name']} packed away"
            self.addPopup("Packed", spot)
            return
        player.spendMaterials(recipe.needs)
        if kind == "station":
            player.stations.add(recipe.makes)
            message = f"{recipe.name} made: new tab unlocked"
            if recipes.STATION_INFO[recipe.makes]["setup"]:
                message += ", set it up there"
            popup = recipe.name
        elif kind == "upgrade":
            player.pouchLimit = resources.BIG_POUCH_LIMIT
            message = popup = f"Pouch holds {player.pouchLimit} of each"
        elif kind == "material":
            added = player.addMaterial(recipe.makes, recipe.amount)
            popup = f"+{added} {resources.materialName(recipe.makes)}"
            message = popup if added == recipe.amount else popup + " (pouch full)"
        elif kind == "scrap":
            player.inventory = [item for item in player.inventory if item is not recipe.target]
            player.addMaterial("relic_dust", 3)
            message = popup = "+3 Relic Dust"
            if rand.random() < 0.5:
                player.addMaterial("void_shard", 1)
                message += ", +1 Void Shard"
        elif kind == "salvage":
            player.inventory = [item for item in player.inventory if item is not recipe.target]
            made = recipes.RECIPES_BY_ID[recipe.makes]
            back = recipes.rollSalvage(made, self.salvagePercent())
            for materialId, amount in back.items():
                self.give(materialId, amount, self.playerPositionFlat)
            got = ", ".join(f"{n} {'Gold' if m == 'gold' else resources.materialName(m)}" for m, n in back.items())
            self.craftMessage = f"Took apart {recipe.target.name}: " + (got or "nothing worth keeping")
            return
        elif kind == "plant":
            look = self.PlayerLookPosition
            self.grid[look] = [8, self.grid[look][1], plants.Plant(recipe.makes, planted=True)]
            popup = f"Planted {plants.PLANTS[recipe.makes]['name']}"
            message = popup
            self.craftMessage = message
            self.addPopup(popup, look)
            return
        elif kind == "potion":
            for _ in range(recipe.amount):
                made = recipe.makeItem(0, 0)
                made.recipeId = recipe.id
                player.addItemToInventory(made)
            name = recipe.makeItem(0, 0).name
            popup = name if recipe.amount == 1 else f"{recipe.amount} {name}"
            message = f"{popup} added to your inventory"
        elif kind in ("reforge", "rekindle"):
            relics.givePower(recipe.target, relics.newPower(recipe.target))
            popup = recipe.target.name
            message = f"{recipe.target.name}: {relics.EFFECTS[recipe.target.relicPower][1]}"
        else:
            quality = recipes.rollQuality(player.attributeBonuses["intelligence"])
            item = recipe.build(quality)
            player.addItemToInventory(item)
            popup = item.name
            message = f"{item.name} added to your inventory"
            if item.enchants:
                message += f" ({', '.join(relics.effectName(t) for t in item.enchants)})"
        self.craftMessage = message
        self.addPopup(popup, self.playerPositionFlat)

    def onStationInteract(self, position):
        """Interacting with a station: claim it if it's a found one, then open its tab in the Crafting window."""
        station = self.grid[position][2]
        if not station.claimed:
            station.claimed = True
            self.player.stations.add(station.id)
            self.player.stationPlaced[station.id] = (self.level, position)
            self.addPopup(f"{station.name} claimed", position)
            self.craftMessage = f"The {station.name} is yours. Pack it up to carry it."
        self.craftTab = recipes.STATIONS.index(station.id)
        self.windowSel["crafting"] = 0
        self.openWindow("crafting")

    def destroyStation(self, position):
        """A station ran out of HP: it's gone, leaving a little Goblin Scrap."""
        station = self.grid[position][2]
        self.grid[position] = [0, self.grid[position][1]]
        self.placeItems(position, [resources.MaterialStack("scrap", rand.randint(1, 2))])
        self.player.stations.discard(station.id)
        self.player.stationPlaced.pop(station.id, None)
        self.addPopup(f"{station.name} destroyed!", position)
        self.craftMessage = f"Your {station.name} was destroyed"

    def craftSpec(self, spec):
        """The Crafting window: station tabs, the recipe list, details for the selected recipe and a status line."""
        player = self.player
        station = self.craftStation()
        state = self.stationState(station)
        info = recipes.STATION_INFO[station]
        spec["kind"] = "craft"
        spec["tabs"] = [recipes.TAB_NAMES[s] for s in recipes.STATIONS]
        spec["tabsLocked"] = [not self.stationOwned(s) for s in recipes.STATIONS]
        spec["tab"] = self.craftTab
        recipeList = self.craftRecipes()
        spec["selected"] = min(self.windowSel["crafting"], max(0, len(recipeList) - 1))
        spec["list"] = []
        for recipe in recipeList:
            if recipe.kind in ("setup", "pack", "salvage"):
                spec["list"].append((recipe.name, f"{recipe.turns}t", self.craftProblem(recipe) is None))
            elif (recipe.kind == "station" and recipe.makes in player.stations) or \
                    (recipe.kind == "upgrade" and player.pouchLimit >= resources.BIG_POUCH_LIMIT):
                spec["list"].append((recipe.name, "made", False))
            else:
                count = self.craftableCount(recipe)
                spec["list"].append((recipe.name, f"x{count}" if count else "", count > 0 and state == "ready"))

        def needRows(needs):
            rows = []
            for m, n in needs.items():
                have = player.have(m)
                name = resources.materialName(m)
                if m == "coal" and player.materials.get("charcoal"):  # (have counts the Charcoal too)
                    name += f" (or {resources.CHARCOAL_PER_COAL} Charcoal each)"
                rows.append(("need" if have >= n else "short", name, f"{have} / {n}"))
            return rows

        detail = []
        recipe = self.selectedRecipe()
        if state == "locked":
            detail = [("title", info["name"], "")]
            if info.get("found"):
                detail += [("muted", "Can't be crafted. Find one and interact with it to claim it.", ""),
                           ("label", "FOUND IN", ""), ("body", info["found"], "")]
            else:
                maker = recipes.stationRecipe(station)
                detail += [("muted", "Not made yet. " + maker.description, ""),
                           ("label", "MAKE IT BY HAND" if maker.station == "hand" else f"MAKE IT AT THE {recipes.STATION_INFO[maker.station]['name'].upper()}", "")] + needRows(maker.needs)
        elif recipe is None:
            detail = [("title", info["name"], ""), ("muted", "Nothing to work on. Relics and Masterwork gear in your pack show up here.", "")]
        elif recipe.kind == "salvage":
            percent = self.salvagePercent()
            made = recipes.RECIPES_BY_ID[recipe.makes]
            detail = [("title", recipe.name, ""), ("muted", recipe.description, "")]
            problem = self.craftProblem(recipe)
            if problem:
                detail.append(("warn", problem[0].upper() + problem[1:], ""))
            detail.append(("label", "GIVES BACK", f"about {percent:g}%"))
            for m, share in recipes.salvageShares(made, percent).items():
                low, high = int(share), int(share) + (1 if share % 1 else 0)
                amount = f"x{low}" if low == high else f"x{low}-{high}"
                detail.append(("need", "Gold" if m == "gold" else resources.materialName(m), amount))
            detail.append(("label", "TAKES", f"{recipe.turns} turn" + ("s" if recipe.turns > 1 else "")))
            detail.append(("muted", f"INT {player.attributes['intelligence']}: {percent:g}% back. More Intelligence, more back.", ""))
            detail.append(("hint", "Enter  take apart", ""))
        else:
            detail = [("title", recipe.name, ""), ("muted", recipe.description, "")]
            problem = self.craftProblem(recipe)
            if problem and problem not in ("not enough materials", "not enough gold"):  # those show as red rows below
                detail.append(("warn", problem[0].upper() + problem[1:], ""))
            detail.append(("label", "MAKES", recipe.result))
            if recipe.enchants:
                detail.append(("ench", "Enchanted: " + relics.describe(recipe.enchants), ""))
            turns = f"takes {recipe.turns} turn" + ("s" if recipe.turns > 1 else "")
            if recipe.needs:
                detail.append(("label", "NEEDS", turns))
                detail += needRows(recipe.needs)
                if recipe.needs.get("gold"):
                    detail.append(("muted", f"Your next level-up costs {player.nextLevelGold} gold.", ""))
            else:
                detail.append(("label", "TAKES", turns))
            if recipe.kind == "item":
                odds = recipes.qualityOdds(player.attributeBonuses["intelligence"])
                detail.append(("muted", f"INT {player.attributes['intelligence']}:  " + "  ".join(f"{name} {pct}%" for name, pct in odds), ""))
            if recipe.kind in ("material", "item", "potion"):
                detail.append(("hint", f"Enter  craft      Shift+Enter  up to {CRAFT_MORE}", ""))
            else:
                detail.append(("hint", "Enter  " + {"setup": "set up", "pack": "pack up", "plant": "plant"}.get(recipe.kind, "craft"), ""))
        spec["detail"] = detail

        craft = self.crafting
        spec["progress"] = None
        if craft is not None:
            r = craft["recipe"]
            count = f"  ({craft['done'] + 1} of {craft['times']})" if craft["times"] > 1 else ""
            spec["status"] = f"{r.name}{count}   turn {craft['turn'] + 1} of {r.turns}   Esc stops"
            spec["progress"] = (craft["done"] * r.turns + craft["turn"]) / (craft["times"] * r.turns)
        else:
            spec["status"] = self.craftMessage
        return spec

    # ------------------------------------------------------------- effects

    def faceToward(self, enemy, fromPosition, toPosition):
        """Turns an enemy to face from one tile toward another (it keeps its facing if they're the same tile).
        A big enemy turns from the middle of its body. Facing: 0 left, 1 right, 2 up, 3 down."""
        if fromPosition == toPosition or enemy is None:
            return
        R = self.rowLength
        middle = (getattr(enemy, "size", 1) - 1) / 2 if fromPosition == getattr(enemy, "anchor", None) else 0
        dx = toPosition % R - (fromPosition % R + middle)
        dy = toPosition // R - (fromPosition // R + middle)
        if abs(dx) >= abs(dy):
            enemy.facing = 1 if dx > 0 else 0
        else:
            enemy.facing = 3 if dy > 0 else 2

    def hitPlayer(self, enemy, enemyPosition):
        """An enemy attacks the player."""
        if self.peaceful:  # developer console /peaceful
            return
        self.faceToward(enemy, enemyPosition, self.playerPositionFlat)  # it turns to swing at you
        player = self.player
        if enemy.name in ("Goblin", "Goblin Chieftan") and player.hasEffect("goblin_fear") and rand.random() < 0.3:
            enemy.lastPlayerPosition = None
            self.addPopup("Flees!", enemyPosition)
            return
        dodged = self.dodge(player.evasion(), player.cleanDodge())
        if dodged == "clean":  # missed you entirely: no Ward used up, no thorns
            self.addPopup("Dodged", self.playerPositionFlat)
            return
        if player.hasEffect("ward") and player.wardReady:
            player.wardReady = False
            self.addPopup("Warded", self.playerPositionFlat)
            return
        damage = player.hitDamage(enemy.damage)
        if dodged == "partial":
            damage = math.ceil(damage / 2)
            self.addPopup("Grazed", self.playerPositionFlat)
        player.damageTaken += damage
        self.bleed(self.playerPositionFlat)
        tile = self.grid.get(enemyPosition)
        if player.hasEffect("fed_thorns") and tile and tile[0] == 5 and len(tile) > 2 and tile[2] is enemy:
            self.magicEnemy(enemyPosition, relics.THORN_DAMAGE)  # Demise Stew: the thorns in your blood bite back

    def dodge(self, evasion, cleanDodge):
        """Rolls whether an attack is evaded: None (it hits), "clean" (it misses) or "partial" (half damage).
        Fire, magic, bombs and falling can't be evaded; only melee hits go through this."""
        if rand.random() >= evasion:
            return None
        return "clean" if rand.random() < cleanDodge else "partial"

    def enemyDodge(self, enemy, damage, position):
        """How much of a melee hit on an enemy lands, after its evasion (a Dire Rat has some)."""
        dodged = self.dodge(getattr(enemy, "evasion", 0), getattr(enemy, "cleanDodge", enemies.CLEAN_DODGE_BASE))
        if dodged is None:
            return damage
        if self.grid.get(position, [0, 0])[1] == 1:  # only popups you can see
            self.addPopup("Dodged" if dodged == "clean" else "Grazed", position)
        return 0 if dodged == "clean" else math.ceil(damage / 2)

    def placeRelicChest(self, grid, depth, proportion):
        """Sometimes a floor has a chest with a relic in it."""
        choices = relics.chestRelics(depth, proportion)
        if not choices or rand.random() >= relics.RELIC_CHEST_CHANCE:
            return
        for _ in range(500):
            i = rand.randint(0, self.numberOfSpots - 1)
            if grid[i][0] == 0 and i != self.playerPositionFlat:
                grid[i] = [3, 0, [relics.make(rand.choice(choices))]]
                return

    def placeVault(self, grid, stationId, enemyPositions):
        """A 5x5 vault sealed in gold walls, with a found station in the middle and a relic chest beside it.
        Returns the station's position, or None if no spot was found."""
        R = self.rowLength
        columns = self.numberOfSpots // R
        px, py = self.playerPositionFlat % R, self.playerPositionFlat // R
        for _ in range(300):
            cx, cy = rand.randint(3, R - 4), rand.randint(3, columns - 4)
            if abs(cx - px) + abs(cy - py) < 15:
                continue
            block = [(cx + dx) + (cy + dy) * R for dy in range(-2, 3) for dx in range(-2, 3)]
            if any(grid[b][0] in (1, 3, 4, 5, 6, 7) or b in enemyPositions for b in block):
                continue
            for dy in range(-2, 3):
                for dx in range(-2, 3):
                    b = (cx + dx) + (cy + dy) * R
                    grid[b] = [2, 0, wall.GoldWall()] if abs(dx) == 2 or abs(dy) == 2 else [0, 0]
            center = cx + cy * R
            grid[center] = [7, 0, recipes.Station(stationId, claimed=False)]
            grid[center - 1 - R] = [3, 0, [relics.make(rand.choice(list(relics.RELICS)))]]
            return center
        return None

    # ----------------------------------------------------------------- mouse

    def onMouseDown(self, event):
        if self.skipTitleFade():
            return
        if self.scene != "playing" or self.pausePage is not None or event.button != 1:
            return
        for windowId in reversed(self.windowDrawOrder):  # topmost window first
            rect = self.windowRects.get(windowId)
            if rect is not None and rect.collidepoint(event.pos):
                self.focus = windowId
                self.change = True
                if event.pos[1] < rect.y + self.painter.WINDOW_HEAD:
                    self.drag = (windowId, event.pos[0] - rect.x, event.pos[1] - rect.y)
                return

    def onMouseMotion(self, event):
        if self.drag is None:
            return
        windowId, offsetX, offsetY = self.drag
        rect = self.windowRects[windowId]
        x = max(0, min(self.painter.screenWidth - rect.w, event.pos[0] - offsetX))
        y = max(0, min(self.painter.screenHeight - rect.h, event.pos[1] - offsetY))
        self.settings.windowPositions[windowId] = [x, y]
        self.windowRects[windowId] = pygame.Rect(x, y, rect.w, rect.h)
        self.change = True

    def onMouseUp(self, event):
        if event.button == 1 and self.drag is not None:
            self.drag = None
            self.settings.save()

    def onMouseWheel(self, event):
        if self.scene != "playing":
            return
        if self.console.open:
            self.console.scrollBy(event.y * 3)
            return
        if event.y and pygame.key.get_mods() & pygame.KMOD_CTRL:  # Ctrl + wheel: zoom the map in (up) or out (down)
            return self.zoomMap(1 if event.y > 0 else -1)
        if self.picker["ChangingColor"]:
            keys = list(self.painter.colorDict.keys())
            newIndex = self.pickerIndex - event.y
            if 0 <= newIndex < len(keys):
                self.pickerIndex = newIndex
                self.selectedColor = keys[newIndex]
        elif self.picker["ColorSelected"]:
            color = self.painter.colorDict[self.selectedColor]
            if 0 <= color[self.colorIndex] + event.y <= 255:
                color[self.colorIndex] += event.y
                self.painter.clearTileCaches()  # the theme's colors changed in place: redraw every tile
                self.painter.drawnGrid = None
        self.change = True

    def zoomMap(self, step):
        """One step in or out through settings.MAP_ZOOMS. The camera stays centered on you; the zoom is saved."""
        levels = MAP_ZOOMS
        current = levels.index(self.settings.mapZoom) if self.settings.mapZoom in levels else 0
        zoom = levels[max(0, min(len(levels) - 1, current + step))]
        if zoom != self.settings.mapZoom:
            self.settings.mapZoom = zoom
            self.settings.save()
            self.change = True

    # ------------------------------------------------------------- gameplay

    def pickerActive(self):
        return True in self.picker.values()

    def onEnter(self):
        if self.aim:
            return
        if self.pickerActive():
            if self.picker["ChangingColor"]:
                self.picker = {"ChangingColor": False, "ColorSelected": True}
            return
        if self.focus in LIST_WINDOWS:
            self.onWindowEnter(self.focus)
        elif self.currentLocation[0] == SCORCHED_DOOR:
            self.enterScorched()
        elif self.playerPositionFlat in self.doorPositions:
            self.onOpenDoor()

    def onDirectionKey(self, dx, dy, newDirection):
        if self.enemyMove:
            return
        if self.picker["ColorSelected"]:
            self.colorIndex = max(0, min(2, self.colorIndex + dx))
        if self.aim:
            start = self.playerPositionFlat if self.currentAimSpot is None else self.currentAimSpot
            if dx and not self.sameRow(start, start + dx):
                return  # the map's left/right edge: the aim stops there
            self.currentAimSpot = start + dx + (dy * self.rowLength)
            self.aimLine = self.createARay(self.playerPositionFlat, self.currentAimSpot)
        elif self.rotate:
            self.player.playerDirection = newDirection
        elif self.pickerActive():
            return
        elif self.focus in LIST_WINDOWS:
            self.moveSelection(dx, dy)
        else:
            self.player.playerDirection = newDirection
            if dx and not self.sameRow(self.playerPositionFlat, self.playerPositionFlat + dx):
                return  # the map's left/right edge is solid: no wrapping onto the next row
            self.movePlayer(self.playerPositionFlat + dx + (dy * self.rowLength))

    def movePlayer(self, newPosition):
        targetLocation = self.grid[newPosition][0] if newPosition in self.grid else None
        if targetLocation == 8 and self.grid[newPosition][2].walkable:
            hidden = self.playerHidden()
            self.grid[self.playerPositionFlat] = copy.copy(self.currentLocation)
            self.currentLocation = copy.copy(self.grid[newPosition])
            self.playerPositionFlat = newPosition
            self.enemyMove = True
            if self.playerHidden() and not hidden:
                self.addPopup("Hidden", newPosition)
            return
        if targetLocation not in (7, 8, expansion.CAMP) and self.player.checkValidMoveLocation(targetLocation):  # stations, other plants and camp pieces block
            self.grid[self.playerPositionFlat] = copy.copy(self.currentLocation)
            self.currentLocation = copy.copy(self.grid[newPosition])
            self.playerPositionFlat = newPosition
            self.enemyMove = True

    def onInteract(self):
        target = self.PlayerLookPosition
        if target not in self.grid:
            return
        tile = self.grid[target]
        if tile[0] == 2:  # wall
            self.sound.playHit()
            self.chip(target, self.playerPositionFlat)
            dig = not (self.player.burrow and tile[2].soft)
            if dig:
                hits = 2 if self.player.hasEffect("half_swings") else 1  # Mole-King's Claws: half the swings
                for _ in range(hits):
                    if tile[2].hp > 0:
                        tile[2].takeDamage(self.player.getWallDamage(), self.tileSize)
                if tile[2].hp <= 0:
                    self.breakWall(target)
            else:  # burrow into a soft wall
                currentWall = copy.copy(tile)
                currentWall[2].hp -= 1
                if currentWall[2].hp <= 0:
                    self.breakWall(target)
                else:
                    self.grid[self.playerPositionFlat] = copy.copy(self.currentLocation)
                    self.currentLocation = currentWall
                    self.playerPositionFlat = target
        elif tile[0] == 5:  # enemy
            dealt = self.enemyDodge(tile[2], self.player.DealDamage(), target)
            tile[2].hp -= dealt
            if dealt > 0:
                self.bleed(target)
                self.thirst()
            if tile[2].hp <= 0:
                self.killEnemy(target)
            elif dealt > 0 and self.player.hasEffect("molten"):  # the Molten Blade
                self.fireEnemy(target, relics.MOLTEN_FIRE, igniteChance=relics.MOLTEN_IGNITE_CHANCE)
        elif tile[0] in (3, 9):  # a chest or an item pile
            if self.roomItems is not None:
                self.openWindow("items")
        elif tile[0] == 7:  # a crafting station
            self.onStationInteract(target)
        elif tile[0] == expansion.CAMP:  # a spawner or bonfire: smash it / put it out
            expansion.hitStructure(self, target)
        elif tile[0] == 8:  # a plant: harvest it
            self.harvestPlant(target)
        self.enemyMove = True

    # ------------------------------------------------------------------ loot

    def breakWall(self, position):
        """A wall was broken: it becomes floor and its materials go straight into the pouch."""
        organizers.wallBroken(self, position, "player")  # if an Organizer built it, it may come after you
        tile = self.grid[position]
        name = tile[2].name
        if name == "Gold Wall" and self.proportion == "All Gold":
            self.goldWallCount += 1
            if self.goldWallCount >= 10 and not self.addUnsealed:
                self.messageBools["brokenSealMessage"] = True
                self.painter.fade = 255
                self.addUnsealed = True
                self.openScorchedDoor()
        if name == "Molten Wall" and not self.player.fireImmune():
            self.firePlayer(MOLTEN_WALL_DAMAGE)
        broken = tile.pop()
        tile[0] = expansion.HOLE if getattr(broken, "holeBelow", False) else 0  # (the floor under it was broken)
        player = self.player
        drops = loot.rollWall(name, player.attributes["wisdom"])
        if isinstance(broken, wall.OreVein) and position in self.rooms["Gold"]:  # a vein in a gold wall: gold too
            drops += loot.rollWall("Gold Wall", player.attributes["wisdom"])
        if isinstance(broken, wall.OreVein):  # Iron Pick (+1 ore) and Keen Eye (1 in 4 for +1)
            extra = player.countEffect("extra_ore") + sum(1 for _ in range(player.countEffect("keen_eye")) if rand.random() < 0.25)
            drops = [(m, n + extra if m == broken.ore else n) for m, n in drops]
        if player.hasEffect("gold_double"):
            drops = [(m, n * 2 if m == "gold" else n) for m, n in drops]
        kind = getattr(broken, "corruptedBy", None)
        if kind:  # a wall a plant had corrupted (Overgrowth): its herb too
            drops = drops + [(plants.PLANTS[kind]["herb"], 1)]
        self.collectDrops(drops, name, position)

    def harvestPlant(self, position):
        """A plant was picked: what its stage gives (its herb, or seeds) goes straight into the pouch."""
        plant = self.grid[position][2]
        name = plant.name
        if plant.kind == organizers.DEMISE and not self.player.hasEffect("demise_ward"):
            self.magicPlayer(DEMISE_DAMAGE)  # its thorns: bare-handed, it hurts you and stays where it is
            return
        stage = plant.pick()  # picking uses it up; what it gives depends on its stage (plants.Plant)
        self.grid[position] = [0, self.grid[position][1]]
        self.change = True
        if stage is None:
            self.addPopup("Not ripe", position)  # (pulled up as a sprout or growing: nothing)
            return
        self.collectDrops(loot.rollPick(plant, stage), loot.plantSource(plant, stage), position)

    def killEnemy(self, position, killer="player"):
        """An enemy died. killer is "player", the enemy that killed it, or None (the environment, e.g.
        Demise). If you killed it, it pays all its gold (including gold it took from Gold Walls), rolls its loot
        table, and gives back some of the materials it pocketed from walls (more with Wisdom, see carriedShare);
        relics, and whatever doesn't fit in a full pouch, are left in a pile. Otherwise you get no loot: some of
        its gold and of what it pocketed spills on the ground, some goes to the enemy that killed it, and the
        rest is lost (see spillPockets)."""
        if self.isBig(self.grid[position][2]):  # a giant: clear its other tiles, then it dies at its anchor
            giant = self.grid[position][2]
            position = giant.anchor
            for p in self.footprint(position, giant.size)[1:]:
                self.grid[p] = [0, self.grid[p][1]]
        tile = self.grid[position]
        enemy = tile.pop()
        self.EnemyPositions.discard(position)
        if killer == "player":
            stacks, gold = self.killLoot(enemy, position), 0
        else:
            stacks, gold = self.spillPockets(enemy, killer)
        stacks = list(stacks) + list(getattr(enemy, "loot", []))  # items it picked up (Expansion goblins) drop too
        underneath = self.enemyOccupiedItemSpaces.pop(position, None)  # what it was standing on, if anything
        if underneath is not None and (underneath[0] != 2 or not (stacks or gold)):  # a pile, chest or plant stays
            underneath[1] = tile[1]                          # (so does the wall round a burrower that left nothing)
            self.grid[position] = underneath
        else:  # (a burrower inside a wall that left something: the wall crumbles so it can be picked up)
            self.grid[position] = [0, tile[1]]
        if stacks or gold:
            self.placeItems(position, stacks, gold)

    def carriedShare(self):
        """The share of an enemy's pocketed materials you get back when you kill it."""
        wisdom = self.player.attributes["wisdom"]
        return min(1.0, CARRIED_SHARE + CARRIED_SHARE_PER_WISDOM * max(0, wisdom - 1))

    def killLoot(self, enemy, position):
        """Your reward for a kill: gold, its loot roll and your share of what it carried go straight to you, with
        a popup each. Returns what's left for the floor: relics, and whatever doesn't fit in a full pouch."""
        player = self.player
        gold = enemy.gold + 3 * player.countEffect("gold_per_kill") + player.countEffect("lucky")
        if gold:
            self.give("gold", gold, position)
        drops = loot.roll(loot.ENEMY_LOOT, enemy.name)
        player.lootFound.add(loot.discoveryKey(enemy.name))
        stacks = []
        for dropId, amount in drops:
            player.lootFound.add(loot.discoveryKey(enemy.name, dropId))
            if loot.isRelicDrop(dropId):
                relic = relics.make(dropId[6:])
                stacks.append(relic)
                self.addPopup(f"{relic.name} dropped!", position)
            else:
                left = amount - self.give(dropId, amount, position)
                if left:
                    stacks.append(resources.MaterialStack(dropId, left))
        share = self.carriedShare()
        for materialId, amount in getattr(enemy, "materials", {}).items():
            back = int(amount * share + rand.random())  # rounded up or down at random, so small amounts still pay
            left = back - self.give(materialId, back, position) if back else 0
            if left:
                stacks.append(resources.MaterialStack(materialId, left))
        return stacks

    @staticmethod
    def splitSpoils(amount):
        """(spilled, taken) out of amount: each one is rolled on its own (SPILLED_SHARE spills, KILLER_SHARE goes
        to the killer, the rest is lost), so even a single ore or coin can go any of the three ways."""
        spilled = taken = 0
        for _ in range(amount):
            roll = rand.random()
            if roll < SPILLED_SHARE:
                spilled += 1
            elif roll < SPILLED_SHARE + KILLER_SHARE:
                taken += 1
        return spilled, taken

    def spillPockets(self, enemy, killer):
        """Someone other than you killed enemy. Its gold and each material it pocketed are split (splitSpoils): the
        spilled part is returned for the ground as (stacks, gold), the killer's part goes into killer's pockets
        (lost if killer is None, the environment), the rest is lost."""
        stacks = []
        gold, taken = self.splitSpoils(enemy.gold)
        if taken and killer is not None:
            killer.gold += taken
        for materialId, amount in getattr(enemy, "materials", {}).items():
            spilled, taken = self.splitSpoils(amount)
            if materialId == "gold":
                gold += spilled
            elif spilled:
                stacks.append(resources.MaterialStack(materialId, spilled))
            if taken and killer is not None:
                self.pocket(killer, materialId, taken)
        return stacks, gold

    def pocket(self, enemy, materialId, amount):
        """Puts materials in an enemy's pockets; gold goes with its own gold (all of it is yours if you kill it)."""
        if materialId == "gold":
            enemy.gold += amount
            return
        if not hasattr(enemy, "materials"):  # enemies from saves made before they could carry anything
            enemy.materials = {}
        enemy.materials[materialId] = enemy.materials.get(materialId, 0) + amount

    def enemyBrokeWall(self, position, enemy):
        """An enemy broke a wall: it's floor now. The enemy always keeps any gold in it, and with POCKET_CHANCE
        the wall's other materials too."""
        organizers.wallBroken(self, position, enemy)
        broken = self.grid[position].pop()
        self.grid[position][0] = expansion.HOLE if getattr(broken, "holeBelow", False) else 0
        drops = loot.rollWall(broken.name, 1)
        if isinstance(broken, wall.OreVein) and position in self.rooms["Gold"]:
            drops += loot.rollWall("Gold Wall", 1)
        keep = rand.random() < POCKET_CHANCE or getattr(enemy, "faction", None) is not None  # Expansion squads keep it all to stash
        for materialId, amount in drops:
            if materialId == "gold" or keep:
                self.pocket(enemy, materialId, amount)

    def collectDrops(self, drops, source, position, alreadyFound=False):
        """Gives drops straight to the player (gold to gold, materials to the pouch) with a popup for each."""
        if not alreadyFound:
            self.player.lootFound.add(loot.discoveryKey(source))
        for materialId, amount in drops:
            if not alreadyFound:
                self.player.lootFound.add(loot.discoveryKey(source, materialId))
            self.give(materialId, amount, position)

    def give(self, materialId, amount, position):
        """Gold or a material into the player's hands. Returns how many were taken (the pouch can be full)."""
        if materialId == "gold":
            self.player.alterGold(amount)
            self.addPopup(f"+{amount} Gold", position)
            return amount
        player = self.player
        if not hasattr(player, "pouchFullShown"):  # players from saves made before this was counted
            player.pouchFullShown = {}
        if player.materials.get(materialId, 0) < player.pouchLimit:
            player.pouchFullShown.pop(materialId, None)  # below the max again: the message can show again
        added = player.addMaterial(materialId, amount)
        name = resources.materialName(materialId)
        # "pouch full" shows at most POUCH_FULL_MESSAGES times for each material until it drops below the max
        shown = player.pouchFullShown.get(materialId, 0)
        full = added < amount and shown < POUCH_FULL_MESSAGES
        if full:
            player.pouchFullShown[materialId] = shown + 1
        if added == amount:
            self.addPopup(f"+{added} {name}", position)
        elif added:
            self.addPopup(f"+{added} {name}" + (" (pouch full)" if full else ""), position)
        elif full:
            self.addPopup(f"{name} pouch full", position)
        return added

    def addPopup(self, text, position):
        now = pygame.time.get_ticks()
        for popup in self.popups:
            if popup[0] == text and popup[1] == position:  # the same message again: restart it instead of stacking
                popup[2] = now
                self.change = True
                return
        # A different message on the same tile waits until the last one has risen out of the way (POPUP_GAP)
        latest = max((p[2] for p in self.popups if p[1] == position), default=now - POPUP_GAP)
        self.popups.append([text, position, max(now, latest + POPUP_GAP)])
        self.change = True

    def onColorPickerKey(self):
        if self.picker["ChangingColor"]:
            self.picker["ChangingColor"] = False
        elif self.picker["ColorSelected"]:
            self.picker["ColorSelected"] = False
        else:
            self.picker["ChangingColor"] = True
            self.pickerIndex = list(self.painter.colorDict.keys()).index(self.selectedColor)

    def onPickUpItem(self):
        if self.roomItems is None:
            self.closeWindow("items")
            return
        self.pickUpItem()
        self.windowSel["items"] = 0
        if len(self.roomItems) == 0:
            spot = self.itemsSpot()
            ground = self.groundAt(spot)
            if not (len(ground) > 2 and isinstance(ground[2], expansion.CampChest)):  # a goblin chest stays, empty
                self.setGround(spot, [0, ground[1]])
            self.roomItems = None
            self.closeWindow("items")

    def onOpenDoor(self):
        if self.playerPositionFlat == self.doorPositions[self.level]:
            if self.proportion == SCORCHED:
                self.leaveScorched()
            elif self.level < len(self.doorPositions) - 1:
                self.changeLevel(self.level + 1)
            else:
                self.goToNewLevel()
        elif self.level > 0 and self.level not in self.trackStarts and self.playerPositionFlat == self.doorPositions[self.level - 1]:
            self.changeLevel(self.level - 1)

    def onQuit(self, event):
        self.saveMenuOptions(MENU_OPTIONS_FILE)
        self.settings.save()
        if self.scene == "playing" and self.menuOptions["Save on Exit"]:
            self.saveGame()
        self.running = False

    # ---------------------------------------------------------------- levels

    def setTheme(self, theme):
        self.theme = theme
        self.painter.setTheme(theme)

    def saveLevel(self):
        # Put back whatever the player is standing on so the saved grid has no player tile in it.
        self.grid[self.playerPositionFlat] = copy.copy(self.currentLocation)
        data = [self.grid, self.rooms, self.proportion, self.EnemyPositions, self.enemyOccupiedItemSpaces, self.theme,self.blood,self.bloodDry]
        if self.level < len(self.levelGrids):
            self.levelGrids[self.level] = data
        else:
            self.levelGrids.append(data)

    def LoadLevel(self, level):
        data = self.levelGrids[level]
        self.grid, self.rooms, self.proportion, self.EnemyPositions, self.enemyOccupiedItemSpaces, theme = data[:6]
        self.blood =data[6] if len(data) > 6 else {}
        self.bloodDry = data[7] if len(data) >7 else {}
        self.setTheme(theme)

    def changeLevel(self, newLevel, falling=False):
        self.saveLevel()
        self.level = newLevel
        self.deepest = max(self.deepest, self.level)
        self.LoadLevel(newLevel)
        if falling:  # you land where you fell, or on the nearest open floor to it
            self.playerPositionFlat = self.openSpot(self.playerPositionFlat) or self.playerPositionFlat
        self.currentLocation = copy.copy(self.grid[self.playerPositionFlat])
        self.afterLevelChange()

    # ------------------------------------------------------ the Scorched Depths

    def forceMoltenVault(self):
        """The next new floor is All Gold with the Molten Vault theme (for testing the Scorched Depths route)."""
        self.forcedOreFloor = ("All Gold", False)
        self.forcedTheme = SCORCHED_THEME

    def newFloorTheme(self):
        """A theme for the floor just made: the forced one if it's waiting for this floor type, else random."""
        if self.forcedTheme:
            for data in themes.THEMES.get(self.proportion, []):
                if data["name"] == self.forcedTheme:
                    self.forcedTheme = None
                    return themes.Theme(self.proportion, data)
        return themes.randomTheme(self.proportion)

    def openScorchedDoor(self):
        """The Seal broke: on a Molten Vault floor a Scorched door opens on a random open tile (once per floor)."""
        if self.proportion != "All Gold" or self.theme.name != SCORCHED_THEME or self.level in self.scorchedDoors:
            return
        spots = [i for i, tile in self.grid.items() if tile[0] == 0 and i != self.playerPositionFlat]
        if not spots:
            return
        spot = rand.choice(spots)
        self.grid[spot] = [SCORCHED_DOOR, self.grid[spot][1]]
        self.scorchedDoors[self.level] = spot
        self.addPopup("Somewhere, rock melts", self.playerPositionFlat)

    def dropFloorsBelow(self, last):
        """Every floor deeper than last is gone for good: its saved grid, its doors, and what's kept per floor."""
        del self.levelGrids[last + 1:]
        del self.doorPositions[last + 1:]
        for store in (self.floorEvents, self.camps, self.memoryFade, self.scorchedDoors, self.fallen):
            for floor in [f for f in store if f > last]:
                del store[floor]
        self.motherlodes = {f for f in self.motherlodes if f <= last}
        self.trackStarts = {f for f in self.trackStarts if f <= last}
        for station, (floor, _) in list(self.player.stationPlaced.items()):
            if floor > last:  # set up on a floor that's gone: it's packed again
                del self.player.stationPlaced[station]

    def enterScorched(self):
        """Through the Scorched door: a new Scorched Depths floor one deeper, with no door back up. Any floors you
        had already been to below this one are gone (this starts a new track)."""
        last = self.level
        self.saveLevel()
        self.dropFloorsBelow(last)
        self.blood = {}
        self.bloodDry = {}
        self.grid, self.EnemyPositions, self.rooms, self.proportion, self.nodes = self.generateScorchedLevel(last + 1)
        self.setTheme(themes.randomTheme(SCORCHED))
        self.enemyOccupiedItemSpaces = {}
        self.level = last + 1
        self.deepest = max(self.deepest, self.level)
        self.trackStarts.add(self.level)
        self.PlaceNextLevelDoor()
        self.currentLocation = copy.copy(self.grid[self.playerPositionFlat])
        self.afterLevelChange()

    def leaveScorched(self, falling=False):
        """Down from the Scorched Depths (by its door or through a hole): the Scorched Depths floor is gone and a
        normal floor takes its number, with no door back up. The normal track goes on from there."""
        floor = self.level
        landing = self.fallen.pop(floor, [])  # what fell from the Scorched Depths lands on the new floor
        self.dropFloorsBelow(floor - 1)
        if landing:
            self.fallen[floor] = landing
        self.blood = {}
        self.bloodDry = {}
        self.grid, self.EnemyPositions, self.rooms, self.proportion, self.nodes = self.generateNewLevel(depth=floor)
        self.setTheme(self.newFloorTheme())
        self.enemyOccupiedItemSpaces = {}
        if self.newFloorMotherlode:
            self.motherlodes.add(floor)
        event = events.roll(floor)
        if event:
            self.floorEvents[floor] = event
        self.trackStarts.add(floor)
        self.PlaceNextLevelDoor()
        if falling:
            self.playerPositionFlat = self.openSpot(self.playerPositionFlat) or self.playerPositionFlat
        self.currentLocation = copy.copy(self.grid[self.playerPositionFlat])
        self.afterLevelChange()

    def tilesAround(self, center, radius):
        """The tiles in a square radius tiles out from center, staying on the map (no wrapping round a row)."""
        R, rows = self.rowLength, self.numberOfSpots // self.rowLength
        cx, cy = center % R, center // R
        return [x + y * R for y in range(cy - radius, cy + radius + 1) for x in range(cx - radius, cx + radius + 1)
                if 0 <= x < R and 0 <= y < rows]

    def generateScorchedLevel(self, depth):
        """A Scorched Depths floor: half Stone rooms, half Molten. Its walls come in blobs, not scattered single
        tiles, so there's wide open ground between them. The Molten Blade waits in a chest in the middle."""
        R, rows = self.rowLength, self.numberOfSpots // self.rowLength
        grid = {i: [0, 0] for i in range(self.numberOfSpots)}
        target, walls = int(self.numberOfSpots * SCORCHED_WALL_SHARE), 0
        while walls < target:
            cx, cy, radius = rand.randrange(R), rand.randrange(rows), rand.randint(1, 3)
            for y in range(cy - radius, cy + radius + 1):
                for x in range(cx - radius, cx + radius + 1):
                    if 0 <= x < R and 0 <= y < rows and self.inCircle(x - cx, y - cy, radius) and grid[x + y * R][0] == 0:
                        grid[x + y * R][0] = 2
                        walls += 1
        center = (rows // 2) * R + R // 2
        if center == self.playerPositionFlat:
            center += 3
        for p in self.tilesAround(self.playerPositionFlat, 2) + self.tilesAround(center, 3):
            grid[p][0] = 0
        rooms, proportion, nodes = self.createRooms(CER.createNodes(grid, R, 5), SCORCHED)
        for p in self.tilesAround(self.playerPositionFlat, 1):  # you arrive on cool stone
            rooms["Molten"].discard(p)
            rooms["Stone"].add(p)
        self.placeRandomItems(grid, items.createRandomStatItems(3), 10, self.playerPositionFlat - 1)
        self.createObjects(grid, rooms)
        grid[center] = [3, 0, [relics.make("molten_blade")]]
        self.newFloorMotherlode = False
        giants = self.placeGiants(grid, rand.randint(*enemies.GIANT_COUNT), avoid=self.tilesAround(center, 4))
        return grid, giants, rooms, proportion, nodes

    # ---------------------------------------------------------------- big enemies
    # A Fire Giant fills size x size tiles. Its anchor (top-left) is the tile on EnemyPositions; every tile of its
    # footprint is [5, visibility, giant], the same object, so anything that hits a tile hits the giant.

    def footprint(self, anchor, size=2):
        """The tiles a size x size enemy anchored here covers, or None if that runs off the map."""
        R, rows = self.rowLength, self.numberOfSpots // self.rowLength
        x, y = anchor % R, anchor // R
        if not (0 <= x <= R - size and 0 <= y <= rows - size):
            return None
        return [(x + dx) + (y + dy) * R for dy in range(size) for dx in range(size)]

    def canFit(self, anchor, size=2, own=(), grid=None):
        """Can a size x size enemy stand anchored here? Every tile open floor (or its own tiles, own)."""
        grid = self.grid if grid is None else grid
        tiles = self.footprint(anchor, size)
        return tiles is not None and all(p in own or (grid[p][0] == 0 and p != self.playerPositionFlat) for p in tiles)

    def putGiant(self, grid, anchor, giant):
        for p in self.footprint(anchor, giant.size):
            grid[p] = [5, grid[p][1], giant]
        giant.anchor = anchor

    def liftGiant(self, grid, giant):
        for p in self.footprint(giant.anchor, giant.size):
            grid[p] = [0, grid[p][1]]

    def placeGiants(self, grid, count, avoid=()):
        """Puts count Fire Giants on open ground, away from where you arrive. Returns their anchors."""
        R, avoid = self.rowLength, set(avoid)
        px, py = self.playerPositionFlat % R, self.playerPositionFlat // R
        anchors = set()
        spots = [i for i in grid if (i % R - px) ** 2 + (i // R - py) ** 2 > 15 ** 2]
        rand.shuffle(spots)
        for a in spots:
            if len(anchors) >= count:
                break
            tiles = self.footprint(a)
            if tiles and not avoid & set(tiles) and self.canFit(a, grid=grid):
                self.putGiant(grid, a, enemies.FireGiant())
                anchors.add(a)
        return anchors

    def isBig(self, enemy):
        return getattr(enemy, "size", 1) > 1

    def oncePerEnemy(self, positions):
        """positions, leaving out every tile after the first that holds the same enemy (a giant's other tiles),
        so a blast covering a whole giant hits it once."""
        seen = set()
        for p in positions:
            tile = self.grid.get(p)
            if tile is not None and tile[0] == 5 and len(tile) > 2:
                if id(tile[2]) in seen:
                    continue
                seen.add(id(tile[2]))
            yield p

    def reachOf(self, giant, anchor, position):
        """How many tiles position is from the nearest tile of a big enemy's body (diagonals count as 1)."""
        R, n = self.rowLength, giant.size
        ax, ay, px, py = anchor % R, anchor // R, position % R, position // R
        return max(max(0, ax - px, px - (ax + n - 1)), max(0, ay - py, py - (ay + n - 1)))

    def giantTurn(self, anchor, giant):
        """One action for a giant. You within its reach (giant.reach tiles of its body, and it can see you, or
        right beside it): it attacks. Otherwise it steps toward you, or where it last saw you, or somewhere it can
        see, if its whole body fits there. Returns its anchor."""
        tiles = self.footprint(anchor, giant.size)
        player = self.playerPositionFlat
        sight = set()
        for p in (tiles[0], tiles[-1]):  # it looks from two corners of its body
            sight |= self.rayCircleVision(p, giant.visionRange, 5)
        sight -= set(tiles)
        if self.peaceful or (self.playerHidden() and not giant.tremorSense):
            sight.discard(player)
        distance = self.reachOf(giant, anchor, player)
        if not self.peaceful and (distance <= 1 or (distance <= getattr(giant, "reach", 1) and player in sight)):
            self.giantHit(giant, anchor)
            return anchor
        if player in sight:
            giant.lastPlayerPosition = player
        elif giant.lastPlayerPosition is None or giant.lastPlayerPosition in tiles:
            open_ = [p for p in sight if self.grid[p][0] == 0]
            giant.lastPlayerPosition = rand.choice(open_) if open_ else None
        target = giant.lastPlayerPosition
        if target is None:
            return anchor
        R = self.rowLength
        # aim the middle of its body at the target
        dx = target % R - (anchor % R + (giant.size - 1) / 2)
        dy = target // R - (anchor // R + (giant.size - 1) / 2)
        sx, sy = (dx > 0) - (dx < 0), (dy > 0) - (dy < 0)
        steps = [(sx, 0), (0, sy)] if abs(dx) >= abs(dy) else [(0, sy), (sx, 0)]
        for mx, my in steps:
            if not (mx or my):
                continue
            x, y = anchor % R + mx, anchor // R + my
            if not 0 <= x < R:
                continue
            new = x + y * R
            if self.canFit(new, giant.size, own=set(tiles)):
                self.liftGiant(self.grid, giant)
                self.putGiant(self.grid, new, giant)
                return new
        giant.lastPlayerPosition = None  # blocked: pick somewhere else next time
        return anchor

    def giantHit(self, giant, anchor):
        """A giant's blow: a normal hit (dodges, Ward and thorns all count), then fire if it landed."""
        before = self.player.damageTaken
        self.hitPlayer(giant, anchor)
        if self.player.damageTaken > before and not self.player.fireImmune():
            dealt = max(0, giant.fireDamage - self.player.fireResistance())
            self.player.damageTaken += dealt
            if dealt == 0:
                self.addPopup("Resisted", self.playerPositionFlat)
            elif BURN_DAMAGE > self.player.fireResistance() and rand.random() < giant.igniteChance:
                self.player.burnTurns = BURN_TURNS

    def stepMolten(self):
        """Standing on Molten floor burns you, unless fire can't hurt you."""
        if self.currentLocation[0] == 2 or self.player.fireImmune():
            return  # (burrowed into a wall: not standing on the floor)
        if plants.floorOf(self.playerPositionFlat, self.rooms) == "Molten":
            self.firePlayer(MOLTEN_FLOOR_DAMAGE)

    def goToNewLevel(self):
        self.saveLevel()
        self.blood = {}
        self.bloodDry = {}
        self.grid, self.EnemyPositions, self.rooms, self.proportion, self.nodes = self.generateNewLevel(depth=self.level + 1)
        self.setTheme(self.newFloorTheme())
        self.enemyOccupiedItemSpaces = {}
        self.level += 1
        if self.newFloorMotherlode:
            self.motherlodes.add(self.level)
        self.deepest = max(self.deepest, self.level)
        event = events.roll(self.level)
        if event:
            self.floorEvents[self.level] = event
        self.PlacePreviousLevelDoor()
        self.PlaceNextLevelDoor()
        self.currentLocation = copy.copy(self.grid[self.playerPositionFlat])
        self.afterLevelChange()

    def floorTypeName(self):
        return f"Motherlode ({self.proportion})" if self.level in self.motherlodes else self.proportion

    def floorSubtitle(self):
        """The second line of the "Floor N" message: the theme, plus the floor type on an ore floor."""
        if self.proportion in wall.ORE_FLOORS:
            return f"{self.floorTypeName()}  -  {self.theme.name}"
        return self.theme.name

    def afterLevelChange(self):
        self.player.wardReady = True
        self.goldWallCount = 0
        self.addUnsealed = False
        self.player.burnTurns = 0  # the stairs put you out
        self.smoke = {}      # smoke, fire and potions in the air stay behind on the floor you left
        self.inFlight = []
        self.fires = {}
        self.freshFires = set()
        self.explosions = []
        self.spurts = []
        self.flecks = []
        self.playerBloodSpot = None
        self.closeWindow("items")
        self.picker = {"ChangingColor": False, "ColorSelected": False}
        self.messageBools["floorLevelMessage"] = True
        self.painter.fade = 255
        self.landFallen()

    def PlacePreviousLevelDoor(self):
        position = self.doorPositions[-1]
        self.grid[position] = [6, 1]
        self.EnemyPositions.discard(position)

    def doorRadius(self):
        """How far (in tiles) from where you arrive the door down can be on this floor. It grows every floor,
        and once it's bigger than the map the door can be anywhere."""
        return DOOR_RADIUS + DOOR_RADIUS_GROWTH * self.level

    def PlaceNextLevelDoor(self):
        R = self.rowLength
        px, py = self.playerPositionFlat % R, self.playerPositionFlat // R
        radius = self.doorRadius()
        while True:
            spots = [i for i in range(self.numberOfSpots) if i != self.playerPositionFlat and self.grid[i][0] in (0, 2)
                     and (i % R - px) ** 2 + (i // R - py) ** 2 <= radius * radius]
            if spots:
                break
            radius += DOOR_RADIUS_GROWTH  # nowhere in range (shouldn't happen): look further out
        i = rand.choice(spots)
        self.grid[i] = [4, 0]
        self.doorPositions.append(i)

    def updateDoors(self):
        currentDoorPos = self.doorPositions[self.level]
        previousDoorPos = self.doorPositions[self.level - 1] if self.level > 0 and self.level not in self.trackStarts else None

        if self.playerPositionFlat == currentDoorPos:
            self.currentPosition = "Door to Next Level"
        elif self.playerPositionFlat == previousDoorPos:
            self.currentPosition = "Door to previous Level"
        elif self.currentLocation[0] == SCORCHED_DOOR:
            self.currentPosition = "Scorched Door"
        elif self.currentLocation[0] == 3:
            self.currentPosition = "Items" if len(self.currentLocation[2]) > 1 else "Item"
        elif self.currentLocation[0] == 9:
            self.currentPosition = "Item pile"
        elif self.currentLocation[0] == 8:
            self.currentPosition = self.currentLocation[2].name + (" (hidden)" if self.playerHidden() else "")
        else:
            self.currentPosition = "Hidden in smoke" if self.playerPositionFlat in self.smoke else "Floor"

        if self.grid[currentDoorPos][0] != 1:
            self.grid[currentDoorPos][0] = 4
        if previousDoorPos is not None and self.grid[previousDoorPos][0] != 1:
            self.grid[previousDoorPos][0] = 6

    # ------------------------------------------------------------ generation

    def setLookPosition(self):
        match self.player.playerDirection:
            case 1:
                self.PlayerLookPosition = self.playerPositionFlat + 1
            case 2:
                self.PlayerLookPosition = self.playerPositionFlat - self.rowLength
            case 3:
                self.PlayerLookPosition = self.playerPositionFlat + self.rowLength
            case _:
                self.PlayerLookPosition = self.playerPositionFlat - 1
        if not self.sameRow(self.playerPositionFlat, self.PlayerLookPosition) and self.player.playerDirection in (0, 1):
            self.PlayerLookPosition = -1  # facing the map's edge: nothing there (not the far side of the next row)
        return self.PlayerLookPosition

    def sameColumn(self, i, j):
        return i % self.rowLength == j % self.rowLength

    def sameRow(self, i, j):
        return i // self.rowLength == j // self.rowLength

    def generateNewLevel(self, addStartingItem=False, depth=0):
        grid = {}
        ListOfEnemyPositions = set()
        for i in range(self.numberOfSpots):
            grid[i] = [0, 0]
        wallChance = rand.choice(WALL_DENSITIES)  # this floor's wall density
        for i in grid.keys():
            if rand.random() < wallChance:
                grid[i][0] = 2
        grid[self.playerPositionFlat] = [0, 0]
        if addStartingItem:
            grid[self.playerPositionFlat - 1] = [3, 0, [items.startingPick]]
        # The first floor is always Mixed, so every starting material (and every herb) is there to find
        oreFloor, motherlode = (None, False) if depth == 0 else self.pickOreFloor(depth)
        self.newFloorMotherlode = motherlode
        rooms, proportion, nodes = self.createRooms(CER.createNodes(grid, self.rowLength, 5), "Mixed" if depth == 0 else oreFloor)
        for room in nodes:
            caveIn = rand.randint(0, 100)
            if caveIn == 0:
                for i in room:
                    if i != self.playerPositionFlat and grid[i][0] == 0:
                        grid[i][0] = 2
        if proportion != "All Gold":
            ListOfEnemyPositions = self.placeRandomEnemies(grid, 5)
        self.placeRandomItems(grid, items.createRandomStatItems(3), 10, self.playerPositionFlat - 1)
        self.createObjects(grid, rooms)
        if proportion in wall.ORE_FLOORS:
            self.placeOreFloorVeins(grid, proportion, depth, motherlode)
        else:
            self.placeVeins(grid, proportion, depth)
        if depth == 0:  # at least one Coal and one Copper vein on the first floor
            for veinClass in (wall.CoalVein, wall.CopperVein):
                walls = [i for i, tile in grid.items() if tile[0] == 2 and not isinstance(tile[2], wall.OreVein)]
                if walls and not any(isinstance(tile[2], veinClass) for tile in grid.values() if tile[0] == 2):
                    self.growVein(grid, rand.choice(walls), veinClass, rand.randint(2, 5))
        self.placeRelicChest(grid, depth, proportion)
        plants.placeWild(grid, rooms, self.rowLength, self.numberOfSpots, avoid={self.playerPositionFlat, self.playerPositionFlat - 1},
                         everyKind=depth == 0)
        owned = self.player.stations if hasattr(self, "player") else set()
        if depth >= 5 and "shrine" not in owned and rand.random() < 0.4:
            self.placeVault(grid, "shrine", ListOfEnemyPositions)
        if proportion == "All Gold" and depth >= 8 and "forge" not in owned and rand.random() < 0.5:
            self.placeVault(grid, "forge", ListOfEnemyPositions)

        return grid, ListOfEnemyPositions, rooms, proportion, nodes

    def placeVeins(self, grid, proportion, depth):
        """Turns clusters of walls into ore veins, by floor type and depth (see wall.VEIN_SPAWNS)."""
        walls = [i for i, tile in grid.items() if tile[0] == 2]
        if not walls:
            return
        scale = self.numberOfSpots / 10000
        for veinClass, firstFloor, rates in wall.VEIN_SPAWNS:
            if depth < firstFloor:
                continue
            expected = rates.get(proportion, 0) * scale
            clusters = int(expected) + (1 if rand.random() < expected % 1 else 0)
            for _ in range(clusters):
                self.growVein(grid, rand.choice(walls), veinClass, rand.randint(2, 5))

    def pickOreFloor(self, depth):
        """(ore floor type, motherlode) for a new floor at this depth, or (None, False) for a normal floor."""
        if self.forcedOreFloor:
            forced, self.forcedOreFloor = self.forcedOreFloor, None
            return forced
        if rand.random() >= wall.ORE_FLOOR_CHANCE:
            return None, False
        unlocked = {name: spec["weight"] for name, spec in wall.ORE_FLOORS.items() if depth >= spec["first"]}
        if not unlocked:
            return None, False
        name = rand.choices(list(unlocked), weights=list(unlocked.values()))[0]
        return name, rand.random() < wall.MOTHERLODE_CHANCE

    def placeOreFloorVeins(self, grid, proportion, depth, motherlode):
        """Fills an ore floor (wall.ORE_FLOORS): a random share of its walls become veins, a third of them coal
        on metal floors. Each vein is 2 to 2^depth tiles (capped by wall.MAX_VEIN_SIZE and by what's left)."""
        spec = wall.ORE_FLOORS[proportion]
        walls = [i for i, tile in grid.items() if tile[0] == 2]
        ores = {cls: weight for cls, weight in spec["ores"].items() if depth >= wall.VEIN_FIRST_FLOOR.get(cls, 0)}
        if not walls or not ores:
            return
        low, high = wall.MOTHERLODE_DENSITY if motherlode else wall.ORE_FLOOR_DENSITY
        budget = int(len(walls) * rand.uniform(low, high))
        coal = int(budget * wall.COAL_SHARE) if spec["coal"] else 0
        biggest = min(2 ** min(depth, 9), wall.MAX_VEIN_SIZE)
        for veinClass, amount in ((wall.CoalVein, coal), (None, budget - coal)):
            misses = 0  # a start on a wall that's already a vein places nothing; give up after many in a row
            while amount > 0 and misses < 200:
                cls = veinClass or rand.choices(list(ores), weights=list(ores.values()))[0]
                placed = self.growVein(grid, rand.choice(walls), cls, rand.randint(2, max(2, min(biggest, amount))))
                amount -= placed
                misses = 0 if placed else misses + 1

    def growVein(self, grid, start, veinClass, size):
        """Spreads a vein from start through neighboring walls until it has size tiles. Returns how many it placed."""
        frontier, placed = [start], 0
        while frontier and placed < size:
            i = frontier.pop(rand.randrange(len(frontier)))
            tile = grid.get(i)
            if tile is None or tile[0] != 2 or isinstance(tile[2], wall.OreVein):
                continue
            tile[2] = veinClass()
            placed += 1
            for neighbor in (i - 1, i + 1, i - self.rowLength, i + self.rowLength):
                if neighbor in grid and (abs(neighbor - i) != 1 or self.sameRow(i, neighbor)):
                    frontier.append(neighbor)
        return placed

    def getRoomType(self, position, rooms):
        for key in rooms.keys():
            if position in rooms[key]:
                return key

    def createWall(self, position, rooms):
        match self.getRoomType(position, rooms):
            case "Stone":
                return wall.StoneWall()
            case "Wood":
                return wall.WoodWall()
            case "Gold":
                return wall.GoldWall()
            case "Molten":
                return wall.MoltenWall()
            case _:
                return wall.SandWall()

    def createNPC(self, position, rooms):
        # TODO: pick enemies by room type / floor level
        if rand.random() < enemies.ORGANIZER_CHANCE:
            return rand.choice(enemies.organizers)()
        return rand.choice(enemies.lowerFloorEnemies)()

    def createObjects(self, grid, rooms):
        for i in grid.keys():
            if grid[i][0] == 2:
                grid[i].append(self.createWall(i, rooms))
            elif grid[i][0] == 5:
                grid[i].append(self.createNPC(i, rooms))

    def placeRandomItems(self, grid, listOfItems, NumOfitems, startingItemPosition):
        while NumOfitems != 0:
            i = rand.randint(0, self.numberOfSpots - 1)
            if grid[i][0] == 0 and i != startingItemPosition and i != self.playerPositionFlat:
                grid[i][0] = 3
                grid[i].append([rand.choice(listOfItems)])
                NumOfitems -= 1

    def placeRandomEnemies(self, grid, amount) -> set:
        placedPositions = set()
        while len(placedPositions) < amount:
            i = rand.randint(0, self.numberOfSpots - 1)
            if i != self.playerPositionFlat and grid[i][0] in (0, 2) and i not in placedPositions:
                placedPositions.add(i)
                grid[i][0] = 5
        return placedPositions

    def createRooms(self, emptyNodes, proportion=None):
        """proportion picks the floor type; None means a random one."""
        rooms = {"Stone": set(), "Wood": set(), "Sand": set(), "Gold": set(), "Molten": set()}

        nodes = []
        for node in emptyNodes:
            nodes.append(set().union(node))

        MostlyStone = [0] * 20 + [1, 2, 3]
        MostlySand = [3] * 27 + [0, 2]
        MostlyWood = [1] * 20 + [2, 0, 3]
        Gold = [2]
        Mixed = [0, 1, 2, 3]
        randomProportions = {"Mostly Stone": MostlyStone, "Mostly Sand": MostlySand, "Mostly Wood": MostlyWood,
                             "All Gold": Gold, "Mixed": Mixed}
        if proportion is None:
            proportion = rand.choice(list(randomProportions))
        if proportion in wall.ORE_FLOORS:  # ore floors have their own room mix (wall.ORE_FLOORS "rooms")
            numbers = {"Stone": 0, "Wood": 1, "Gold": 2, "Sand": 3}
            randomProportions[proportion] = [numbers[room] for room, weight in wall.ORE_FLOORS[proportion]["rooms"].items()
                                             for _ in range(weight)]

        randomProportions[SCORCHED] = [0, 4]  # half Stone rooms, half Molten
        roomNames = {0: "Stone", 1: "Wood", 2: "Gold", 3: "Sand", 4: "Molten"}
        if proportion in ("Mixed", "Geode"):  # these always have some of every room type
            rand.shuffle(emptyNodes)
            for roomName in ("Stone", "Wood", "Gold", "Sand"):
                if emptyNodes:
                    rooms[roomName] = rooms[roomName].union(emptyNodes.pop())
        while len(emptyNodes) > 0:
            node = emptyNodes.pop()
            roomName = roomNames.get(rand.choice(randomProportions[proportion]), "Sand")
            rooms[roomName] = rooms[roomName].union(node)
        return rooms, proportion, nodes

    # ---------------------------------------------------------------- vision

    def createARay(self, startPosition, targetPosition):
        rowLength = self.rowLength
        sX = startPosition % rowLength
        sY = startPosition // rowLength

        tX = targetPosition % rowLength
        tY = targetPosition // rowLength

        angle = math.atan2(tY - sY, tX - sX)
        distance = int(math.sqrt(((tX - sX) ** 2) + ((tY - sY) ** 2)))

        flatRays = {targetPosition}
        for r in range(0, distance + 1):
            x = round(r * math.cos(angle) + sX)
            y = round(r * math.sin(angle) + sY)
            flatRays.add(x + (y * rowLength))

        flatRays.discard(startPosition)
        return flatRays

    def rayCircleVision(self, position, visionRange, selfNum, tremorSense=False) -> set:
        """The tiles seen from position: rays every 0.1 radians out to visionRange, each stopping after the first
        tile that can't be seen through (see rayOffsets for the rays themselves)."""
        positions = set()
        add = positions.add
        R, grid = self.rowLength, self.grid
        h, k = position % R, position // R
        smoke = self.smoke if not tremorSense else {}  # smoke blinds everyone (tremor sense feels through it)
        for ray in rayOffsets(visionRange):
            for dx, dy in ray:
                flat = h + dx + (k + dy) * R
                tile = grid.get(flat)
                if tile is None:
                    continue
                add(flat)
                if flat in smoke and flat != position:
                    break  # sight goes into smoke but not through it, so from inside it you only see the tiles beside you
                if tremorSense:
                    continue
                kind = tile[0]
                if not (kind in SEE_THROUGH or kind == selfNum or (kind == 8 and not tile[2].blocksSight)):
                    break
        return positions

    def seeThroughForPlayer(self, position):
        """The same rule your vision uses: open floor, item piles and short plants don't block it."""
        tile = self.grid[position]
        return tile[0] in (0, 1, 9, expansion.CAMP) or (tile[0] == 8 and not tile[2].blocksSight)

    def lightAround(self, fire, radius=FIRE_LIGHT_RADIUS):
        """The tiles a fire lights: rays out to radius, stopping at (and lighting) the first thing that blocks
        sight. The fire's own tile always lights, whatever is burning there."""
        lit, R = set(), self.rowLength
        fx, fy = fire % R, fire // R
        for ray in rayOffsets(radius, start=1):
            for dx, dy in ray:
                x, y = fx + dx, fy + dy
                if not 0 <= x < R:
                    break
                p = x + y * R
                if p not in self.grid:
                    break
                lit.add(p)
                if p != fire and not self.seeThroughForPlayer(p):
                    break
        lit.add(fire)
        return lit

    def lineOfSight(self, start, end):
        """True if nothing that blocks your sight stands on the straight line between two tiles."""
        R = self.rowLength
        x0, y0, x1, y1 = start % R, start // R, end % R, end // R
        dx, dy = abs(x1 - x0), -abs(y1 - y0)
        sx, sy = (1 if x0 < x1 else -1), (1 if y0 < y1 else -1)
        err = dx + dy
        while (x0, y0) != (x1, y1):
            e2 = 2 * err
            if e2 >= dy:
                err += dy
                x0 += sx
            if e2 <= dx:
                err += dx
                y0 += sy
            if (x0, y0) == (x1, y1):
                return True
            if not self.seeThroughForPlayer(x0 + y0 * R) or x0 + y0 * R in self.smoke:  # smoke blocks sight too
                return False
        return True

    def hiddenBySmoke(self, position):
        """Anything standing in Smoke Bomb smoke can't be seen (it shows as smoke)."""
        return position in self.smoke

    def updateFireLight(self):
        """Which tiles the fires and bonfires light, as {tile: (the nearest fire lighting it, its light radius)}."""
        R = self.rowLength
        self.fireLight = {}
        best = {}
        sources = [(fire, FIRE_LIGHT_RADIUS) for fire in self.fires] + \
                  [(bonfire, expansion.BONFIRE_LIGHT_RADIUS) for bonfire in expansion.bonfires(self)]
        for fire, radius in sources:
            for p in self.lightAround(fire, radius):
                d = (p % R - fire % R) ** 2 + (p // R - fire // R) ** 2
                if p not in best or d < best[p]:
                    best[p], self.fireLight[p] = d, (fire, radius)

    def updateGlowLight(self):
        """Which tiles Glowrocks light, as {tile: brightness 0..1}: each rock lights out to GLOW_RADIUS, fading
        with distance (GLOW_BRIGHTNESS on its own tile, nothing at the edge), and walls stop it like they stop fire
        light. Two rocks lighting the same tile add up. A rock in a pile, under you or under an enemy all count."""
        R = self.rowLength
        rocks = [p for p, tile in self.grid.items() if tile[0] == 9 and items.pileGlows(tile[2])]
        if len(self.currentLocation) > 2 and items.pileGlows(self.currentLocation[2]):
            rocks.append(self.playerPositionFlat)
        rocks += [p for p, ground in self.enemyOccupiedItemSpaces.items() if len(ground) > 2 and items.pileGlows(ground[2])]
        self.glowLight = {}
        for rock in rocks:
            for p in self.lightAround(rock, math.ceil(GLOW_RADIUS)):
                d = math.hypot(p % R - rock % R, p // R - rock // R)
                if d <= GLOW_RADIUS:
                    glow = GLOW_BRIGHTNESS * (1 - d / (GLOW_RADIUS + 0.5))
                    self.glowLight[p] = round(min(1.0, self.glowLight.get(p, 0.0) + glow), 3)

    def torchSpotSeen(self, seen):
        """The torchlit tile nearest you among the tiles in seen (what an enemy can see), or None. Enemies that see
        your torchlight head for it; once they see you, they go for you (enemies with tremor sense don't do this)."""
        lit = seen & getattr(self, "torchLight", set())
        if not lit:
            return None
        R, here = self.rowLength, self.playerPositionFlat
        return min(lit, key=lambda t: (t % R - here % R) ** 2 + (t // R - here // R) ** 2)

    def setPositionsVisible(self):
        visiblePositions = self.rayCircleVision(self.playerPositionFlat, self.player.getVisionRange(), 1)
        # what was in view last time goes back to remembered: just those tiles, unless this is a different floor
        # (or a loaded game) since then, when every tile is checked
        if getattr(self, "visibleGrid", None) is self.grid:
            for i in self.visibleTiles:
                if self.grid[i][1] == 1:
                    self.grid[i][1] = 2
        else:
            for tile in self.grid.values():
                if tile[1] == 1:
                    tile[1] = 2
        for position in visiblePositions:
            self.grid[position][1] = 1
        # Firelight: tiles a fire lights are visible too, from any distance, if nothing blocks your line of sight
        self.updateFireLight()
        if self.playerPositionFlat not in self.smoke:  # from inside smoke you can't see firelight out there
            for position in self.fireLight:
                if position not in visiblePositions and self.lineOfSight(self.playerPositionFlat, position):
                    self.grid[position][1] = 1
        # Glowrock light: the same, from any distance you have a clear line to
        self.updateGlowLight()
        if self.playerPositionFlat not in self.smoke:
            for position in self.glowLight:
                if position not in visiblePositions and self.lineOfSight(self.playerPositionFlat, position):
                    self.grid[position][1] = 1
        if self.player.hasEffect("see_enemies"):
            for position in self.EnemyPositions:
                if position in self.grid and self.grid[position][0] == 5:
                    self.grid[position][1] = 1
        # torchlight: with a torch in hand, the tiles you see by your own light are lit, and enemies can spot them
        self.torchLight = set(visiblePositions) if self.player.holdingTorch() and not self.peaceful else set()
        self.ownSight = set(visiblePositions)  # lit by your own light (Glowrock light adds to it, see renderer.tileLighting)
        if getattr(self, "revealMap", False):  # developer console /reveal: the whole floor is in view
            for tile in self.grid.values():
                tile[1] = 1
        self.visibleGrid = self.grid  # (see the top of this function)
        self.visibleTiles = list(self.grid) if getattr(self, "revealMap", False) else             [i for i in set(visiblePositions) | set(self.fireLight) | set(self.glowLight) | set(self.EnemyPositions)
             if self.grid.get(i, (None, 0))[1] == 1]
        if self.player.seeDoor:
            self.grid[self.doorPositions[self.level]][1] = 2
            self.player.seeDoor = False
        door = self.doorPositions[self.level]
        if self.grid[door][1] == 0:  # Wisdom: sense the door down when it's close, even through walls
            R, radius = self.rowLength, self.doorSense()
            if (door % R - self.playerPositionFlat % R) ** 2 + (door // R - self.playerPositionFlat // R) ** 2 <= radius * radius:
                self.grid[door][1] = 2
                self.addPopup("You sense a door", door)

    def levelUpPreview(self, attribute):
        """What one more point in this attribute would change: [(what, now, after)] for the Level Up window."""
        player = self.player
        now = self.attributeEffects(attribute)
        old, oldBonus = player.attributes[attribute], player.attributeBonuses[attribute]
        player.attributes[attribute] = old + 1
        player.attributeBonuses[attribute] = int(math.log2(old + 1) * 4)
        try:
            after = self.attributeEffects(attribute)
        finally:
            player.attributes[attribute], player.attributeBonuses[attribute] = old, oldBonus
        return {"title": f"{attribute.title()} {old} -> {old + 1}",
                "rows": [(what, a, b) for (what, a), (_, b) in zip(now, after)],
                "note": "Leveling up also heals you fully"}

    def attributeEffects(self, attribute):
        """[(what, value as text)] for everything this attribute affects, at the player's current stats."""
        player = self.player
        bonus = player.attributeBonuses[attribute]
        if attribute == "strength":
            low, high = player.getMinMaxDamage()
            return [("STR bonus to gear", f"+{bonus}"), ("Damage", f"{low}-{high}"), ("Wall Damage", str(player.getWallDamage()))]
        if attribute == "constitution":
            return [("Max HP", str(player.getMaxHealth()))]
        if attribute == "dexterity":  # (Clean Dodge doesn't come from DEX, so it isn't listed)
            return [("Speed", f"{player.getSpeed():.2f}"), ("Evasion", f"{player.evasion() * 100:.1f}%")]
        if attribute == "intelligence":
            odds = dict(recipes.qualityOdds(bonus))
            return [("Crafted Masterwork", f"{odds['Masterwork']}%"), ("Crafted Fine", f"{odds['Fine']}%"),
                    ("Crafted Crude", f"{odds['Crude']}%"), ("Taking apart gives", f"{self.salvagePercent():g}%")]
        if attribute == "wisdom":
            nothing, _, _ = loot.wallOdds(player.attributes["wisdom"])
            return [("Healing potions", f"+{bonus}"), ("Walls give nothing", f"{nothing:g}%"),
                    ("Door sense", f"{self.doorSense()} tile" + ("s" if self.doorSense() != 1 else ""))]
        return []

    def doorSense(self):
        """How many tiles away Wisdom lets you sense the door down."""
        wisdom = self.player.attributes["wisdom"]
        return min(DOOR_SENSE_MOST, DOOR_SENSE + max(0, wisdom - 1) // DOOR_SENSE_WISDOM)

    # --------------------------------------------------------------- enemies

    def thirst(self):
        """Hollow Blade: a hit sometimes heals you."""
        player = self.player
        if player.hasEffect("lifedrinker") and player.damageTaken > 0 and rand.random() < relics.THIRST_CHANCE:
            healed = min(relics.THIRST_HEAL, player.damageTaken)
            player.damageTaken -= healed
            self.addPopup(f"+{healed} HP", self.playerPositionFlat)

    def enemiesInLight(self):
        """Enemies in your light: in sight and within your vision range (not just seen through walls)."""
        if not self.EnemyPositions:
            return []
        lit = self.rayCircleVision(self.playerPositionFlat, self.player.getVisionRange(), 1)
        return [p for p in self.EnemyPositions if p in lit]

    def burnEnemiesInLight(self, damage):
        """Damages every enemy in your light. Returns how many were hit."""
        hit = self.enemiesInLight()
        for position in hit:
            enemy = self.grid[position][2]
            enemy.hp -= damage
            self.bleed(position)
            if enemy.hp <= 0:
                self.killEnemy(position)
        return len(hit)

    def searingLight(self):
        """Lantern of the Deep: every enemy in your light takes damage each turn."""
        if self.player.hasEffect("searing_light"):
            self.burnEnemiesInLight(relics.SEARING_DAMAGE)

    def playerHidden(self):
        """Hidden from enemies: standing in a plant you can hide in, or in a Smoke Bomb's smoke."""
        if self.playerPositionFlat in self.smoke:
            return True
        here = self.currentLocation
        return here[0] == 8 and len(here) > 2 and here[2].hides

    def useConsumable(self, index):
        """Drinks a potion or eats a meal from the inventory (thrown ones go through startThrow instead)."""
        item = self.player.inventory[index]
        self.player.useConsumable(index)
        if item.effect == "Meal":
            self.addPopup(f"Ate {item.name}", self.playerPositionFlat)  # (it replaces any meal still working)
            self.change = True

    # ---------------------------------------------------------------- throwing
    # Enter on a Fire Flask or Smoke Bomb starts aiming: the aim line runs from you to where it will land and the
    # landing spot's reach is outlined. Arrows move the target, Enter throws (one turn), Esc puts it away.
    # Far throws stay in the air for a turn or two (FLIGHT_TURNS) before they land, so you have to lead a target.

    def startThrow(self, index):
        self.throwing = index
        look = self.PlayerLookPosition
        self.currentAimSpot = look if look in self.grid else self.playerPositionFlat
        self.refreshThrowAim()
        self.addPopup("Aim, Enter to throw", self.playerPositionFlat)

    def cancelThrow(self):
        self.throwing = None
        self.throwArea = None
        self.currentAimSpot = None
        self.aimLine = None
        self.change = True

    def onThrowKey(self, key):
        if key == pygame.K_ESCAPE:
            return self.cancelThrow()
        if key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            return self.throw()
        move = self.direction(key)
        if move is None:
            return
        x, y = self.currentAimSpot % self.rowLength + move[0], self.currentAimSpot // self.rowLength + move[1]
        px, py = self.playerPositionFlat % self.rowLength, self.playerPositionFlat // self.rowLength
        target = x + y * self.rowLength
        if 0 <= x < self.rowLength and target in self.grid and math.hypot(x - px, y - py) <= THROW_RANGE:
            self.currentAimSpot = target
            self.refreshThrowAim()

    def linePoints(self, start, target):
        """The tiles on a straight line from start to target, in order, not counting start (Bresenham)."""
        x0, y0 = start % self.rowLength, start // self.rowLength
        x1, y1 = target % self.rowLength, target // self.rowLength
        dx, dy = abs(x1 - x0), -abs(y1 - y0)
        sx, sy = (1 if x1 > x0 else -1), (1 if y1 > y0 else -1)
        err = dx + dy
        points = []
        while (x0, y0) != (x1, y1):
            e2 = 2 * err
            if e2 >= dy:
                err += dy
                x0 += sx
            if e2 <= dx:
                err += dx
                y0 += sy
            points.append((x0, y0))
        return points

    def blocksThrow(self, position):
        """Walls, stations and plants you can't see through stop a thrown potion."""
        tile = self.grid.get(position)
        return tile is None or tile[0] in (2, 7) or (tile[0] == 8 and tile[2].blocksSight)

    def throwPath(self, target):
        """(the tiles the potion flies over, where it lands). It stops short of anything that blocks it and lands
        on the first enemy it reaches. The landing spot is None when there's no room to throw at all."""
        path = []
        for x, y in self.linePoints(self.playerPositionFlat, target):
            position = x + y * self.rowLength
            if not 0 <= x < self.rowLength or self.blocksThrow(position):
                break
            path.append(position)
            if self.grid[position][0] == 5:
                break
        return path, (path[-1] if path else None)

    def inCircle(self, dx, dy, radius):
        """The round area shape used for every splash: radius 2 is the 21-tile circle."""
        return dx * dx + dy * dy <= radius * radius + radius

    def plantsAtEdge(self, center, radius):
        """Plants you can't see through inside the circle: they stop the splash, but fire still reaches them."""
        cx, cy = center % self.rowLength, center // self.rowLength
        out = []
        for y in range(cy - radius, cy + radius + 1):
            for x in range(cx - radius, cx + radius + 1):
                position = x + y * self.rowLength
                tile = self.grid.get(position)
                if not 0 <= x < self.rowLength or tile is None or tile[0] != 8 or not self.inCircle(x - cx, y - cy, radius):
                    continue
                if all(not self.blocksThrow(px + py * self.rowLength) for px, py in self.linePoints(center, position)[:-1]):
                    out.append(position)
        return out

    def blastWalls(self,center,radius,area):
        reached = set(area) | {center}
        cx, cy = center % self.rowLength, center // self.rowLength
        walls = []
        for y in range(cy - radius, cy + radius +1):
            for x in range(cx - radius, cx +radius+1):
                if not 0 <= x < self.rowLength or not self.inCircle(x - cx, y- cy, radius):
                    continue
                position = x + y * self.rowLength
                tile = self.grid.get(position)
                if tile is None or tile[0] != 2 or len(tile) < 3:
                    continue
                neighbors = [(x + dx) + (y + dy) * self.rowLength for dx, dy in ((1,0),(-1,0),(0,1),(0,-1))
                              if 0 <= x + dx < self.rowLength]
                if any(n in reached for n in neighbors):
                    walls.append(position)
        return walls

    def blastArea(self, center, radius):
        """The tiles within the circle around center that a splash can reach (walls stop it)."""
        cx, cy = center % self.rowLength, center // self.rowLength
        area = []
        for y in range(cy - radius, cy + radius + 1):
            for x in range(cx - radius, cx + radius + 1):
                position = x + y * self.rowLength
                if not 0 <= x < self.rowLength or not self.inCircle(x - cx, y - cy, radius):
                    continue
                if self.blocksThrow(position):
                    continue
                if all(not self.blocksThrow(px + py * self.rowLength) for px, py in self.linePoints(center, position)):
                    area.append(position)
        return area

    def flightTurns(self, landing):
        px, py = self.playerPositionFlat % self.rowLength, self.playerPositionFlat // self.rowLength
        distance = math.hypot(landing % self.rowLength - px, landing // self.rowLength - py)
        return next((turns for reach, turns in FLIGHT_TURNS if distance <= reach), FLIGHT_TURNS[-1][1])

    def refreshThrowAim(self):
        item = self.player.inventory[self.throwing]
        path, landing = self.throwPath(self.currentAimSpot)
        self.aimLine = set(path[:-1])  # the landing tile is outlined instead, so you can still see what's on it
        self.throwArea = (landing, self.blastArea(landing, BLAST_RADIUS[item.effect]), self.flightTurns(landing)) if landing else None
        self.change = True

    def throw(self):
        path, landing = self.throwPath(self.currentAimSpot)
        if landing is None:
            self.addPopup("No room to throw", self.playerPositionFlat)
            return
        item = self.player.takeOne(self.throwing)
        self.cancelThrow()
        turns = self.flightTurns(landing)
        shot = {"effect": item.effect, "power": item.bonus, "path": path, "landing": landing, "turns": turns, "flight": turns}
        if turns == 0:
            self.land(shot)
        else:
            self.inFlight.append(shot)
        self.enemyMove = True  # throwing takes your turn

    def land(self, shot):
        """A thrown potion hits the ground. The splash is worked out now, so enemies that moved in are caught."""
        landing = shot["landing"]
        radius = BLAST_RADIUS[shot["effect"]]
        area = self.blastArea(landing, radius)
        self.explosions.append([landing, radius, shot["effect"], pygame.time.get_ticks()])
        if shot["effect"] == "Fire":
            self.igniteArea(area + [p for p in self.plantsAtEdge(landing, radius) if p not in area])
            hit = 0
            for position in self.oncePerEnemy(area):
                tile = self.grid[position]
                if tile[0] == 5 and len(tile) > 2:
                    hit += 1
                    self.fireEnemy(position, shot["power"])
            if self.playerPositionFlat in area:  # too close: you burn too
                hit += 1
                self.firePlayer(shot["power"])
            if not hit:
                self.addPopup("Nothing burns", landing)
        elif shot["effect"] == "Magic":  # Demise Flask: magic damage, but Organizers take root instead
            hit = 0
            for position in self.oncePerEnemy(area):
                tile = self.grid[position]
                if tile[0] == 5 and len(tile) > 2:
                    hit += 1
                    if isinstance(tile[2], enemies.Organizer):
                        organizers.overgrow(self, position)
                    else:
                        self.magicEnemy(position, shot["power"])
            if self.playerPositionFlat in area:  # too close: it hits you too
                hit += 1
                self.magicPlayer(shot["power"])
            if not hit:
                self.addPopup("Nothing there", landing)
        elif shot["effect"] == "Explosive":
            hit = 0
            self.sound.playExplosion()
            self.igniteArea(area + [p for p in self.plantsAtEdge(landing, radius) if p not in area])
            for position in self.oncePerEnemy(area):
                tile = self.grid[position]
                if tile[0] == 5 and len(tile) > 2:
                    hit += 1
                    tile[2].hp -= shot["power"]
                    self.bleed(position)
                    if tile[2].hp <= 0:
                        self.killEnemy(position)
            if self.playerPositionFlat in area:
                hit += 1
                self.player.damageTaken += shot["power"]
                self.bleed(self.playerPositionFlat)
            for position in self.blastWalls(landing,radius,area):
                hit += 1
                w = self.grid[position][2]
                self.chip(position,landing)
                w.brokenPoints |= wall.getRandomPoints((1,self.tileSize -1), (1,self.tileSize -1), self.tileSize ** 2//3)
                w.hp -= recipes.BOMB_WALL_DAMAGE
                if w.hp <= 0: 
                    self.breakWall(position)
            if rand.random() < FLOOR_BREAK_CHANCE:
                hit += 1
                self.collapseFloor(landing, radius)
            if not hit:
                self.addPopup("Boom",landing)
        else:
            for position in area:
                self.smoke[position] = max(self.smoke.get(position, 0), shot["power"])
                tile = self.grid[position]
                if tile[0] == 5 and len(tile) > 2:
                    tile[2].lastPlayerPosition = None  # caught in the smoke: it loses track of you
            self.addPopup("Smoke", landing)
        self.change = True

    # ------------------------------------------------------------- holes
    # A Bomb can break the floor (FLOOR_BREAK_CHANCE): its whole blast circle turns to holes (expansion.HOLE), the
    # floor under its walls too (wall.holeBelow: break one and it's a hole). What was on it falls to the floor below
    # and waits there (self.fallen) until you get there; step on a hole and you fall too. Every fall does FALL_DAMAGE.

    def collapseFloor(self, center, radius):
        """Every tile in the circle becomes a hole, bar doors, stations and camp pieces (they keep a scrap of floor).
        Enemies, chests, item piles and plants on it fall to the floor below; so do you, if you're on it."""
        R = self.rowLength
        cx, cy = center % R, center // R
        # (from the Scorched Depths, what falls lands on the floor that replaces it, at the same number)
        below = self.fallen.setdefault(self.level if self.proportion == SCORCHED else self.level + 1, [])
        for y in range(cy - radius, cy + radius + 1):
            for x in range(cx - radius, cx + radius + 1):
                if not 0 <= x < R or not self.inCircle(x - cx, y - cy, radius):
                    continue
                p = x + y * R
                tile = self.grid.get(p)
                if tile is None:
                    continue
                kind = tile[0]
                if kind == 2:
                    tile[2].holeBelow = True  # it stands over a hole now
                    continue
                if kind in (4, 6, 7, expansion.CAMP, expansion.HOLE, SCORCHED_DOOR):
                    continue
                if kind == 5 and len(tile) > 2 and self.isBig(tile[2]):
                    continue  # a giant is too big to fall: the floor under it holds
                if p == self.playerPositionFlat:  # what you stand on falls with you (you fall: the main loop)
                    if self.currentLocation[0] in (3, 8, 9) and len(self.currentLocation) > 2:
                        expansion.dropOut(self, self.currentLocation[2])
                        below.append((p, self.currentLocation))
                    self.currentLocation = [expansion.HOLE, self.currentLocation[1]]
                    continue
                if kind == 5 and len(tile) > 2:
                    enemy = tile[2]
                    self.EnemyPositions.discard(p)
                    expansion.dropOut(self, enemy)
                    below.append((p, [5, 0, enemy]))
                    under = self.enemyOccupiedItemSpaces.pop(p, None)
                    if under is not None and under[0] in (3, 8, 9) and len(under) > 2:
                        expansion.dropOut(self, under[2])
                        below.append((p, under))
                elif kind in (3, 8, 9) and len(tile) > 2:
                    expansion.dropOut(self, tile[2])
                    below.append((p, tile))
                self.grid[p] = [expansion.HOLE, tile[1]]
        self.change = True

    def fall(self):
        """You fell through a hole: FALL_DAMAGE, and you land on the floor below, where you fell (or on the nearest
        open floor to it there)."""
        self.player.damageTaken += FALL_DAMAGE
        if self.proportion == SCORCHED:  # the floor below the Scorched Depths is a new one, like its door
            self.leaveScorched(falling=True)
        elif self.level < len(self.doorPositions) - 1:
            self.changeLevel(self.level + 1, falling=True)
        else:
            self.goToNewLevel()
        self.bleed(self.playerPositionFlat)

    def openSpot(self, position, avoid=()):
        """position if it's open floor, else the nearest open floor tile to it (None if there's none)."""
        tile = self.grid.get(position)
        if tile is not None and tile[0] == 0 and position not in avoid:
            return position
        R = self.rowLength
        px, py = position % R, position // R
        best = None
        for i, t in self.grid.items():
            if t[0] == 0 and i not in avoid:
                d = (i % R - px) ** 2 + (i // R - py) ** 2
                if best is None or d < best[0]:
                    best = (d, i)
        return best[1] if best else None

    def landFallen(self):
        """What fell into this floor through a hole lands where it fell (or the nearest open floor), now that you're
        here: enemies take FALL_DAMAGE (and may die of it). Faction goblins and goblin chests land as their faction on
        this floor (expansion.land)."""
        for position, tile in self.fallen.pop(self.level, []):
            spot = self.openSpot(position, avoid={self.playerPositionFlat})
            if spot is None:
                continue
            visibility = self.grid[spot][1]
            obj = tile[2]
            if tile[0] == 5:
                self.grid[spot] = [5, visibility, obj]
                self.EnemyPositions.add(spot)
                obj.hp -= FALL_DAMAGE
                if hasattr(obj, "lastPlayerPosition"):
                    obj.lastPlayerPosition = None
                if obj.hp <= 0:
                    self.killEnemy(spot, killer=None)
                else:
                    expansion.land(self, obj, spot)
                continue
            self.grid[spot] = [tile[0], visibility, obj]
            expansion.land(self, obj, spot)
        self.change = True

    # ------------------------------------------------------------------- fire
    # Fire ignores Defense: only Fire Resist (gear) takes damage off it. Fire that gets through has a
    # BURN_CHANCE chance to set the target burning for BURN_TURNS turns, BURN_DAMAGE fire damage a turn.

    def firePlayer(self, damage, canIgnite=True):
        player = self.player
        dealt = max(0, damage - player.fireResistance())
        if dealt == 0:
            self.addPopup("Resisted", self.playerPositionFlat)
            return
        player.damageTaken += dealt
        self.bleed(self.playerPositionFlat)
        if canIgnite and BURN_DAMAGE > player.fireResistance() and rand.random() < BURN_CHANCE:
            player.burnTurns = BURN_TURNS  # shown as flames on you, not a message

    def enemyFireDamage(self, enemy, damage):
        """Fire damage after an enemy's resistance: flat fireResistance first, then fireResistPercent (0-1)."""
        dealt = max(0, damage - getattr(enemy, "fireResistance", 0))
        return round(dealt * (1 - getattr(enemy, "fireResistPercent", 0)))

    def fireEnemy(self, position, damage, canIgnite=True, igniteChance=BURN_CHANCE):
        enemy = self.grid[position][2]
        dealt = self.enemyFireDamage(enemy, damage)
        if dealt == 0:
            self.addPopup("Resisted", position)
            return
        enemy.hp -= dealt
        self.bleed(position)
        if enemy.hp <= 0:
            self.killEnemy(position)
            return
        if canIgnite and self.enemyFireDamage(enemy, BURN_DAMAGE) > 0 and rand.random() < igniteChance:
            enemy.burnTurns = BURN_TURNS  # shown as flames on it (no point setting alight something its burn can't hurt)

    # ------------------------------------------------------------------ magic
    # Magic ignores Defense, like fire: only Magic Resist (gear "MagicRes") takes damage off it for you, and
    # an enemy's magicResistance (flat) then magicResistPercent (0-1). It never sets anything burning.

    def magicPlayer(self, damage):
        dealt = max(0, damage - self.player.magicResistance())
        if dealt == 0:
            self.addPopup("Resisted", self.playerPositionFlat)
            return
        self.player.damageTaken += dealt
        self.bleed(self.playerPositionFlat)

    def magicEnemy(self, position, damage, killer="player"):
        enemy = self.grid[position][2]
        dealt = max(0, damage - getattr(enemy, "magicResistance", 0))
        dealt = round(dealt * (1 - getattr(enemy, "magicResistPercent", 0)))
        if dealt == 0:
            self.addPopup("Resisted", position)
            return
        enemy.hp -= dealt
        self.bleed(position)
        if enemy.hp <= 0:
            self.killEnemy(position, killer)

    def inDemise(self, position):
        plant = self.plantAt(position)
        return plant is not None and plant.kind == organizers.DEMISE

    def stepDemise(self):
        """Organizer's Demise hurts everything standing in it with magic, except Organizers. Its kills are the
        environment's, even Demise you planted: no loot, and only some of the enemy's gold and pocketed
        materials spill on the ground (no one gets the killer's share)."""
        for position in list(self.EnemyPositions):
            tile = self.grid.get(position)
            if tile and tile[0] == 5 and len(tile) > 2 and not isinstance(tile[2], enemies.Organizer) \
                    and self.inDemise(position):
                self.magicEnemy(position, DEMISE_DAMAGE, killer=None)
        if self.inDemise(self.playerPositionFlat) and not self.player.hasEffect("demise_ward"):
            self.magicPlayer(DEMISE_DAMAGE)

    def stepBurning(self):
        """Everything on fire takes its burn damage and burns a turn shorter."""
        for position in list(self.EnemyPositions):
            tile = self.grid.get(position)
            if not tile or tile[0] != 5 or len(tile) < 3 or getattr(tile[2], "burnTurns", 0) <= 0:
                continue
            tile[2].burnTurns -= 1
            self.fireEnemy(position, BURN_DAMAGE, canIgnite=False)
        player = self.player
        if getattr(player, "burnTurns", 0) > 0:
            player.burnTurns -= 1
            self.firePlayer(BURN_DAMAGE, canIgnite=False)

    # ------------------------------------------------------- burning ground
    # A Fire Flask can set the tiles it splashes alight: plain ground with GROUND_FIRE_CHANCE, plants with
    # their catch chance. Anyone standing in fire takes BURN_DAMAGE (and may start burning) every turn.
    # Burning plants spread fire to the plants around them, and burn away when their fire goes out.

    def plantAt(self, position):
        """The plant on a tile, also when you or an enemy is standing in it. None if there isn't one."""
        if position == self.playerPositionFlat:
            here = self.currentLocation
        elif position in self.enemyOccupiedItemSpaces:
            here = self.enemyOccupiedItemSpaces[position]
        else:
            here = self.grid.get(position)
        return here[2] if here and here[0] == 8 and len(here) > 2 else None

    def burnAwayPlant(self, position):
        visibility = self.grid[position][1]
        if position == self.playerPositionFlat:
            self.currentLocation = [0, visibility]
        elif position in self.enemyOccupiedItemSpaces:
            del self.enemyOccupiedItemSpaces[position]  # the enemy's tile becomes floor when it moves on
        else:
            self.grid[position] = [0, visibility]

    def catchChance(self, plant):
        return FIREPROOF_CATCH if plants.PLANTS[plant.kind]["herb"] in recipes.FIRE_HERBS else PLANT_CATCH

    def lightFire(self, position, turns):
        if self.fires.get(position, 0) < turns:
            self.fires[position] = turns
            self.freshFires.add(position)

    def igniteArea(self, area):
        for position in area:
            plant = self.plantAt(position)
            if plant is not None:
                if rand.random() < self.catchChance(plant):
                    self.lightFire(position, PLANT_FIRE_TURNS)
            elif self.grid[position][0] in (0, 1, 5) and rand.random() < GROUND_FIRE_CHANCE:
                self.lightFire(position, GROUND_FIRE_TURNS)

    def eightAround(self, i):
        x = i % self.rowLength
        return [i + dx + dy * self.rowLength for dy in (-1, 0, 1) for dx in (-1, 0, 1)
                if (dx or dy) and 0 <= x + dx < self.rowLength and i + dx + dy * self.rowLength in self.grid]

    def stepFires(self):
        if not self.fires:
            return
        for position in list(self.oncePerEnemy(list(self.fires))):
            if position in self.freshFires:
                continue
            tile = self.grid[position]
            if tile[0] == 5 and len(tile) > 2:
                self.fireEnemy(position, BURN_DAMAGE)
            if position == self.playerPositionFlat:
                self.firePlayer(BURN_DAMAGE)
        spread = []
        for position in self.fires:
            if self.plantAt(position) is None:
                continue
            for near in self.eightAround(position):
                plant = self.plantAt(near)
                if plant is not None and near not in self.fires and near not in spread and rand.random() < self.catchChance(plant):
                    spread.append(near)
        self.freshFires = set()
        for position in list(self.fires):
            self.fires[position] -= 1
            if self.fires[position] <= 0:
                del self.fires[position]
                if self.plantAt(position) is not None:
                    self.burnAwayPlant(position)
        for position in spread:
            self.lightFire(position, PLANT_FIRE_TURNS)
        self.change = True

    # ----------------------------------------------------------------- blood
    # Every hit makes a little spurt and leaves a speck on the floor. At LOW_HEALTH or below, you and enemies
    # bleed: a drip on each tile you leave, and a pool that grows under you while you stay put. A full tile
    # spills into a floor tile beside it. Blood dries away slowly and is left behind when you change floors.

    def bleed(self, position):
        self.spurts.append([position, pygame.time.get_ticks(), rand.random()])
        self.addBlood(position, HIT_SPECK)

    def addBlood(self, position, amount):
        have = self.blood.get(position, 0)
        if have + amount > 1:
            spill = [n for n in self.eightAround(position) if self.grid[n][0] in (0, 1, 5)]
            if spill:
                near = rand.choice(spill)
                self.wetBlood(near,SPILL)
                self.blood[near] = min(1.0, self.blood.get(near, 0) + SPILL)
        self.wetBlood(position,amount)
        self.blood[position] = min(1.0, have + amount)
        self.change = True

    def wetBlood(self,position,amount):
        have = self.blood.get(position,0)
        self.bloodDry[position] = self.bloodDry.get(position,0) * have/(have + amount)

    def chip(self, wallTile, fromTile):
        """Flecks fly off the face of a wall that was just hit, in its colors (and its ore's, for a vein)."""
        tile = self.grid.get(wallTile)
        if not tile or tile[0] != 2 or len(tile) < 3:
            return
        w = tile[2]
        if isinstance(w, wall.OreVein):
            base = self.painter.roomWallColor(wallTile, self.rooms, False)
            colors = [list(w.oreHighlight), list(w.oreColor), themes.mix(list(base), [0, 0, 0], 0.45)]
        else:
            base = self.painter.wallColor(w.name, False)
            colors = [themes.mix(list(base), [255, 255, 255], 0.45), themes.mix(list(base), [0, 0, 0], 0.45), list(base)]
        dx = fromTile % self.rowLength - wallTile % self.rowLength
        dy = fromTile // self.rowLength - wallTile // self.rowLength
        self.flecks.append([wallTile, pygame.time.get_ticks(), rand.random(), (dx, dy), colors])

    def stepBlood(self):
        for position in self.blood:
            self.bloodDry[position] = min(1.0,self.bloodDry.get(position,0) + BLOOD_DRY)
        for position in list(self.EnemyPositions):
            tile = self.grid.get(position)
            if not tile or tile[0] != 5 or len(tile) < 3:
                continue
            enemy = tile[2]
            if not hasattr(enemy, "maxHp"):  # from an old save
                enemy.maxHp = max(1, enemy.hp)
            if 0 < enemy.hp <= max(1, enemy.maxHp * LOW_HEALTH):  # the last HP always counts, so small things bleed too
                last = getattr(enemy, "bloodSpot", None)
                if last == position:
                    self.addBlood(position, POOL)
                elif last is not None:
                    self.addBlood(last, DRIP)
            enemy.bloodSpot = position
        player = self.player
        here = self.playerPositionFlat
        if 0 < player.getCurrentHealth() <= max(1, player.getMaxHealth() * LOW_HEALTH):
            if self.playerBloodSpot == here:
                self.addBlood(here, POOL)
            elif self.playerBloodSpot is not None:
                self.addBlood(self.playerBloodSpot, DRIP)
        self.playerBloodSpot = here

    def animating(self):
        """True while something on screen moves: bursts, fire in view, something burning, or a throw that would
        land at once (its landing tile shows a little burst)."""
        if self.explosions or self.spurts or self.flecks or any(self.grid[p][1] == 1 for p in self.fires) \
                or any(self.grid[p][1] == 1 for p in expansion.bonfires(self)):
            return True
        if getattr(self.player, "burnTurns", 0) > 0:
            return True
        if self.throwArea is not None and self.throwArea[2] == 0:
            return True
        return any(self.grid[p][1] == 1 and len(self.grid[p]) > 2 and getattr(self.grid[p][2], "burnTurns", 0) > 0
                   for p in self.EnemyPositions if p in self.grid)

    def stepThrows(self):
        """Potions in the air get one turn closer to landing."""
        landed = [shot for shot in self.inFlight if shot["turns"] <= 1]
        self.inFlight = [shot for shot in self.inFlight if shot["turns"] > 1]
        for shot in self.inFlight:
            shot["turns"] -= 1
        for shot in landed:
            self.land(shot)

    def fadingHere(self):
        """This floor's fading remembered tiles: {tile: turns faded}."""
        if not hasattr(self, "memoryFade"):
            self.memoryFade = {}
        return self.memoryFade.setdefault(self.level, {})

    def stepForgetting(self):
        """Every remembered tile more than FORGET_DISTANCE from you fades one turn darker; at FORGET_TURNS it's
        forgotten (back to unseen). Tiles in view stop fading and start over next time they're remembered."""
        fading = self.fadingHere()
        R, here = self.rowLength, self.playerPositionFlat
        hx, hy = here % R, here // R
        far = FORGET_DISTANCE * FORGET_DISTANCE
        for i, tile in self.grid.items():
            if tile[1] != 2:
                if i in fading:
                    del fading[i]
                continue
            if tile[0] in (4, 6, SCORCHED_DOOR) or (i % R - hx) ** 2 + (i // R - hy) ** 2 <= far:
                continue
            turns = fading.get(i, 0) + 1
            if turns >= FORGET_TURNS:
                tile[1] = 0
                fading.pop(i, None)
            else:
                fading[i] = turns
            self.change = True

    def memoryShades(self):
        """How dark each remembered tile is painted into the map, 0..1. Past FORGET_DISTANCE that's black (a door
        only to DOOR_SHADE_MOST); closer in, it's how far the tile has faded over time. The smooth falloff inside
        FORGET_DISTANCE isn't painted into tiles (every step would repaint hundreds of them): the renderer lays it
        over the map instead (renderer.drawMemoryFalloff). Worked out again only when you move, a turn passes, or
        the floor changes."""
        fading = self.fadingHere()
        key = (id(self.grid), self.level, self.playerPositionFlat, self.turnCount, len(fading))
        cached = getattr(self, "shadeCache", None)
        if cached and cached[0] == key:
            return cached[1]
        R, here = self.rowLength, self.playerPositionFlat
        hx, hy = here % R, here // R
        edge = FORGET_DISTANCE * FORGET_DISTANCE
        shades = {}
        for i, tile in self.grid.items():
            if tile[1] != 2:
                continue
            door = tile[0] in (4, 6, SCORCHED_DOOR)
            if (i % R - hx) ** 2 + (i // R - hy) ** 2 >= edge:
                shades[i] = DOOR_SHADE_MOST if door else 1.0
            elif not door and i in fading:
                shades[i] = fading[i] / FORGET_TURNS
        self.shadeCache = (key, shades)
        return shades

    def stepSmoke(self):
        for position in list(self.smoke):
            self.smoke[position] -= 1
            if self.smoke[position] <= 0:
                del self.smoke[position]

    def throwView(self):
        """What the renderer needs to show aiming and potions in the air."""
        flying = []
        for shot in self.inFlight:
            path = shot["path"]
            progress = (shot["flight"] - shot["turns"] + 1) / (shot["flight"] + 1)
            flying.append({"landing": shot["landing"], "turns": shot["turns"], "effect": shot["effect"],
                           "area": self.blastArea(shot["landing"], BLAST_RADIUS[shot["effect"]]),
                           "at": path[min(len(path) - 1, int(len(path) * progress))]})
        aim = None
        if self.throwArea is not None:
            landing, area, turns = self.throwArea
            effect = self.player.inventory[self.throwing].effect
            aim = {"landing": landing, "area": area, "turns": turns, "effect": effect}
        smoke = {p: turns for p, turns in self.smoke.items() if self.grid[p][1] != 0}  # over remembered tiles too: sight stops at its edge
        now = pygame.time.get_ticks()
        burning = [p for p in self.EnemyPositions if p in self.grid and self.grid[p][1] == 1 and len(self.grid[p]) > 2
                   and getattr(self.grid[p][2], "burnTurns", 0) > 0]
        if getattr(self.player, "burnTurns", 0) > 0:
            burning.append(self.playerPositionFlat)
        return {"aim": aim, "flying": flying, "smoke": smoke, "time": now / 1000,
                "fires": [p for p in self.fires if self.grid[p][1] == 1], "burning": burning,
                "explosions": [(landing, radius, effect, (now - start) / EXPLOSION_MS)
                               for landing, radius, effect, start in self.explosions if self.grid[landing][1] != 0],
                "spurts": [(tile, (now - start) / SPURT_MS, seed) for tile, start, seed in self.spurts
                           if tile in self.grid and self.grid[tile][1] == 1 and 0 <= now - start < SPURT_MS],
                "flecks": [(tile, (now - start) / FLECK_MS, seed, direction, colors)
                           for tile, start, seed, direction, colors in self.flecks
                           if tile in self.grid and self.grid[tile][1] != 0 and 0 <= now - start < FLECK_MS]}

    def activeEvent(self):
        """The id of the event going on on this floor, or None."""
        event = self.floorEvents.get(self.level)
        return event["id"] if event and event["active"] else None

    def stepFloorEvent(self):
        """Counts down to this floor's event and fires it: its name shows big on screen."""
        event = self.floorEvents.get(self.level)
        if event and event["active"] and event["id"] == "expansion" and not event.get("spawned"):
            event["spawned"] = expansion.spawnWarband(self)  # tries again next turn if there's no room yet
        if not event or event["active"]:
            return
        event["turnsLeft"] -= 1
        if event["turnsLeft"] <= 0:
            event["active"] = True
            self.messageBools["eventMessage"] = True
            self.painter.fade = 255
            self.change = True

    def enemyTurn(self):
        self.turnCount += 1
        self.MoveEnemies()
        expansion.stepCamp(self)
        self.searingLight()
        self.stepBurning()
        self.stepMolten()
        self.stepDemise()
        self.stepFires()
        self.stepBlood()
        self.stepSmoke()
        self.stepForgetting()
        self.stepThrows()
        self.stepFloorEvent()
        growth = events.plantRules(self.activeEvent())
        if self.turnCount % growth.get("growTurns", plants.GROW_TURNS) == 0:
            changed = plants.step(self.grid, self.rooms, self.rowLength, noBirth=expansion.allFarmTiles(self), **growth)
            changed = plants.keepAlive(self.grid, self.rooms, self.rowLength, avoid={self.playerPositionFlat}) or changed
            if changed:
                self.change = True
        player = self.player
        if player.hasEffect("regen") and self.turnCount % 20 == 0 and player.damageTaken > 0:
            player.damageTaken -= 1  # Gilded Amulet
        if player.hasEffect("fed_mend") and self.turnCount % 5 == 0 and player.damageTaken > 0:
            player.damageTaken -= 1  # Bloodcap Stew
        if player.hasEffect("fed_sick") and self.turnCount % relics.SICK_TURNS == 0 and player.getCurrentHealth() > 1:
            player.damageTaken += 1  # Demise Stew's sickness
        for tag in player.stepBuffs():
            self.addPopup(f"{relics.effectName(tag)} wore off", self.playerPositionFlat)
        if self.addUnsealed and not player.hasEffect("seal_ward"):
            validSpots = [k for k in self.grid.keys() if self.grid[k][0] == 2]
            if len(validSpots) > 0:
                addPosition = rand.choice(validSpots)
                self.grid[addPosition] = [5, self.grid[addPosition][1], enemies.Unsealed()]
                self.EnemyPositions.add(addPosition)
            else:
                self.addUnsealed = False

    def MoveEnemies(self):
        listOfNewPositions = set()
        self.movedEnemies = listOfNewPositions  # so an Organizer can find an enemy that already moved this turn
        organizerContext = organizers.gather(self)
        campContext = expansion.beginTurn(self)
        for i in list(self.EnemyPositions):  # a copy: an Organizer can kill an enemy partway through
            if self.grid[i][0] != 5 or len(self.grid[i]) < 3:
                continue  # stale position, the enemy is no longer here
            currentEnemy: enemies.Enemy = self.grid[i][2]
            position = i
            if self.isBig(currentEnemy):  # a giant: its whole body moves at once (giantTurn)
                for action in range(self.enemyActions(currentEnemy)):
                    if self.grid[position][0] != 5 or len(self.grid[position]) < 3 or self.grid[position][2] is not currentEnemy:
                        break
                    before = position
                    position = self.giantTurn(position, currentEnemy)
                    self.faceToward(currentEnemy, before, position)
                listOfNewPositions.add(position)
                continue
            for action in range(self.enemyActions(currentEnemy)):  # a fast one sometimes acts twice
                tile = self.grid[position]
                if action and (tile[0] != 5 or len(tile) < 3 or tile[2] is not currentEnemy):
                    break  # it died (or something took its place) during its first action
                tile.pop()
                before = position
                position, currentEnemy = self.enemyAct(position, currentEnemy, organizerContext, campContext)
                self.faceToward(currentEnemy, before, position)
                self.grid[position].append(currentEnemy)
            listOfNewPositions.add(position)
        # leave out anyone an Organizer killed after it had already moved
        self.EnemyPositions = {p for p in listOfNewPositions if self.grid[p][0] == 5 and len(self.grid[p]) > 2}
        self.movedEnemies = set()


    def enemyActions(self, enemy):
        """How many actions an enemy takes this turn: its speed goes into a pool, and it acts once for each
        whole action there (the rest carries over)."""
        speed = getattr(enemy, "speed", 1)
        if speed == 2:  # saved before speed counted, when the quick ones had 2 (now enemies.FAST)
            speed = enemy.speed = enemies.FAST
        pool = getattr(enemy, "actionPool", 0.0) + speed
        actions = int(pool)
        enemy.actionPool = pool - actions
        return actions

    def enemyAct(self, i, currentEnemy, organizerContext, campContext):
        """One action for the enemy at i (already lifted off its tile). Returns (where it ends up, the enemy)."""
        if isinstance(currentEnemy, enemies.Organizer):  # builders: their own turn (organizers.py)
            return organizers.takeTurn(self, i, currentEnemy, organizerContext)
        if getattr(currentEnemy, "faction", None) is not None:  # an Expansion faction's goblin (expansion.py)
            return expansion.takeTurn(self, i, currentEnemy, campContext), currentEnemy
        finalPosition = expansion.otherTurn(self, i, currentEnemy, campContext)  # fighting back, or drawn to a bonfire
        if finalPosition is not None:
            return finalPosition, currentEnemy
        finalPosition = i
        passes = 0
        moving = True
        sight = None  # what it can see from i: the same on every pass (nothing changes until it moves or digs)
        while moving:
            passes += 1
            if passes > 4:
                break
            if sight is None:
                sight = self.rayCircleVision(i, currentEnemy.visionRange, 5, currentEnemy.tremorSense)
            visiblePositions = set(sight)
            if currentEnemy.lastPlayerPosition is not None:
                if currentEnemy.lastPlayerPosition == i or self.grid[currentEnemy.lastPlayerPosition][0] == 5:
                    currentEnemy.lastPlayerPosition = None
            visiblePositions.discard(i)
            if currentEnemy.allSight:
                visiblePositions.add(self.playerPositionFlat)
            if self.peaceful:  # developer console /peaceful: you're invisible to them
                visiblePositions.discard(self.playerPositionFlat)
                if currentEnemy.lastPlayerPosition == self.playerPositionFlat:
                    currentEnemy.lastPlayerPosition = None
            if len(visiblePositions) == 0:
                break
            if self.playerPositionFlat in visiblePositions and self.playerHidden() and not currentEnemy.tremorSense \
                    and self.playerPositionFlat not in self.neighbors(i):
                visiblePositions.discard(self.playerPositionFlat)  # hidden: only an enemy right beside you notices
                if currentEnemy.lastPlayerPosition == self.playerPositionFlat:
                    currentEnemy.lastPlayerPosition = None
                if not visiblePositions:
                    break
            torchSpot = None if currentEnemy.tremorSense else self.torchSpotSeen(visiblePositions)
            if self.playerPositionFlat in visiblePositions:
                currentEnemy.lastPlayerPosition = self.playerPositionFlat
            elif torchSpot is not None and currentEnemy.lastPlayerPosition != self.playerPositionFlat:
                currentEnemy.lastPlayerPosition = torchSpot  # it sees your torchlight: heads into the light
            elif currentEnemy.lastPlayerPosition is None:
                currentEnemy.lastPlayerPosition = rand.choice(list(visiblePositions))

            target = currentEnemy.lastPlayerPosition
            direction = 1 if target > i else -1

            if self.sameColumn(i, target):
                newPosition = (direction * self.rowLength) + i
            elif self.sameRow(i, target):
                newPosition = direction + i
            elif rand.randint(0, 1):
                newPosition = (direction * self.rowLength) + i
            else:
                newPosition = direction + i

            if newPosition not in self.grid:
                currentEnemy.lastPlayerPosition = None
                continue

            moving = False
            movedToNewPosition = False
            tileType = self.grid[newPosition][0]
            if tileType == 0:
                movedToNewPosition = True
            elif tileType == 1:
                self.hitPlayer(currentEnemy, i)
            elif tileType == 2:
                if currentEnemy.dig:
                    self.chip(newPosition, i)
                    self.grid[newPosition][2].takeDamage(currentEnemy.wallDamage, self.tileSize)
                    if self.grid[newPosition][2].hp <= 0:
                        self.enemyBrokeWall(newPosition, currentEnemy)
                elif currentEnemy.burrow:
                    self.chip(newPosition, i)
                    self.enemyOccupiedItemSpaces[newPosition] = copy.copy(self.grid[newPosition])
                    self.enemyOccupiedItemSpaces[newPosition][2].hp -= 1
                    self.grid[newPosition] = [0, self.grid[newPosition][1]]
                    movedToNewPosition = True
                elif currentEnemy.lastPlayerPosition == newPosition:
                    currentEnemy.lastPlayerPosition = None
                    moving = True
            elif tileType == 7:  # a station: diggers wear it down, everyone else goes around
                station = self.grid[newPosition][2]
                if currentEnemy.dig and station.claimed:
                    station.hp -= currentEnemy.wallDamage
                    if station.hp <= 0:
                        self.destroyStation(newPosition)
                elif currentEnemy.lastPlayerPosition == newPosition:
                    currentEnemy.lastPlayerPosition = None
                    moving = True
            elif tileType in (3, 9) or (tileType == 8 and self.grid[newPosition][2].walkable):
                self.enemyOccupiedItemSpaces[newPosition] = copy.copy(self.grid[newPosition])
                self.grid[newPosition] = [0, self.grid[newPosition][1]]
                movedToNewPosition = True

            if movedToNewPosition:
                # put back whatever this enemy was standing on (items / burrowed wall)
                if i in self.enemyOccupiedItemSpaces:
                    self.grid[i] = self.enemyOccupiedItemSpaces.pop(i)
                else:
                    self.grid[i][0] = 0
                self.grid[newPosition][0] = 5
                finalPosition = newPosition

        return finalPosition, currentEnemy

    # ----------------------------------------------------------------- items

    def pickUpItem(self):
        index = self.windowSel["items"]
        if not (0 <= index < len(self.roomItems)):
            return
        item = self.roomItems[index]
        if isinstance(item, resources.MaterialStack):
            taken = self.give(item.materialId, item.amount, self.PlayerLookPosition)
            if taken == item.amount:
                self.roomItems.pop(index)
            else:
                item.amount -= taken  # the rest stays on the floor until there's room in the pouch
            return
        item = copy.copy(item)
        if self.player.addItemToInventory(item):
            self.roomItems.pop(index)

    def itemsSpot(self):
        """Where Items Here takes from: the chest or pile you face, otherwise a pile you're standing on."""
        look = self.grid.get(self.PlayerLookPosition)
        if look is not None and look[0] in (3, 9):
            return self.PlayerLookPosition
        if self.currentLocation[0] == 9:
            return self.playerPositionFlat
        return None

    def getItemsFromGrid(self):
        spot = self.itemsSpot()
        if spot is None:
            return None
        ground = self.groundAt(spot)
        return ground[2].items if ground[0] == 9 else ground[2]

    # ----------------------------------------------------------- menu options

    def saveMenuOptions(self, fileName):
        with open(fileName, 'w') as openOptions:
            for key, value in self.menuOptions.items():
                openOptions.write(f"{key},{value}\n")

    def loadMenuOptions(self, fileName):
        try:
            with open(fileName, 'r') as openOptions:
                for line in openOptions:
                    parts = line.strip().split(',')
                    if len(parts) == 2 and parts[0] in self.menuOptions:
                        self.menuOptions[parts[0]] = parts[1] == "True"
        except FileNotFoundError:
            pass
    # ----------------------------------------------------------- pickling

    def saveGame(self,filename = SAVE_FILE):
        self.saveLevel()
        data = {
            "version": SAVE_VERSION,
            "mapSize": (self.rowLength, self.painter.columnLength),
            "screenSize": (self.painter.screenWidth, self.painter.screenHeight),  # so the title can say what Continue needs
            "level": self.level,
            "deepest": self.deepest,
            "levelGrids": self.levelGrids,
            "doorPositions": self.doorPositions,
            "playerPositionFlat": self.playerPositionFlat,
            "currentLocation": self.currentLocation,
            "player": self.player,
            "goldwallCount": self.goldWallCount,
            "addUnsealed": self.addUnsealed,
            "floorEvents": self.floorEvents,
            "motherlodes": self.motherlodes,
            "camps": self.camps,
            "fallen": self.fallen,
            "memoryFade": self.memoryFade,
            "scorchedDoors": self.scorchedDoors,
            "trackStarts": self.trackStarts,
        }
        with open(filename,"wb") as f:
            pickle.dump(data,f)

    def loadGame(self,filename = SAVE_FILE):
        try:
            with open(filename,"rb") as f:
                data = pickle.load(f)
        except FileNotFoundError:
            return False
        except (pickle.UnpicklingError, EOFError,AttributeError):
            return False
        # A save only fits a map of the same size (a different screen resolution gives a different map)
        if SAVE_VERSION == data.get("version") and data.get("mapSize") == (self.rowLength, self.painter.columnLength):
            self.level = data["level"]
            # .get with a default: saves made before "deepest" was added still load
            self.deepest = data.get("deepest", self.level)
            self.levelGrids = data["levelGrids"]
            self.floorEvents = data.get("floorEvents", {})
            self.motherlodes = data.get("motherlodes", set())
            self.camps = data.get("camps", {})
            self.fallen = data.get("fallen", {})
            self.memoryFade = data.get("memoryFade", {})
            self.scorchedDoors = data.get("scorchedDoors", {})
            self.trackStarts = data.get("trackStarts", set())
            self.forcedOreFloor = None  # not saved (a console setting); a loaded game never ran newGame to set it
            self.forcedTheme = None
            self.enemyOccupiedItemSpaces = {}  # (also only set by newGame)
            self.doorPositions = data["doorPositions"]
            self.playerPositionFlat = data["playerPositionFlat"]
            self.currentLocation = data["currentLocation"]
            self.player = data["player"]
            # Saves from before the materials pouch: pickle restores the old player object, which doesn't have
            # these yet, so give them their starting values (the .get-with-a-default idea, for objects)
            if not hasattr(self.player, "materials"):
                self.player.materials = {}
            if not hasattr(self.player, "lootFound"):
                self.player.lootFound = set()
            if not hasattr(self.player, "stations"):
                self.player.stations = set()
            if not hasattr(self.player, "stationPlaced"):
                self.player.stationPlaced = {}
            if not hasattr(self.player, "pouchLimit"):
                self.player.pouchLimit = resources.POUCH_LIMIT
            if not hasattr(self.player, "wardReady"):
                self.player.wardReady = True
            if not hasattr(self.player, "buffs"):
                self.player.buffs = {}
            if not hasattr(self.player, "meal"):
                self.player.meal = None
            self.player.syncSlots()  # saves from before the Back slot
            self.updateOldGems()
            self.updateOldRelics()
            self.goldWallCount = data["goldwallCount"]
            self.addUnsealed = data["addUnsealed"]

            self.LoadLevel(self.level)
            return True
        return False

    def updateOldRelics(self):
        """Relic powers that were changed: old copies get the new power and an up-to-date description."""
        found = list(self.player.inventory) + list(self.player.equipment.values())
        for data in self.levelGrids:
            if data:
                found += [item for tile in data[0].values() if tile[0] == 3 and len(tile) > 2 for item in tile[2]]
        for item in found:
            power = getattr(item, "relicPower", None)
            if power is None:
                continue
            item.relicPower = relics.RENAMED_POWERS.get(power, power)
            item.description = relics.describe([item.relicPower] + list(getattr(item, "enchants", [])))

    def updateOldGems(self):
        """Saves from before the five gem types had one "Gem Vein" and Rough/Cut Gem. They become Amethyst."""
        rename = {"rough_gem": "rough_amethyst", "cut_gem": "cut_amethyst"}
        for old, new in rename.items():
            if old in self.player.materials:
                self.player.materials[new] = self.player.materials.get(new, 0) + self.player.materials.pop(old)
        for data in self.levelGrids:
            if not data:
                continue
            grid = data[0]
            for i, tile in grid.items():
                obj = tile[2] if len(tile) > 2 else None
                if tile[0] == 2 and getattr(obj, "ore", None) == "rough_gem":
                    vein = wall.AmethystVein()
                    vein.hp, vein.brokenPoints = obj.hp, obj.brokenPoints
                    tile[2] = vein
                elif tile[0] == 3 and isinstance(obj, list):
                    for item in obj:
                        if getattr(item, "materialId", None) in rename:
                            item.materialId = rename[item.materialId]

    # ----------------------------------------------------------------- drawing

    def getDirectionName(self):
        return {0: "Left", 1: "Right", 2: "Up", 3: "Down"}.get(self.player.playerDirection)

    def lookingAt(self):
        tile = self.grid.get(self.PlayerLookPosition)
        if tile is None:
            return "Nothing"
        if tile[0] == 2:
            return tile[2].name + (" (over a hole)" if getattr(tile[2], "holeBelow", False) else "")
        if tile[0] == 8:
            plant = tile[2]
            notes = [n for n in (("yours" if plant.planted and getattr(plant, "faction", None) is None else
                                  "goblin crop" if plant.planted else ""), plant.stageLabel()) if n]
            return plant.name + (f" ({', '.join(notes)})" if notes else "")
        if tile[0] == 7:
            station = tile[2]
            return f"{station.name} ({station.hp}/{station.maxHp})" if station.claimed else f"{station.name} (unclaimed)"
        if tile[0] == expansion.CAMP:
            piece = tile[2]
            return f"{piece.name} ({piece.hp}/{piece.maxHp})" if piece.kind == "spawner" else piece.name
        if tile[0] == 5 and len(tile) > 2:
            return tile[2].name + (" (burning)" if getattr(tile[2], "burnTurns", 0) > 0 else "")
        return {0: "Floor", 3: "Chest", 4: "Door Down", 6: "Door Up", SCORCHED_DOOR: "Scorched Door", expansion.HOLE: "Hole (a drop to the floor below)"}.get(tile[0], "Floor")

    def windowSpec(self, windowId):
        """Everything the renderer needs to draw one window."""
        player = self.player
        spec = {"id": windowId, "title": WINDOW_TITLES[windowId], "focused": windowId == self.focus,
                "hotkey": self.settings.nameFor(WINDOW_HOTKEY[windowId]), "kind": "rows", "rows": [],
                "selectable": windowId in LIST_WINDOWS, "selected": self.windowSel[windowId],
                "position": self.settings.windowPositions.get(windowId)}
        if windowId == "character":
            minDamage, maxDamage = player.getMinMaxDamage()
            spec["rows"] = [("Health", f"{player.getCurrentHealth()} / {player.getMaxHealth()}"),
                            ("Actions", f"{getattr(player, 'actionsSpent', 0)} / {getattr(player, 'actionsAllowed', 1)}"),
                            ("AC", player.damageReduction()),
                            ("Evasion", f"{player.evasion() * 100:.1f}%"), ("Clean Dodge", f"{player.cleanDodge() * 100:.0f}%"),
                            ("Fire Resist", player.fireResistance()),
                            ("Magic Resist", player.magicResistance()),
                            ("Door Sense", f"{self.doorSense()} tile" + ("s" if self.doorSense() != 1 else "")),
                            ("Status", ", ".join(([f"Burning ({player.burnTurns})"] if getattr(player, "burnTurns", 0) > 0 else []) +
                                                 [f"{relics.effectName(t)} ({n})" for t, n in player.drawbacks()]) or "Fine"),
                            ("Gold", player.gold),
                            ("Facing", self.getDirectionName()), ("Wall Damage", player.getWallDamage()),
                            ("Damage", f"{minDamage} - {maxDamage}"), ("Vision", player.getVisionRange()),
                            ("Effects", ", ".join(relics.effectName(t) for t in player.gearEffects()) or "None"),
                            ("Meal", f"{player.meal} ({player.mealTurns()})" if getattr(player, "meal", None) and player.mealTurns() else "None")]
        elif windowId == "room":
            spec["rows"] = [("Floor Type", self.floorTypeName()), ("Theme", self.theme.name),
                            ("Room Type", self.getRoomType(self.playerPositionFlat, self.rooms) or "-"),
                            ("Floor", self.level), ("Event", events.name(self.activeEvent()) if self.activeEvent() else "-"),
                            ("Standing On", self.currentPosition), ("Looking At", self.lookingAt())]
            if self.pickerActive():
                spec["rows"].append(("Color Selected", self.selectedColor))
        elif windowId == "equipment":
            spec["rows"] = [(slot, getattr(item, "name", item)) for slot, item in player.equipment.items()]
            if self.swapActive():
                spec["header"] = f"Swap in {self.swap['item'].name}: Enter swaps, Esc cancels"
                spec["dimRows"] = {i for i, slot in enumerate(player.equipment) if slot not in self.swap["slots"]}
            else:  # always shown (not just when focused) so the window doesn't change size
                spec["header"] = "Enter takes off, Ctrl+Enter drops"
        elif windowId == "levelup":
            spec["header"] = f"Gold {player.gold}     Next point costs {player.nextLevelGold}"
            spec["rows"] = [(name.title(), value) for name, value in player.attributes.items()]
            names = list(player.attributes)
            if self.focus == "levelup":  # the attached panel only shows while Level Up is focused
                spec["preview"] = self.levelUpPreview(names[min(self.windowSel["levelup"], len(names) - 1)])
        elif windowId == "items":
            spec["rows"] = [(f"Slot {i + 1}", item.name) for i, item in enumerate(self.roomItems or [])]
        elif windowId == "materials":
            spec["kind"] = "sections"
            sections = [{"title": None, "rows": [("Gold", player.gold, (226, 181, 68))], "note": "Gold also pays for leveling up"}]
            for group in resources.GROUPS:
                rows = [(name, player.materials[mid], color) for mid, (name, g, color) in resources.MATERIALS.items()
                        if g == group and player.materials.get(mid, 0) > 0]
                if rows:
                    sections.append({"title": group, "rows": rows})
            if len(sections) == 1:
                sections.append({"title": None, "rows": [("Pouch is empty. Break walls with E.", "", None)]})
            spec["sections"] = sections
        elif windowId == "loot":
            spec["kind"] = "sections"
            tab = self.windowSel["loot"]
            spec["tabs"] = [name for name, _ in loot.LOOT_TABS]
            spec["tab"] = tab
            found = player.lootFound
            sections = []
            compact = {"title": None, "rows": []}  # sources with one drop: one line each ("Coal Vein   Coal  always x2-3")
            table = loot.LOOT_TABS[tab][1]
            walls = table is loot.WALL_LOOT
            if walls:  # every wall rolls the same 0-2, better with Wisdom
                nothing, one, two = loot.wallOdds(player.attributes["wisdom"])
                sections.append({"title": None, "rows": [], "note":
                                 f"Walls give x0/x1/x2, ore and gem veins x1/x2/x3: {nothing:g}% / {one:g}% / {two:g}%. "
                                 "Wisdom raises the odds of more. Gold walls always give 1 "
                                 "(veins in gold walls too) unless an item changes it."})
                table = {source: [(materialId, 100, loot.wallRange(source))] for source, materialId in table.items()}
            for source, lines in table.items():
                if len(lines) == 1:
                    materialId, chance, (fewest, most) = lines[0]
                    sourceKnown = loot.discoveryKey(source) in found
                    known = loot.discoveryKey(source, materialId) in found
                    amount = f"x{fewest}" if fewest == most else f"x{fewest}-{most}"
                    odds = "always" if chance == 100 else f"{chance}%"
                    if walls:
                        odds = ""
                    color = loot.dropColor(materialId)
                    label = loot.displayName(source) if sourceKnown else "???"
                    what = loot.dropName(materialId) if known else "???"
                    compact["rows"].append((label, "  ".join(p for p in (what, odds, amount) if p), color if known else None))
                    continue
                rows = []
                for materialId, chance, (fewest, most) in lines:
                    known = loot.discoveryKey(source, materialId) in found
                    amount = f"x{fewest}" if fewest == most else f"x{fewest}-{most}"
                    odds = "always" if chance == 100 else f"{chance}%"
                    color = loot.dropColor(materialId)
                    rows.append((loot.dropName(materialId) if known else "???", f"{odds}  {amount}", color if known else None))
                title = loot.displayName(source) if loot.discoveryKey(source) in found else "???"
                sections.append({"title": title, "rows": rows})
            if compact["rows"]:
                sections.append(compact)
            spec["sections"] = sections
        elif windowId == "crafting":
            self.craftSpec(spec)
        elif windowId == "inventory":
            spec["kind"] = "grid"
            spec["items"] = [item.name + (f" x{pc.countOf(item)}" if pc.countOf(item) > 1 else "")
                             for item in player.inventory]
            spec["capacity"] = player.inventoryLimit
            self.fitSelections()
            spec["visibleRows"] = INVENTORY_ROWS
            spec["scroll"] = self.inventoryScroll
            index = self.windowSel["inventory"]
            spec["detail"] = self.itemDetail(player.inventory[index]) if index < len(player.inventory) else \
                [("muted", "Empty slot", "")]
        return spec

    STAT_NAMES = {"Damage": "Damage", "WallDamage": "Wall Damage", "Defense": "Defense", "Light": "Vision", "Health": "Health",
                  "FireRes": "Fire Resist", "MagicRes": "Magic Resist", "Storage": "Inventory Slots",
                  pc.POTION_STACK: "Potions per Slot", "CleanDodge": "Clean Dodge %"}

    def statLines(self, item):
        """[(stat name, bonus)] for a piece of gear."""
        if item.Etype == "DaWa":
            return [("Damage", item.b1), ("Wall Damage", item.b2)]
        if item.Etype in self.STAT_NAMES:
            return [(self.STAT_NAMES[item.Etype], item.bonus)]
        return []

    def itemDetail(self, item):
        """The lines in the inventory's details panel for one item: what it is, its bonuses, its effects, and
        how it compares with what you have on."""
        player = self.player
        lines = [("title", item.name, "")]
        if item.Etype == "Consume" and item.effect == "Meal":
            lines.append(("label", "MEAL", ""))
            lines.append(("body", f"Heals {item.bonus}", ""))
            for tag, turns in getattr(item, "buffs", {}).items():
                name, text = relics.EFFECTS.get(tag, (tag, ""))
                lines.append(("ench", f"{name}: {text} ({turns} turns)", ""))
            if getattr(player, "meal", None):  # only one meal works at a time
                lines.append(("worse", f"Replaces {player.meal}", ""))
            lines.append(("hint", "Enter  eat", ""))
            lines.append(("hint", "Ctrl+Enter  drop", ""))
            return lines
        if items.isGlowrock(item):
            lines.append(("label", "LIGHT", ""))
            lines.append(("body", "Set it down and it gives off a dim light on its tile and the tiles around it, "
                                  "even after you walk away. Pick it back up any time", ""))
            if player.potionStackLimit() > 1 or pc.countOf(item) > 1:
                lines.append(("row", "In this stack", f"{pc.countOf(item)} / {player.potionStackLimit()}"))
            lines.append(("hint", "Enter  set it down", ""))
            lines.append(("hint", "Ctrl+Enter  drop", ""))
            return lines
        if item.Etype == "Consume":
            lines.append(("label", "POTION", ""))
            bonus = player.attributeBonuses.get(item.attributeScaling, 0)
            effect = {"Heal": f"Heals {item.bonus}" + (f" (+{bonus} from WIS)" if bonus else ""),
                      "DoorLocate": "Shows the way to the next floor",
                      "Fire": f"Thrown: {item.bonus} damage to everything where it lands, you included. Can set the ground and plants alight",
                      "Smoke": f"Thrown: a smoke cloud for {item.bonus} turns. Everything in it is hidden, and no one sees into or out of it",
                      "Magic": f"Thrown: {item.bonus} magic damage to everything where it lands, you included. "
                            "Organizers it hits become Plant Organizers instead",
                      "Explosive": f"Thrown: {item.bonus} damage to everything where it lands, you included. Breaks nearby walls"}.get(item.effect, item.effect)
                               
            lines.append(("body", effect, ""))
            if player.potionStackLimit() > 1 or pc.countOf(item) > 1:
                lines.append(("row", "In this stack", f"{pc.countOf(item)} / {player.potionStackLimit()}"))
            lines.append(("hint", "Enter  aim and throw" if item.effect in THROWN_EFFECTS else "Enter  use", ""))
            lines.append(("hint", "Ctrl+Enter  drop", ""))
            return lines
        lines.append(("label", (item.slot or "").upper(), getattr(item, "quality", "")))
        scaling = player.scalingBonus(item)
        attrs = item.attributeScaling if isinstance(item.attributeScaling, (tuple, list)) else (item.attributeScaling,)
        attrNames = "+".join(a[:3].upper() for a in attrs if a)
        for stat, value in self.statLines(item):
            lines.append(("row", stat, f"+{value}" + (f"  (+{scaling} {attrNames})" if scaling and attrNames in ("STR", "STR+INT") else "")))
        tags = ([item.relicPower] if getattr(item, "relicPower", None) else []) + list(getattr(item, "enchants", []))
        for tag in tags:
            name, text = relics.EFFECTS.get(tag, (tag, ""))
            lines.append(("ench", f"{name}: {text}", ""))
        if item.Etype == "Unique" and not tags and item.description not in (None, "None"):
            lines.append(("ench", item.description, ""))
        slots = player.slotsFor(item)
        if slots:
            worn = [player.equipment[s] for s in slots if player.equipment[s] != "None"]
            free = len(worn) < len(slots)
            lines.append(("label", "NOW WEARING", "free slot" if free else ""))
            for other in worn:
                lines.append(("muted", other.name, ""))
                theirs = dict(self.statLines(other))
                for stat, value in self.statLines(item):
                    diff = value - theirs.get(stat, 0)
                    if diff:
                        lines.append(("better" if diff > 0 else "worse", f"{stat} {'+' if diff > 0 else ''}{diff} vs this", ""))
            lines.append(("hint", "Enter  equip" if free else "Enter  swap", ""))
        lines.append(("hint", "Ctrl+Enter  drop", ""))
        return lines

    def pauseRowValue(self, label):
        if label == "Light Style":
            return self.settings.lightStyle.title()
        return self.menuOptions.get(label)

    def unsealedInView(self):
        """True if an Unsealed is on screen (its seal shards circle it, so it needs redrawing)."""
        for position in self.EnemyPositions:
            tile = self.grid.get(position)
            if tile and tile[1] == 1 and len(tile) > 2 and getattr(tile[2], "name", "") == "Unsealed":
                return True
        return False

    def lightStyle(self):
        """How the light animates right now, or None when Animated Light is off."""
        if not self.menuOptions["Animated Light"]:
            return None
        return self.settings.lightStyle

    def pauseView(self):
        if self.pausePage is None:
            return None
        hotkeys = [(label, self.settings.nameFor(action)) for action, label, _ in HOTKEY_ACTIONS]
        hotkeys.append(("Reset to Defaults", ""))
        return {"page": self.pausePage, "level": self.level, "sel": self.pauseSel,
                "rows": [(kind, label, self.pauseRowValue(label)) for kind, label in PAUSE_ROWS],
                "hotkeys": hotkeys, "hotkeySel": self.hotkeySel, "perColumn": HOTKEYS_PER_COLUMN,
                "rebinding": self.rebinding, "message": self.hotkeyMessage, "fixed": FIXED_KEYS}

    def popupView(self):
        """(text, map position, age 0..1) for each popup still rising."""
        now = pygame.time.get_ticks()
        return [(text, position, (now - start) / 1000 / POPUP_SECONDS) for text, position, start in self.popups if start <= now]

    def draw(self, lightOnly=False, glintOnly=False, overlayOnly=False):
        if self.scene == "title":
            self.painter.drawTitle(self.titleOptions(), self.titleSel, self.titleMessage, self.titleFade, *self.titleView(), fog=self.titleFog)
            return
        if self.scene == "attempts":
            self.painter.drawAttempts(self.attemptList, self.attemptScroll)
            return

        messageKey, messageText = None, None
        messageTexts = {"escapeMessage": "Escape", "floorLevelMessage": f"{SCORCHED}\n{self.theme.name}" if self.proportion == SCORCHED else f"Floor {self.level}\n{self.floorSubtitle()}",
                        "brokenSealMessage": "The Seal is Broken",
                        "eventMessage": events.name(self.activeEvent()) if self.activeEvent() else ""}
        for key, active in self.messageBools.items():
            if active:
                messageKey, messageText = key, messageTexts[key]
                break

        # The focused window is drawn last so it sits on top of any it overlaps
        self.windowDrawOrder = [w for w in self.openWindows if w != self.focus]
        if self.focus in self.openWindows:
            self.windowDrawOrder.append(self.focus)

        hud = None
        if self.menuOptions["Mini HUD"]:
            hud = (self.player.getCurrentHealth(), self.player.getMaxHealth(), self.player.gold, self.level)

        messageFinished, self.windowRects = self.painter.draw(
            grid=self.grid, rooms=self.rooms, player=self.player, playerPosition=self.playerPositionFlat,
            aimLine=self.aimLine, throws=self.throwView(), hud=hud,
            windows=[self.windowSpec(w) for w in self.windowDrawOrder], pause=self.pauseView(),
            message=messageText, fadeStep=FADE_STEPS.get(messageKey, 0),
            lightTime=self.lightStep / SWAY_FPS, lightStyle=self.lightStyle(), lightOnly=lightOnly, glintOnly=glintOnly, overlayOnly=overlayOnly,
            fireLight=getattr(self, "fireLight", {}), glowLight=getattr(self, "glowLight", {}), ownSight=getattr(self, "ownSight", set()),
            memoryFade=self.memoryShades(), memoryFalloff=(FORGET_DISTANCE, FORGET_CURVE, DOOR_SHADE_MOST),
            popups=self.popupView(), blood=self.blood, bloodDry = self.bloodDry, console=self.console.view(),
            smoke=self.smoke, zoom=self.settings.mapZoom,
            openOrder=[w for w in getattr(self, "openOrder", []) if w in self.openWindows])

        if messageKey is not None and messageFinished:
            self.messageBools[messageKey] = False

    # ----------------------------------------------------------------- loop

    def RunGame(self):
        while self.running:
            self.clock.tick(FPS)
            self.sound.update()

            if self.scene in ("title", "attempts"):
                if self.scene == "title":
                    self.titleFade = min(255, self.titleFade + TITLE_FADE_STEP)
                    self.change = True  # the fog is always moving, so the title redraws every frame
                if self.updater.takeChange():  # the update check found a newer version: show the button
                    if self.scene == "title" and self.titlePage == "main" and self.titleSel == len(self.titleOptions()) - 2:
                        self.titleSel += 1  # the button went in above Quit: keep Quit selected, not the update
                    self.change = True
                for event in pygame.event.get():
                    self.EventDispatcher.dispatch(event)
                # A run that just started (New Game / Continue) is drawn by the playing part of the loop, which works
                # out what you can see first. Drawing it here would show a blank floor and use up the redraw.
                if self.change and self.running and self.scene in ("title", "attempts"):
                    self.draw()
                    self.change = False
                continue

            if True in self.messageBools.values():
                self.overlayChange = True  # a big message fading: only the overlays change

            pressed = pygame.key.get_pressed()
            self.aim = bool(pressed[self.settings.hotkeys["aim"]])
            self.rotate = not self.aim and bool(pressed[self.settings.hotkeys["rotate"]])

            self.setLookPosition()
            self.roomItems = self.getItemsFromGrid()

            for event in pygame.event.get():
                self.EventDispatcher.dispatch(event)
            if not self.running:
                break
            if self.scene != "playing":  # "Quit to Title" was chosen
                continue

            if "items" in self.openWindows and self.getItemsFromGrid() is None:
                self.closeWindow("items")

            self.grid[self.playerPositionFlat][0] = 1

            self.stepCrafting(pygame.time.get_ticks())
            self.stepAutoPlay(pygame.time.get_ticks())

            if self.enemyMove:
                self.spendActions(1)
                self.enemyMove = False

            if self.currentLocation[0] == expansion.HOLE:  # you stepped on a hole, or the floor broke under you
                self.change = True
                self.fall()

            if self.player.actionMade:
                self.change = True
                self.player.actionMade = False

            if self.player.getCurrentHealth() <= 0:
                self.endAttempt()
                continue

            self.updateDoors()

            # Animation steps SWAY_FPS times a second: the light (unless it's turned off) and any Unsealed in view
            step = pygame.time.get_ticks() * SWAY_FPS // 1000
            if step != self.lightStep and (self.lightStyle() is not None or self.unsealedInView()):
                self.lightStep = step
                self.lightChange = True

            # Flames and landing bursts animate at ANIM_FPS
            now = pygame.time.get_ticks()
            self.explosions = [e for e in self.explosions if now - e[3] < EXPLOSION_MS]
            self.spurts = [b for b in self.spurts if now - b[1] < SPURT_MS]
            self.flecks = [f for f in self.flecks if now - f[1] < FLECK_MS]
            if self.animating():
                step = pygame.time.get_ticks() * ANIM_FPS // 1000
                if step != self.animStep:
                    self.animStep = step
                    self.overlayChange = True  # flames, bursts and flecks are drawn over the map; bonfires redraw themselves

            # Popups rise and fade, so they need redrawing every frame until they're gone
            if self.popups:
                now = pygame.time.get_ticks()
                self.popups = [p for p in self.popups if (now - p[2]) / 1000 < POPUP_SECONDS]
                self.overlayChange = True

            if self.change:
                self.setLookPosition()
                self.roomItems = self.getItemsFromGrid()
                self.setPositionsVisible()
                self.draw()
                self.change = False
                self.lightChange = False
                self.overlayChange = False
            elif self.lightChange:
                self.draw(lightOnly=True)  # only the light moved: redraw just the lit tiles
                self.lightChange = False
                self.overlayChange = False
            elif getattr(self, "overlayChange", False):
                self.draw(overlayOnly=True)  # nothing on the map changed: keep it, redraw what's drawn over it
                self.overlayChange = False
            elif self.painter.glintsDue(self.grid, pygame.time.get_ticks()):
                self.draw(glintOnly=True)  # only ore glints changed: redraw just those vein tiles

        pygame.quit()


if __name__ == "__main__":
    gameManager().RunGame()
