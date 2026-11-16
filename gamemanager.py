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
import EventDispatcher as ED
import themes
import attempts
import loot
import resources
import recipes
import relics
import plants
from settings import Settings, HOTKEY_ACTIONS, FIXED_KEYS, LIGHT_STYLES
from renderer import renderer as rend, SWAY_FPS
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
and holding it while pressing Move Left / Move Right moves focus that way. Drag a window by its title bar.
"""

MENU_OPTIONS_FILE = "menuOpts.txt"

# Frame rate cap, and how much the splash messages fade per frame
FPS = 60
# Each message starts at 255 and loses this much every frame: 255 / step / FPS = seconds on screen
FADE_STEPS = {"escapeMessage": 1, "floorLevelMessage": 1.5, "brokenSealMessage": 1.5}
# The title fades in as the exact reverse of the "Escape" message fading out: same speed (about 4 seconds)
TITLE_FADE_STEP = FADE_STEPS["escapeMessage"]
KEY_REPEAT_DELAY = 250     # ms before a held key starts repeating
KEY_REPEAT_INTERVAL = 90   # ms between repeats (about 11 a second)
SAVE_FILE = "savegame.pkl"
SAVE_VERSION = 2  # 2: the map now fills the whole screen, so saves from the old smaller map can't load

# Windows, in the order Tab cycles through them (after the "map" stop)
WINDOW_ORDER = ["character", "room", "equipment", "inventory", "materials", "crafting", "levelup", "items", "loot"]
WINDOW_TITLES = {"character": "Character", "room": "Room", "equipment": "Equipment", "materials": "Materials", "loot": "Loot Table",
                 "inventory": "Inventory", "levelup": "Level Up", "items": "Items Here", "crafting": "Crafting"}
WINDOW_HOTKEY = {"character": "character", "room": "room", "equipment": "equipment", "materials": "materials", "loot": "loot_table",
                 "inventory": "inventory", "levelup": "level_up", "items": "interact", "crafting": "crafting"}
LIST_WINDOWS = {"equipment", "inventory", "levelup", "items", "loot", "crafting"}  # windows that take arrows/Enter when focused

PAUSE_ROWS = [("toggle", "Save on Exit"), ("toggle", "Generate Room"), ("toggle", "Mini HUD"),
              ("toggle", "Animated Light"), ("choice", "Light Style"), ("page", "Hotkeys"), ("action", "Reset Windows"), ("action", "Quit to Title"),
              ("action", "Quit to Desktop")]
HOTKEYS_PER_COLUMN = 9
POPUP_SECONDS = 1.2  # how long a "+2 Wood" popup takes to rise and fade
POPUP_GAP = 450      # ms between two different popups on the same tile, so they don't draw over each other
INVENTORY_COLUMNS = 5
EQUIP_TURNS = 1         # turns to put one item on or take one off (a swap is both)
CRAFT_TURN_MS = 150  # while crafting, one turn passes this often, so you can watch enemies move in
CRAFT_MORE = 5       # Shift+Enter crafts up to this many in a row
THROWN_EFFECTS = {"Fire", "Smoke"}  # potions you aim and throw instead of drinking
THROW_RANGE = 8      # how far (in tiles) a potion can be thrown
FLIGHT_TURNS = [(3, 0), (6, 1), (THROW_RANGE, 2)]  # (up to this distance, turns in the air): close throws land at once
BLAST_RADIUS = {"Fire": 1, "Smoke": 2}  # tiles around the landing spot a thrown potion reaches
BURN_CHANCE = 0.5    # chance fire damage sets the target burning
BURN_TURNS = 3       # how long burning lasts
BURN_DAMAGE = 1      # fire damage burning deals each turn (Fire Resist takes off it like any fire)


class gameManager():
    def __init__(self):
        pygame.init()

        self.win = pygame.display.set_mode((0, 0))
        self.clock = pygame.time.Clock()

        self.painter: rend = rend(self.win)

        self.tileSize = self.painter.setTileSize(10)
        self.rowLength = self.painter.rowLength

        self.numberOfSpots = self.painter.rowLength * self.painter.columnLength

        self.menuOptions = {"Generate Room": True, "Save on Exit": False, "Mini HUD": True, "Animated Light": True}
        self.loadMenuOptions(MENU_OPTIONS_FILE)
        self.settings = Settings()

        # Holding a key repeats it (after KEY_REPEAT_DELAY ms, every KEY_REPEAT_INTERVAL ms), but only for keys
        # where that makes sense: see isRepeatable. keysHeld tells a repeat apart from a fresh press.
        pygame.key.set_repeat(KEY_REPEAT_DELAY, KEY_REPEAT_INTERVAL)
        self.keysHeld = set()

        self.EventDispatcher = ED.EventDispatcher()
        self.SubscribeToEvents()

        self.running = True
        self.windowRects = {}
        self.windowDrawOrder = []
        self.drag = None
        self.goToTitle()

    # ------------------------------------------------------------------ scenes

    def goToTitle(self, message=""):
        self.scene = "title"
        self.titleMessage = message
        self.titleSel = 0
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
        options = ["Continue"] if os.path.exists(SAVE_FILE) else []
        return options + ["New Game", "Attempts", "Quit"]

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
        self.enemyOccupiedItemSpaces = {}

        playerposx, playerposy = self.painter.getCenterCartesian()
        self.playerPositionFlat = playerposx + (playerposy * self.rowLength)

        self.grid, self.EnemyPositions, self.rooms, self.proportion, self.nodes = self.generateNewLevel(True)
        self.setTheme(themes.randomTheme(self.proportion))
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
        self.enemyMove = False

        self.picker = {"ChangingColor": False, "ColorSelected": False}
        self.pickerIndex = 0
        self.selectedColor = "fog"
        self.colorIndex = 0

        self.swap = None  # an equipment swap waiting for Enter (see startSwap)
        self.smoke = {}       # thrown Smoke Bomb clouds: {map position: turns left}
        self.throwing = None  # inventory index of the potion being aimed, or None
        self.throwArea = None # tiles the aimed potion would reach where it lands
        self.inFlight = []    # thrown potions still in the air: {"effect", "power", "path", "landing", "turns", "flight"}
        self.currentPosition = "Floor"
        self.currentAimSpot = None
        self.aimLine = None

        self.messageBools = {"escapeMessage": False, "floorLevelMessage": False, "brokenSealMessage": False}
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

    def onKeyDown(self, event):
        key = event.key
        repeat = key in self.keysHeld
        self.keysHeld.add(key)
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
        for windowId in WINDOW_ORDER:
            if windowId != "items" and self.isAction(key, WINDOW_HOTKEY[windowId]):
                return self.onWindowHotkey(windowId)
        if self.isAction(key, "color_picker"):
            return self.onColorPickerKey()
        if key in (pygame.K_RETURN, pygame.K_KP_ENTER):
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
        elif key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            choice = options[self.titleSel]
            if choice == "Continue":
                if not self.continueGame():
                    self.titleMessage = "That save could not be loaded"
                    self.titleSel = 0
            elif choice == "New Game":
                self.newGame()
            elif choice == "Attempts":
                self.openAttempts()
            else:
                self.onQuit(None)
        elif key == pygame.K_ESCAPE:
            self.onQuit(None)

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
        if windowId not in self.openWindows:
            self.openWindows.append(windowId)
            self.openWindows.sort(key=WINDOW_ORDER.index)
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
                elif item.Etype == "Consume":
                    self.useConsumable(index)
                elif self.player.slotsFor(item) and self.player.freeSlotFor(item) is None:
                    self.startSwap(index)
                else:
                    before = len(self.player.inventory)
                    self.player.equipItem(index)
                    if len(self.player.inventory) < before:
                        self.spendTurns(EQUIP_TURNS)
        elif windowId == "equipment":
            slot = list(self.player.equipment.keys())[index]
            if self.swapActive():
                if slot in self.swap["slots"]:
                    self.player.swapEquip(self.swap["index"], slot)
                    self.spendTurns(2 * EQUIP_TURNS)  # taking one off and putting one on
                    self.swap = None
                    self.focus = "inventory" if "inventory" in self.openWindows else "equipment"
            elif self.player.equipment[slot] != "None":
                if self.player.unEquipItem(slot):
                    self.spendTurns(EQUIP_TURNS)
                else:
                    self.addPopup("Inventory full", self.playerPositionFlat)
        elif windowId == "levelup":
            self.player.levelUp(list(self.player.attributes.keys())[index])
        elif windowId == "items":
            self.onPickUpItem()
        elif windowId == "crafting":
            self.startCrafting(1)

    # --------------------------------------------------------- equipment swap
    # Equipping with every fitting slot full opens the Equipment window on that slot; Enter swaps the item in
    # (the old one takes its place in the inventory), Esc cancels. Arrows only move between the slots it fits.

    def spendTurns(self, turns):
        """Equipping, unequipping and swapping take turns: the enemies move once for each."""
        for _ in range(turns):
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
        rows = recipes.forStation(station) + recipes.relicStationRecipes(station, self.player.inventory)
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
        if recipe.kind == "potion" and len(player.inventory) + recipe.amount > player.inventoryLimit:
            return "not enough room in your inventory"
        return None

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
                player.addItemToInventory(recipe.makeItem(0, 0))
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
        self.grid[position] = [3, self.grid[position][1], [resources.MaterialStack("scrap", rand.randint(1, 2))]]
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
            if recipe.kind in ("setup", "pack"):
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
                rows.append(("need" if have >= n else "short", resources.materialName(m), f"{have} / {n}"))
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

    def hitPlayer(self, enemy, enemyPosition):
        """An enemy attacks the player."""
        player = self.player
        if enemy.name in ("Goblin", "Goblin Chieftan") and player.hasEffect("goblin_fear") and rand.random() < 0.3:
            enemy.lastPlayerPosition = None
            self.addPopup("Flees!", enemyPosition)
            return
        if player.hasEffect("ward") and player.wardReady:
            player.wardReady = False
            self.addPopup("Warded", self.playerPositionFlat)
            return
        player.damageTaken += player.hitDamage(enemy.damage)

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
        elif self.playerPositionFlat in self.doorPositions:
            self.onOpenDoor()

    def onDirectionKey(self, dx, dy, newDirection):
        if self.enemyMove:
            return
        if self.picker["ColorSelected"]:
            self.colorIndex = max(0, min(2, self.colorIndex + dx))
        if self.aim:
            start = self.playerPositionFlat if self.currentAimSpot is None else self.currentAimSpot
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
        if targetLocation not in (7, 8) and self.player.checkValidMoveLocation(targetLocation):  # stations and other plants block
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
            tile[2].hp -= self.player.DealDamage()
            self.thirst()
            if tile[2].hp <= 0:
                self.killEnemy(target)
        elif tile[0] == 3:  # items
            if self.roomItems is not None:
                self.openWindow("items")
        elif tile[0] == 7:  # a crafting station
            self.onStationInteract(target)
        elif tile[0] == 8:  # a plant: harvest it
            self.harvestPlant(target)
        self.enemyMove = True

    # ------------------------------------------------------------------ loot

    def breakWall(self, position):
        """A wall was broken: it becomes floor and its materials go straight into the pouch."""
        tile = self.grid[position]
        name = tile[2].name
        if name == "Gold Wall" and self.proportion == "All Gold":
            self.goldWallCount += 1
            if self.goldWallCount >= 10 and not self.addUnsealed:
                self.messageBools["brokenSealMessage"] = True
                self.painter.fade = 255
                self.addUnsealed = True
        broken = tile.pop()
        tile[0] = 0
        drops = loot.roll(loot.WALL_LOOT, name)
        player = self.player
        if isinstance(broken, wall.OreVein):  # Iron Pick (+1 ore) and Keen Eye (1 in 4 for +1)
            extra = player.countEffect("extra_ore") + sum(1 for _ in range(player.countEffect("keen_eye")) if rand.random() < 0.25)
            drops = [(m, n + extra if m == broken.ore else n) for m, n in drops]
        if player.hasEffect("gold_double"):
            drops = [(m, n * 2 if m == "gold" else n) for m, n in drops]
        self.collectDrops(drops, name, position)

    def harvestPlant(self, position):
        """A plant was picked: its herb (and sometimes a seed) goes straight into the pouch."""
        name = self.grid[position][2].name
        self.grid[position] = [0, self.grid[position][1]]
        self.collectDrops(loot.roll(loot.PLANT_LOOT, name), name, position)

    def killEnemy(self, position):
        """An enemy died: it pays its gold, rolls its loot table, and any drops land on its tile as an item pile."""
        tile = self.grid[position]
        enemy = tile.pop()
        player = self.player
        gold = enemy.gold + 3 * player.countEffect("gold_per_kill") + player.countEffect("lucky")
        if gold:
            self.give("gold", gold, position)
        self.EnemyPositions.discard(position)
        drops = loot.roll(loot.ENEMY_LOOT, enemy.name)
        self.player.lootFound.add(loot.discoveryKey(enemy.name))
        # Like breaking a wall, the drops go straight to you with a popup each. Relics (items) and whatever
        # doesn't fit in a full pouch are left on the enemy's tile instead.
        stacks = []
        for dropId, amount in drops:
            self.player.lootFound.add(loot.discoveryKey(enemy.name, dropId))
            if loot.isRelicDrop(dropId):
                relic = relics.make(dropId[6:])
                stacks.append(relic)
                self.addPopup(f"{relic.name} dropped!", position)
            else:
                left = amount - self.give(dropId, amount, position)
                if left:
                    stacks.append(resources.MaterialStack(dropId, left))
        underneath = self.enemyOccupiedItemSpaces.pop(position, None)  # what it was standing on, if anything
        if underneath is not None and underneath[0] == 3:  # an item pile: anything left over joins it
            underneath[2].extend(stacks)
            underneath[1] = tile[1]
            self.grid[position] = underneath
        elif underneath is not None and not stacks:  # a burrower died inside a wall: the wall comes back
            self.grid[position] = underneath
        elif stacks:  # (a burrower inside a wall that left something: the wall crumbles so it can be picked up)
            self.grid[position] = [3, tile[1], stacks]
        else:
            self.grid[position] = [0, tile[1]]

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
        added = self.player.addMaterial(materialId, amount)
        name = resources.materialName(materialId)
        if added == amount:
            self.addPopup(f"+{added} {name}", position)
        elif added:
            self.addPopup(f"+{added} {name} (pouch full)", position)
        else:
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
            self.grid[self.PlayerLookPosition] = [0, 1]
            self.roomItems = None
            self.closeWindow("items")

    def onOpenDoor(self):
        if self.playerPositionFlat == self.doorPositions[self.level]:
            if self.level < len(self.doorPositions) - 1:
                self.changeLevel(self.level + 1)
            else:
                self.goToNewLevel()
        elif self.level > 0 and self.playerPositionFlat == self.doorPositions[self.level - 1]:
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
        data = [self.grid, self.rooms, self.proportion, self.EnemyPositions, self.enemyOccupiedItemSpaces, self.theme]
        if self.level < len(self.levelGrids):
            self.levelGrids[self.level] = data
        else:
            self.levelGrids.append(data)

    def LoadLevel(self, level):
        self.grid, self.rooms, self.proportion, self.EnemyPositions, self.enemyOccupiedItemSpaces, theme = self.levelGrids[level]
        self.setTheme(theme)

    def changeLevel(self, newLevel):
        self.saveLevel()
        self.level = newLevel
        self.deepest = max(self.deepest, self.level)
        self.LoadLevel(newLevel)
        self.currentLocation = copy.copy(self.grid[self.playerPositionFlat])
        self.afterLevelChange()

    def goToNewLevel(self):
        self.saveLevel()
        self.grid, self.EnemyPositions, self.rooms, self.proportion, self.nodes = self.generateNewLevel(depth=self.level + 1)
        self.setTheme(themes.randomTheme(self.proportion))
        self.enemyOccupiedItemSpaces = {}
        self.level += 1
        self.deepest = max(self.deepest, self.level)
        self.PlacePreviousLevelDoor()
        self.PlaceNextLevelDoor()
        self.currentLocation = copy.copy(self.grid[self.playerPositionFlat])
        self.afterLevelChange()

    def afterLevelChange(self):
        self.player.wardReady = True
        self.goldWallCount = 0
        self.addUnsealed = False
        self.player.burnTurns = 0  # the stairs put you out
        self.smoke = {}      # smoke and potions in the air stay behind on the floor you left
        self.inFlight = []
        self.closeWindow("items")
        self.picker = {"ChangingColor": False, "ColorSelected": False}
        self.messageBools["floorLevelMessage"] = True
        self.painter.fade = 255

    def PlacePreviousLevelDoor(self):
        position = self.doorPositions[-1]
        self.grid[position] = [6, 1]
        self.EnemyPositions.discard(position)

    def PlaceNextLevelDoor(self):
        while True:
            i = rand.randint(0, self.numberOfSpots - 1)
            if i != self.playerPositionFlat and self.grid[i][0] in (0, 2):
                self.grid[i] = [4, 0]
                self.doorPositions.append(i)
                break

    def updateDoors(self):
        currentDoorPos = self.doorPositions[self.level]
        previousDoorPos = self.doorPositions[self.level - 1] if self.level > 0 else None

        if self.playerPositionFlat == currentDoorPos:
            self.currentPosition = "Door to Next Level"
        elif self.playerPositionFlat == previousDoorPos:
            self.currentPosition = "Door to previous Level"
        elif self.currentLocation[0] == 3:
            self.currentPosition = "Items" if len(self.currentLocation[2]) > 1 else "Item"
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
        for i in grid.keys():
            if rand.randint(0, 1) == 1:
                grid[i][0] = 2
        grid[self.playerPositionFlat] = [0, 0]
        if addStartingItem:
            grid[self.playerPositionFlat - 1] = [3, 0, [items.startingPick]]
        # The first floor is always Mixed, so every starting material (and every herb) is there to find
        rooms, proportion, nodes = self.createRooms(CER.createNodes(grid, self.rowLength, 5), "Mixed" if depth == 0 else None)
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

    def growVein(self, grid, start, veinClass, size):
        """Spreads a vein from start through neighboring walls until it has size tiles."""
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
            case _:
                return wall.SandWall()

    def createNPC(self, position, rooms):
        # TODO: pick enemies by room type / floor level
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
        rooms = {"Stone": set(), "Wood": set(), "Sand": set(), "Gold": set()}

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

        roomNames = {0: "Stone", 1: "Wood", 2: "Gold", 3: "Sand"}
        if proportion == "Mixed":  # a Mixed floor always has some of every room type
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
        positions = set()
        h = position % self.rowLength
        k = position // self.rowLength
        smoke = self.smoke if selfNum == 5 and not tremorSense else {}  # smoke blinds enemies (tremor sense feels through it)
        t = 0
        while t < 2 * math.pi:
            ray = []
            for r in range(0, visionRange + 1):
                point = (round(r * math.cos(t) + h), round(r * math.sin(t) + k))
                if point not in ray:
                    ray.append(point)
            for p in ray:
                flat = p[0] + (p[1] * self.rowLength)
                if flat not in self.grid:
                    continue
                positions.add(flat)
                if flat in smoke:
                    break  # an enemy sees into smoke but not through it (and sees nothing from inside it)
                tile = self.grid[flat]
                seeThrough = tile[0] == 0 or (tile[0] == 8 and not tile[2].blocksSight)
                if not (seeThrough or tile[0] == selfNum or tremorSense):
                    break
            t += .1
        return positions

    def setPositionsVisible(self):
        visiblePositions = self.rayCircleVision(self.playerPositionFlat, self.player.getVisionRange(), 1)
        for i in self.grid.keys():
            if self.grid[i][1] == 1:
                self.grid[i][1] = 2
        for position in visiblePositions:
            self.grid[position][1] = 1
        if self.player.hasEffect("see_enemies"):
            for position in self.EnemyPositions:
                if position in self.grid and self.grid[position][0] == 5:
                    self.grid[position][1] = 1
        if self.player.seeDoor:
            self.grid[self.doorPositions[self.level]][1] = 2
            self.player.seeDoor = False

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
            if enemy.hp <= 0:
                self.killEnemy(position)
            else:
                self.addPopup(f"-{damage}", position)
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
        """Drinks a potion from the inventory (thrown ones go through startThrow instead)."""
        self.player.useConsumable(index)

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

    def blastArea(self, center, radius):
        """The tiles within radius of center that a splash can reach (walls stop it)."""
        cx, cy = center % self.rowLength, center // self.rowLength
        area = []
        for y in range(cy - radius, cy + radius + 1):
            for x in range(cx - radius, cx + radius + 1):
                position = x + y * self.rowLength
                if not 0 <= x < self.rowLength or (x - cx) ** 2 + (y - cy) ** 2 > radius * radius + radius:
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
        item = self.player.inventory.pop(self.throwing)
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
        area = self.blastArea(landing, BLAST_RADIUS[shot["effect"]])
        if shot["effect"] == "Fire":
            hit = 0
            for position in area:
                tile = self.grid[position]
                if tile[0] == 5 and len(tile) > 2:
                    hit += 1
                    self.fireEnemy(position, shot["power"])
            if self.playerPositionFlat in area:  # too close: you burn too
                hit += 1
                self.firePlayer(shot["power"])
            if not hit:
                self.addPopup("Nothing burns", landing)
        else:
            for position in area:
                self.smoke[position] = max(self.smoke.get(position, 0), shot["power"])
                tile = self.grid[position]
                if tile[0] == 5 and len(tile) > 2:
                    tile[2].lastPlayerPosition = None  # caught in the smoke: it loses track of you
            self.addPopup("Smoke", landing)
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
        self.addPopup(f"-{dealt} HP", self.playerPositionFlat)
        if canIgnite and BURN_DAMAGE > player.fireResistance() and rand.random() < BURN_CHANCE:
            player.burnTurns = BURN_TURNS
            self.addPopup("Burning!", self.playerPositionFlat)

    def enemyFireDamage(self, enemy, damage):
        """Fire damage after an enemy's resistance: flat fireResistance first, then fireResistPercent (0-1)."""
        dealt = max(0, damage - getattr(enemy, "fireResistance", 0))
        return round(dealt * (1 - getattr(enemy, "fireResistPercent", 0)))

    def fireEnemy(self, position, damage, canIgnite=True):
        enemy = self.grid[position][2]
        dealt = self.enemyFireDamage(enemy, damage)
        if dealt == 0:
            self.addPopup("Resisted", position)
            return
        enemy.hp -= dealt
        if enemy.hp <= 0:
            self.killEnemy(position)
            return
        self.addPopup(f"-{dealt}", position)
        if canIgnite and self.enemyFireDamage(enemy, BURN_DAMAGE) > 0 and rand.random() < BURN_CHANCE:
            enemy.burnTurns = BURN_TURNS  # (no point setting alight something its burn can't hurt)
            self.addPopup("Burning!", position)

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

    def stepThrows(self):
        """Potions in the air get one turn closer to landing."""
        landed = [shot for shot in self.inFlight if shot["turns"] <= 1]
        self.inFlight = [shot for shot in self.inFlight if shot["turns"] > 1]
        for shot in self.inFlight:
            shot["turns"] -= 1
        for shot in landed:
            self.land(shot)

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
            aim = {"landing": landing, "area": area, "turns": turns, "effect": self.player.inventory[self.throwing].effect}
        smoke = [p for p in self.smoke if self.grid[p][1] == 1]
        return {"aim": aim, "flying": flying, "smoke": smoke}

    def enemyTurn(self):
        self.turnCount += 1
        self.MoveEnemies()
        self.searingLight()
        self.stepBurning()
        self.stepSmoke()
        self.stepThrows()
        if self.turnCount % plants.GROW_TURNS == 0:
            changed = plants.step(self.grid, self.rooms, self.rowLength)
            changed = plants.keepAlive(self.grid, self.rooms, self.rowLength, avoid={self.playerPositionFlat}) or changed
            if changed:
                self.change = True
        player = self.player
        if player.hasEffect("regen") and self.turnCount % 20 == 0 and player.damageTaken > 0:
            player.damageTaken -= 1  # Gilded Amulet
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
        for i in self.EnemyPositions:
            if self.grid[i][0] != 5 or len(self.grid[i]) < 3:
                continue  # stale position, the enemy is no longer here
            currentEnemy: enemies.Enemy = self.grid[i].pop()
            finalPosition = i
            passes = 0
            moving = True
            while moving:
                passes += 1
                if passes > 4:
                    break
                visiblePositions = self.rayCircleVision(i, currentEnemy.visionRange, 5, currentEnemy.tremorSense)
                if currentEnemy.lastPlayerPosition is not None:
                    if currentEnemy.lastPlayerPosition == i or self.grid[currentEnemy.lastPlayerPosition][0] == 5:
                        currentEnemy.lastPlayerPosition = None
                visiblePositions.discard(i)
                if currentEnemy.allSight:
                    visiblePositions.add(self.playerPositionFlat)
                if len(visiblePositions) == 0:
                    break
                if self.playerPositionFlat in visiblePositions and self.playerHidden() and not currentEnemy.tremorSense \
                        and self.playerPositionFlat not in self.neighbors(i):
                    visiblePositions.discard(self.playerPositionFlat)  # hidden: only an enemy right beside you notices
                    if currentEnemy.lastPlayerPosition == self.playerPositionFlat:
                        currentEnemy.lastPlayerPosition = None
                    if not visiblePositions:
                        break
                if self.playerPositionFlat in visiblePositions:
                    currentEnemy.lastPlayerPosition = self.playerPositionFlat
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
                        self.grid[newPosition][2].takeDamage(currentEnemy.wallDamage, self.tileSize)
                        if self.grid[newPosition][2].hp <= 0:
                            self.grid[newPosition].pop()
                            self.grid[newPosition][0] = 0
                    elif currentEnemy.burrow:
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
                elif tileType == 3 or (tileType == 8 and self.grid[newPosition][2].walkable):
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

            self.grid[finalPosition].append(currentEnemy)
            listOfNewPositions.add(finalPosition)
        self.EnemyPositions = listOfNewPositions

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

    def getItemsFromGrid(self):
        gridList = self.grid.get(self.PlayerLookPosition)
        if gridList is not None and gridList[0] == 3:
            return gridList[2]
        return None

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
            "level": self.level,
            "deepest": self.deepest,
            "levelGrids": self.levelGrids,
            "doorPositions": self.doorPositions,
            "playerPositionFlat": self.playerPositionFlat,
            "currentLocation": self.currentLocation,
            "player": self.player,
            "goldwallCount": self.goldWallCount,
            "addUnsealed": self.addUnsealed
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
            return tile[2].name
        if tile[0] == 8:
            return tile[2].name + (" (yours)" if tile[2].planted else "")
        if tile[0] == 7:
            station = tile[2]
            return f"{station.name} ({station.hp}/{station.maxHp})" if station.claimed else f"{station.name} (unclaimed)"
        if tile[0] == 5 and len(tile) > 2:
            return tile[2].name + (" (burning)" if getattr(tile[2], "burnTurns", 0) > 0 else "")
        return {0: "Floor", 3: "Chest", 4: "Door Down", 6: "Door Up"}.get(tile[0], "Floor")

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
                            ("AC", player.damageReduction()), ("Fire Resist", player.fireResistance()),
                            ("Status", f"Burning ({player.burnTurns})" if getattr(player, "burnTurns", 0) > 0 else "Fine"),
                            ("Gold", player.gold),
                            ("Facing", self.getDirectionName()), ("Wall Damage", player.getWallDamage()),
                            ("Damage", f"{minDamage} - {maxDamage}"), ("Vision", player.getVisionRange()),
                            ("Effects", ", ".join(relics.effectName(t) for t in player.effects()) or "None")]
        elif windowId == "room":
            spec["rows"] = [("Floor Type", self.proportion), ("Theme", self.theme.name),
                            ("Room Type", self.getRoomType(self.playerPositionFlat, self.rooms) or "-"),
                            ("Floor", self.level), ("Standing On", self.currentPosition), ("Looking At", self.lookingAt())]
            if self.pickerActive():
                spec["rows"].append(("Color Selected", self.selectedColor))
        elif windowId == "equipment":
            spec["rows"] = [(slot, getattr(item, "name", item)) for slot, item in player.equipment.items()]
            if self.swapActive():
                spec["header"] = f"Swap in {self.swap['item'].name}: Enter swaps, Esc cancels"
                spec["dimRows"] = {i for i, slot in enumerate(player.equipment) if slot not in self.swap["slots"]}
        elif windowId == "levelup":
            spec["header"] = f"Gold {player.gold}     Next point costs {player.nextLevelGold}"
            spec["rows"] = [(name.title(), value) for name, value in player.attributes.items()]
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
            for source, lines in loot.LOOT_TABS[tab][1].items():
                if len(lines) == 1:
                    materialId, chance, (fewest, most) = lines[0]
                    sourceKnown = loot.discoveryKey(source) in found
                    known = loot.discoveryKey(source, materialId) in found
                    amount = f"x{fewest}" if fewest == most else f"x{fewest}-{most}"
                    odds = "always" if chance == 100 else f"{chance}%"
                    color = loot.dropColor(materialId)
                    label = loot.displayName(source) if sourceKnown else "???"
                    what = loot.dropName(materialId) if known else "???"
                    compact["rows"].append((label, f"{what}  {odds}  {amount}", color if known else None))
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
            spec["items"] = [item.name for item in player.inventory]
            spec["capacity"] = player.inventoryLimit
            index = self.windowSel["inventory"]
            spec["detail"] = self.itemDetail(player.inventory[index]) if index < len(player.inventory) else \
                [("muted", "Empty slot", "")]
        return spec

    STAT_NAMES = {"Damage": "Damage", "WallDamage": "Wall Damage", "Defense": "Defense", "Light": "Vision", "Health": "Health",
                  "FireRes": "Fire Resist"}

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
        if item.Etype == "Consume":
            lines.append(("label", "POTION", ""))
            bonus = player.attributeBonuses.get(item.attributeScaling, 0)
            effect = {"Heal": f"Heals {item.bonus}" + (f" (+{bonus} from WIS)" if bonus else ""),
                      "DoorLocate": "Shows the way to the next floor",
                      "Fire": f"Thrown: {item.bonus} damage to everything where it lands, you included",
                      "Smoke": f"Thrown: a smoke cloud for {item.bonus} turns. Enemies can't see into it"}.get(item.effect, item.effect)
            lines.append(("body", effect, ""))
            lines.append(("hint", "Enter  aim and throw" if item.effect in THROWN_EFFECTS else "Enter  use", ""))
            return lines
        lines.append(("label", (item.slot or "").upper(), getattr(item, "quality", "")))
        scaling = player.attributeBonuses.get(item.attributeScaling, 0)
        for stat, value in self.statLines(item):
            lines.append(("row", stat, f"+{value}" + (f"  (+{scaling} STR)" if scaling and item.attributeScaling == "strength" else "")))
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

    def draw(self, lightOnly=False):
        if self.scene == "title":
            self.painter.drawTitle(self.titleOptions(), self.titleSel, self.titleMessage, self.titleFade)
            return
        if self.scene == "attempts":
            self.painter.drawAttempts(self.attemptList, self.attemptScroll)
            return

        messageKey, messageText = None, None
        messageTexts = {"escapeMessage": "Escape", "floorLevelMessage": f"Floor {self.level}\n{self.theme.name}",
                        "brokenSealMessage": "The Seal is Broken"}
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
            lightTime=self.lightStep / SWAY_FPS, lightStyle=self.lightStyle(), lightOnly=lightOnly,
            popups=self.popupView())

        if messageKey is not None and messageFinished:
            self.messageBools[messageKey] = False

    # ----------------------------------------------------------------- loop

    def RunGame(self):
        while self.running:
            self.clock.tick(FPS)

            if self.scene in ("title", "attempts"):
                if self.scene == "title" and self.titleFade < 255:
                    self.titleFade = min(255, self.titleFade + TITLE_FADE_STEP)
                    self.change = True
                for event in pygame.event.get():
                    self.EventDispatcher.dispatch(event)
                if self.change and self.running:
                    self.draw()
                    self.change = False
                continue

            if True in self.messageBools.values():
                self.change = True

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

            if self.enemyMove:
                self.change = True
                self.enemyTurn()
                self.enemyMove = False

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

            # Popups rise and fade, so they need redrawing every frame until they're gone
            if self.popups:
                now = pygame.time.get_ticks()
                self.popups = [p for p in self.popups if (now - p[2]) / 1000 < POPUP_SECONDS]
                self.change = True

            if self.change:
                self.setLookPosition()
                self.roomItems = self.getItemsFromGrid()
                self.setPositionsVisible()
                self.draw()
                self.change = False
                self.lightChange = False
            elif self.lightChange:
                self.draw(lightOnly=True)  # only the light moved: redraw just the lit tiles
                self.lightChange = False

        pygame.quit()


if __name__ == "__main__":
    gameManager().RunGame()
