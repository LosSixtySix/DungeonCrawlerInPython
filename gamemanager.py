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
WINDOW_ORDER = ["character", "room", "equipment", "inventory", "levelup", "items"]
WINDOW_TITLES = {"character": "Character", "room": "Room", "equipment": "Equipment",
                 "inventory": "Inventory", "levelup": "Level Up", "items": "Items Here"}
WINDOW_HOTKEY = {"character": "character", "room": "room", "equipment": "equipment",
                 "inventory": "inventory", "levelup": "level_up", "items": "interact"}
LIST_WINDOWS = {"equipment", "inventory", "levelup", "items"}  # windows with a selection; they take arrows/Enter

PAUSE_ROWS = [("toggle", "Save on Exit"), ("toggle", "Generate Room"), ("toggle", "Mini HUD"),
              ("toggle", "Animated Light"), ("choice", "Light Style"), ("page", "Hotkeys"), ("action", "Reset Windows"), ("action", "Quit to Title"),
              ("action", "Quit to Desktop")]
HOTKEYS_PER_COLUMN = 8
INVENTORY_COLUMNS = 5


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
        if self.isAction(event.key, "aim"):
            self.currentAimSpot = None
            self.aimLine = None
            self.change = True

    def onEscape(self):
        if self.pickerActive():
            self.picker = {"ChangingColor": False, "ColorSelected": False}
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
        if windowId == "inventory":
            index = self.windowSel["inventory"] + dx + dy * INVENTORY_COLUMNS
            if 0 <= index < self.player.inventoryLimit:
                self.windowSel["inventory"] = index
            return
        count = {"equipment": len(self.player.equipment), "levelup": len(self.player.attributes),
                 "items": len(self.roomItems) if self.roomItems else 0}[windowId]
        self.windowSel[windowId] = max(0, min(count - 1, self.windowSel[windowId] + dy))

    def onWindowEnter(self, windowId):
        index = self.windowSel[windowId]
        if windowId == "inventory":
            if index < len(self.player.inventory):
                if self.player.inventory[index].Etype == "Consume":
                    self.player.useConsumable(index)
                else:
                    self.player.equipItem(index)
        elif windowId == "equipment":
            self.player.unEquipItem(list(self.player.equipment.keys())[index])
        elif windowId == "levelup":
            self.player.levelUp(list(self.player.attributes.keys())[index])
        elif windowId == "items":
            self.onPickUpItem()

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
        if self.player.checkValidMoveLocation(targetLocation):
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
                if tile[2].hp > 0:
                    tile[2].takeDamage(self.player.getWallDamage(), self.tileSize)
                if tile[2].hp <= 0:
                    if tile[2].name == "Gold Wall":
                        self.player.alterGold(1)
                        if self.proportion == "All Gold":
                            self.goldWallCount += 1
                            if self.goldWallCount >= 10 and not self.addUnsealed:
                                self.messageBools["brokenSealMessage"] = True
                                self.painter.fade = 255
                                self.addUnsealed = True
                    tile[0] = 0
                    tile.pop()
            else:  # burrow into a soft wall
                currentWall = copy.copy(tile)
                currentWall[2].hp -= 1
                if currentWall[2].hp <= 0:
                    tile[0] = 0
                    tile.pop()
                else:
                    self.grid[self.playerPositionFlat] = copy.copy(self.currentLocation)
                    self.currentLocation = currentWall
                    self.playerPositionFlat = target
        elif tile[0] == 5:  # enemy
            tile[2].hp -= self.player.DealDamage()
            if tile[2].hp <= 0:
                self.player.gold += tile.pop().gold
                tile[0] = 0
                self.EnemyPositions.discard(target)
        elif tile[0] == 3:  # items
            if self.roomItems is not None:
                self.openWindow("items")
        self.enemyMove = True

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
        self.grid, self.EnemyPositions, self.rooms, self.proportion, self.nodes = self.generateNewLevel()
        self.setTheme(themes.randomTheme(self.proportion))
        self.enemyOccupiedItemSpaces = {}
        self.level += 1
        self.deepest = max(self.deepest, self.level)
        self.PlacePreviousLevelDoor()
        self.PlaceNextLevelDoor()
        self.currentLocation = copy.copy(self.grid[self.playerPositionFlat])
        self.afterLevelChange()

    def afterLevelChange(self):
        self.goldWallCount = 0
        self.addUnsealed = False
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
        else:
            self.currentPosition = "Floor"

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

    def generateNewLevel(self, addStartingItem=False):
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
        rooms, proportion, nodes = self.createRooms(CER.createNodes(grid, self.rowLength, 5))
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

        return grid, ListOfEnemyPositions, rooms, proportion, nodes

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

    def createRooms(self, emptyNodes):
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
        proportion = rand.choice(list(randomProportions))

        roomNames = {0: "Stone", 1: "Wood", 2: "Gold", 3: "Sand"}
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
                if not (self.grid[flat][0] == 0 or self.grid[flat][0] == selfNum or tremorSense):
                    break
            t += .1
        return positions

    def setPositionsVisible(self):
        visiblePositions = self.rayCircleVision(self.playerPositionFlat, self.player.visionRange, 1)
        for i in self.grid.keys():
            if self.grid[i][1] == 1:
                self.grid[i][1] = 2
        for position in visiblePositions:
            self.grid[position][1] = 1
        if self.player.seeDoor:
            self.grid[self.doorPositions[self.level]][1] = 2
            self.player.seeDoor = False

    # --------------------------------------------------------------- enemies

    def enemyTurn(self):
        self.MoveEnemies()
        if self.addUnsealed:
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
                    self.player.damageTaken += currentEnemy.damage
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
                elif tileType == 3:
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
        item = copy.copy(self.roomItems[index])
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
            self.goldWallCount = data["goldwallCount"]
            self.addUnsealed = data["addUnsealed"]

            self.LoadLevel(self.level)
            return True
        return False

    # ----------------------------------------------------------------- drawing

    def getDirectionName(self):
        return {0: "Left", 1: "Right", 2: "Up", 3: "Down"}.get(self.player.playerDirection)

    def lookingAt(self):
        tile = self.grid.get(self.PlayerLookPosition)
        if tile is None:
            return "Nothing"
        if tile[0] == 2:
            return tile[2].name
        return {0: "Floor", 3: "Chest", 4: "Door Down", 5: "Enemy", 6: "Door Up"}.get(tile[0], "Floor")

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
                            ("AC", player.damageReduction()), ("Gold", player.gold),
                            ("Facing", self.getDirectionName()), ("Wall Damage", player.getWallDamage()),
                            ("Damage", f"{minDamage} - {maxDamage}")]
        elif windowId == "room":
            spec["rows"] = [("Floor Type", self.proportion), ("Theme", self.theme.name),
                            ("Room Type", self.getRoomType(self.playerPositionFlat, self.rooms) or "-"),
                            ("Floor", self.level), ("Standing On", self.currentPosition), ("Looking At", self.lookingAt())]
            if self.pickerActive():
                spec["rows"].append(("Color Selected", self.selectedColor))
        elif windowId == "equipment":
            spec["rows"] = [(slot, getattr(item, "name", item)) for slot, item in player.equipment.items()]
        elif windowId == "levelup":
            spec["header"] = f"Gold {player.gold}     Next point costs {player.nextLevelGold}"
            spec["rows"] = [(name.title(), value) for name, value in player.attributes.items()]
        elif windowId == "items":
            spec["rows"] = [(f"Slot {i + 1}", item.name) for i, item in enumerate(self.roomItems or [])]
        elif windowId == "inventory":
            spec["kind"] = "grid"
            spec["items"] = [item.name for item in player.inventory]
            spec["capacity"] = player.inventoryLimit
        return spec

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
        return self.settings.lightStyle if self.menuOptions["Animated Light"] else None

    def pauseView(self):
        if self.pausePage is None:
            return None
        hotkeys = [(label, self.settings.nameFor(action)) for action, label, _ in HOTKEY_ACTIONS]
        hotkeys.append(("Reset to Defaults", ""))
        return {"page": self.pausePage, "level": self.level, "sel": self.pauseSel,
                "rows": [(kind, label, self.pauseRowValue(label)) for kind, label in PAUSE_ROWS],
                "hotkeys": hotkeys, "hotkeySel": self.hotkeySel, "perColumn": HOTKEYS_PER_COLUMN,
                "rebinding": self.rebinding, "message": self.hotkeyMessage, "fixed": FIXED_KEYS}

    def draw(self, lightOnly=False):
        if self.scene == "title":
            self.painter.drawTitle(self.titleOptions(), self.titleSel, self.titleMessage, self.titleFade)
            return
        if self.scene == "attempts":
            self.painter.drawAttempts(self.attemptList, self.attemptScroll)
            return

        messageKey, messageText = None, None
        messageTexts = {"escapeMessage": "Escape", "floorLevelMessage": f"Floor {self.level}",
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
            aimLine=self.aimLine, hud=hud,
            windows=[self.windowSpec(w) for w in self.windowDrawOrder], pause=self.pauseView(),
            message=messageText, fadeStep=FADE_STEPS.get(messageKey, 0),
            lightTime=self.lightStep / SWAY_FPS, lightStyle=self.lightStyle(), lightOnly=lightOnly)

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
