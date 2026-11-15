import math
import pygame
import pygame.ftfont
import themes
import sprites


# Dithered light: tiles in view get a pattern of dark pixels the further they are from the player.
# Each amount is the fraction of a tile's pixels darkened, used for the middle and outer part of the vision range.
DITHER_AMOUNTS = (0.125, 0.25)  # "Soft" from the Dithered Light page
# Sway: the light's center drifts slowly around the player, like a torch swinging in your hand.
SWAY_FPS = 10       # how many times a second the light moves (a stepped, retro feel)
SWAY_AMOUNT = 0.9   # how far the center can drift, in tiles (from -0.45 to +0.45)
SWAY_SPEED = 1.2    # how fast it drifts
# Flicker: the light's reach jumps in and out a little, like a flame in a draft.
FLICKER_AMOUNT = 0.28  # how much the reach changes (from -14% to +14%)
FLICKER_SPEED = 6      # how fast it changes

# A 4x4 ordered-dither (Bayer) pattern: a pixel is darkened when its number is below amount * 16
BAYER = [[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]]


class renderer():
    """Draws the game. Takes everything it needs as arguments and never changes game state."""

    WINDOW_HEAD = 46   # height of a window's title bar (also the part you drag)
    ROW = 30           # height of one row in a window
    PAD = 16           # inner padding of a window
    BOX_W, BOX_H = 118, 74  # one inventory slot

    def __init__(self, win):
        self.win = win
        self.screenWidth, self.screenHeight = self.win.get_size()
        self.overlay = pygame.Surface((self.screenWidth, self.screenHeight), pygame.SRCALPHA)

        self.tileSize = 0
        self.rowLength = 0
        self.columnLength = 0
        self.mapSurface = None
        self.mapOffset = (0, 0)
        self.shades = {}  # (amount index, x parity, y parity) -> transparent tile Surface with the dither pattern
        self.sprites = {}  # chest / door pictures in the current theme's colors (see sprites.py)
        self.pitCache = {}  # (pit style, floor color) -> pit picture, made the first time it's needed

        # The current floor's colors (a themes.Theme). Set by the game manager with setTheme().
        self.theme: themes.Theme = themes.randomTheme("Mixed")
        # Same list objects as theme.colors, so the color picker edits the live colors.
        self.colorDict = self.theme.colors

        pygame.font.init()
        pygame.ftfont.init()
        font = 'Forgore.otf'
        self.SplashScreenFont = pygame.ftfont.Font(font, 150)
        self.titleFont = pygame.ftfont.Font(font, int(self.screenHeight * 0.3))
        self.titleOptionFont = pygame.ftfont.Font(font, 40)
        self.titleHintFont = pygame.ftfont.Font(font, 20)
        self.windowTitleFont = pygame.ftfont.Font(font, 24)
        self.windowFont = pygame.ftfont.Font(font, 21)
        self.windowSmallFont = pygame.ftfont.Font(font, 16)
        self.hudFont = pygame.ftfont.Font(font, 20)

        # Field Journal menu. Its layout was designed in "k" units; k grows with the screen height.
        self.menuScale = self.screenHeight / 520
        k = self.menuScale
        self.menuTitleFont = pygame.ftfont.Font(font, int(46 * k))
        self.menuOptionFont = pygame.ftfont.Font(font, int(22 * k))
        self.menuValueFont = pygame.ftfont.Font(font, int(15 * k))
        self.menuHintFont = pygame.ftfont.Font(font, int(13 * k))

        self.fade = 255

    # ------------------------------------------------------------------ setup

    def setTheme(self, theme):
        self.theme = theme
        self.colorDict = theme.colors
        self.buildShades()

    def buildShades(self):
        """Pre-draws the dither tiles for this theme. The pattern is lined up to the whole map, and because
        a 10px tile isn't a multiple of the 4px pattern, odd and even columns/rows need their own copies."""
        if self.tileSize == 0:
            return
        ts = self.tileSize
        self.sprites = sprites.buildSprites(self.theme.colors, ts)
        self.pitCache = {}
        dark = themes.mix(self.theme.colors["fog"], [0, 0, 0], 0.1)
        self.shades = {}
        for index, amount in enumerate(DITHER_AMOUNTS):
            for xParity in (0, 1):
                for yParity in (0, 1):
                    surface = pygame.Surface((ts, ts), pygame.SRCALPHA)
                    for y in range(ts):
                        for x in range(ts):
                            if BAYER[(yParity * ts + y) % 4][(xParity * ts + x) % 4] < amount * 16:
                                surface.set_at((x, y), dark)
                    self.shades[(index, xParity, yParity)] = surface

    def pitSprite(self, style, floor):
        cacheKey = (style, tuple(floor))
        if cacheKey not in self.pitCache:
            self.pitCache[cacheKey] = sprites.makePit(style, floor, self.tileSize)
        return self.pitCache[cacheKey]

    @staticmethod
    def wiggle(seed, time):
        """A smooth random value between 0 and 1 that drifts over time (eased between random points)."""
        i = math.floor(time)
        f = time - i
        u = f * f * (3 - 2 * f)

        def point(n):
            s = math.sin((n + seed * 101.3) * 127.1) * 43758.5453
            return s - math.floor(s)
        return point(i) * (1 - u) + point(i + 1) * u

    def lightShape(self, lightTime, lightStyle):
        """Where the light's center is (offset from the player, in tiles) and how far it reaches
        (a multiplier on the vision range) at this moment. lightStyle: "sway", "flicker" or None (still)."""
        if lightStyle == "sway":
            t = lightTime * SWAY_SPEED
            return (self.wiggle(2, t) - 0.5) * SWAY_AMOUNT, (self.wiggle(3, t) - 0.5) * SWAY_AMOUNT, 1.0
        if lightStyle == "flicker":
            return 0.0, 0.0, 1 + (self.wiggle(1, lightTime * FLICKER_SPEED) - 0.5) * FLICKER_AMOUNT
        return 0.0, 0.0, 1.0

    def lightLevel(self, x, y, playerX, playerY, visionRange):
        """Which dither tile a visible tile gets: None (full light near the light's center), 0 or 1.
        playerX/playerY can be fractional because the light sways."""
        distance = math.hypot(x - playerX, y - playerY) / max(1, visionRange)
        if distance <= 0.45:
            return None
        return 0 if distance <= 0.8 else 1

    def color(self, key):
        """Looks up a color in the current floor's theme."""
        return self.theme.colors[key]

    def getCenterCartesian(self):
        return int(self.rowLength / 2), int(self.columnLength / 2)

    def setTileSize(self, tileSize) -> int:
        """The map fills the screen. Any leftover pixels (when the screen size isn't a multiple of the tile
        size) are split evenly around the map."""
        self.tileSize = tileSize
        self.rowLength = self.screenWidth // tileSize
        self.columnLength = self.screenHeight // tileSize
        mapW, mapH = self.rowLength * tileSize, self.columnLength * tileSize
        self.mapSurface = pygame.Surface((mapW, mapH))
        self.mapOffset = ((self.screenWidth - mapW) // 2, (self.screenHeight - mapH) // 2)
        self.buildShades()
        return tileSize

    def blitText(self, surface, message, font, color, x, centerY, align="left"):
        """Draws text vertically centered on centerY. align is "left", "right" (x is the right edge) or "center"."""
        text = font.render(str(message), True, color)
        rect = text.get_rect()
        if align == "right":
            rect.midright = (x, centerY)
        elif align == "center":
            rect.center = (x, centerY)
        else:
            rect.midleft = (x, centerY)
        surface.blit(text, rect)

    # ------------------------------------------------------------- top level

    def draw(self, grid, rooms, player, playerPosition, aimLine, hud, windows, pause, message=None, fadeStep=0,
             lightTime=0.0, lightStyle=None, lightOnly=False):
        """Draws one game frame.
        hud: (health, maxHealth, gold, floor) or None to hide it.
        windows: list of window dicts (see drawWindow), drawn in order so the last one is on top.
        pause: dict describing the pause menu, or None when it's closed.
        lightTime: seconds, for the animated light. lightStyle: "sway", "flicker" or None (not animated).
        lightOnly: only the light moved, so just redraw the lit tiles instead of the whole map.
        Returns (message finished fading?, {window id: pygame.Rect}) so the game manager can tell which
        window the mouse is over."""
        self.win.fill(self.color("fog"))
        self.lightTime = lightTime  # also drives the Unsealed's circling shards
        light = self.lightShape(lightTime, lightStyle)
        if lightOnly:
            self.redrawLitTiles(grid, rooms, player.playerDirection, playerPosition, player.visionRange, light)
        else:
            self.mapSurface.fill(self.color("fog"))
            self.renderScreen(grid, rooms, player.playerDirection, playerPosition, player.visionRange, light)
        self.drawAimline(aimLine)
        self.win.blit(self.mapSurface, self.mapOffset)

        if hud is not None:
            self.drawHud(*hud)

        rects = {}
        for spec in windows:
            w, h = self.windowSize(spec)
            x, y = spec["position"] if spec.get("position") else self.defaultWindowPosition(spec["id"], w, h)
            x = max(0, min(self.screenWidth - w, x))
            y = max(0, min(self.screenHeight - h, y))
            rects[spec["id"]] = pygame.Rect(x, y, w, h)
            self.drawWindow(spec, rects[spec["id"]])

        messageFinished = False
        if message is not None:
            self.win.blit(self.drawMessage(message), (0, 0))
            self.fade -= fadeStep
            if self.fade <= 0:
                self.fade = 255
                messageFinished = True

        if pause is not None:
            self.DrawMenu(pause)

        pygame.display.flip()
        return messageFinished, rects

    # ----------------------------------------------------------- title screen

    def drawTitle(self, options, selectedIndex, message="", fade=255):
        """fade (0-255) is how far "CRUEL" has faded in. It's drawn the same way as the splash messages
        (drawMessage), run in reverse: a black veil and the title text both go from invisible to full together.
        The menu only appears once the fade reaches 255, and the veil stays so nothing jumps when it does."""
        W, H = self.screenWidth, self.screenHeight
        font, muted, select, boxLine = self.color("font"), self.color("muted"), self.color("select"), self.color("boxLine")
        alpha = max(0, min(255, int(fade)))
        self.win.fill(self.color("fog"))
        self.overlay.fill((0, 0, 0, alpha))
        self.win.blit(self.overlay, (0, 0))

        titleY = int(H * 0.33)
        title = self.titleFont.render("CRUEL", True, font)
        title.set_alpha(alpha)
        self.win.blit(title, title.get_rect(center=(W // 2, titleY)))
        if fade < 255:
            pygame.display.flip()
            return
        titleWidth = self.titleFont.size("CRUEL")[0]
        ruleY = titleY + self.titleFont.get_height() // 2 + 6
        pygame.draw.rect(self.win, boxLine, pygame.Rect(W // 2 - titleWidth // 2, ruleY, titleWidth, 2))
        if message:
            self.blitText(self.win, message, self.titleHintFont, self.color("enemy"), W // 2, ruleY + 34, align="center")

        startY = int(H * 0.62)
        for index, option in enumerate(options):
            y = startY + index * 58
            selected = index == selectedIndex
            label = f">  {option}  <" if selected else option
            self.blitText(self.win, label, self.titleOptionFont, select if selected else font, W // 2, y, align="center")

        self.blitText(self.win, "Up/Down  choose      Enter  select", self.titleHintFont, muted, W // 2, H - 40, align="center")
        pygame.display.flip()

    # ---------------------------------------------------------- attempts list

    ATTEMPT_ROW = 40

    def attemptRowsThatFit(self):
        return max(1, (self.screenHeight - 300) // self.ATTEMPT_ROW)

    def drawAttempts(self, attemptList, scroll):
        """Every past run, deepest first. attemptList is already sorted; scroll is the first row shown."""
        W, H = self.screenWidth, self.screenHeight
        font, muted, select, boxLine, panel = (self.color(c) for c in ("font", "muted", "select", "boxLine", "panel"))
        self.win.fill(self.color("fog"))

        self.blitText(self.win, "Attempts", self.titleOptionFont, font, W // 2, 70, align="center")
        self.blitText(self.win, "Deepest floor first", self.titleHintFont, muted, W // 2, 108, align="center")

        tableW = min(W - 32, 760)
        x0 = (W - tableW) // 2
        top = 150
        shown = attemptList[scroll:scroll + self.attemptRowsThatFit()]
        rect = pygame.Rect(x0, top, tableW, 56 + max(1, len(shown)) * self.ATTEMPT_ROW + 14)
        pygame.draw.rect(self.win, panel, rect)
        pygame.draw.rect(self.win, boxLine, rect, width=2)

        # column right edges / left edges as fractions of the table width
        columns = [("Rank", 0.04, "left"), ("Attempt", 0.30, "right"), ("Deepest Floor", 0.62, "right"),
                   ("Gold", 0.78, "right"), ("Date", 0.96, "right")]
        headerY = top + 28
        for title, fx, align in columns:
            self.blitText(self.win, title, self.windowSmallFont, muted, x0 + int(tableW * fx), headerY, align=align)
        pygame.draw.rect(self.win, boxLine, pygame.Rect(x0 + 16, top + 50, tableW - 32, 1))

        if not shown:
            self.blitText(self.win, "No attempts yet. They're recorded when a run ends in death.",
                          self.windowFont, muted, W // 2, top + 56 + self.ATTEMPT_ROW // 2, align="center")
        for i, attempt in enumerate(shown):
            rank = scroll + i + 1
            y = top + 56 + i * self.ATTEMPT_ROW + self.ATTEMPT_ROW // 2
            color = select if rank == 1 else font
            values = [f"{rank}.", f"#{attempt['number']}", f"Floor {attempt['deepest']}", attempt.get("gold", 0), attempt.get("date", "")]
            for (title, fx, align), value in zip(columns, values):
                self.blitText(self.win, value, self.windowFont, color, x0 + int(tableW * fx), y, align=align)

        if len(attemptList) > len(shown):
            self.blitText(self.win, f"Showing {scroll + 1}-{scroll + len(shown)} of {len(attemptList)}",
                          self.titleHintFont, muted, W // 2, rect.bottom + 24, align="center")
        hint = "Up/Down  scroll      Esc  back" if len(attemptList) > len(shown) else "Esc  back"
        self.blitText(self.win, hint, self.titleHintFont, muted, W // 2, H - 40, align="center")
        pygame.display.flip()

    # -------------------------------------------------------------------- hud

    def drawHud(self, health, maxHealth, gold, floor):
        parts = [f"HP {health}/{maxHealth}", f"Gold {gold}", f"Floor {floor}"]
        gap = 26
        widths = [self.hudFont.size(p)[0] for p in parts]
        w = self.PAD * 2 + sum(widths) + gap * (len(parts) - 1)
        rect = pygame.Rect(16, 16, w, 38)
        pygame.draw.rect(self.win, self.color("panel"), rect)
        pygame.draw.rect(self.win, self.color("boxLine"), rect, width=2)
        x = rect.x + self.PAD
        lowHealth = maxHealth > 0 and health / maxHealth < 0.4
        for i, part in enumerate(parts):
            color = self.color("enemy") if i == 0 and lowHealth else self.color("font")
            self.blitText(self.win, part, self.hudFont, color, x, rect.centery)
            x += widths[i] + gap

    # ---------------------------------------------------------------- windows

    def windowSize(self, spec):
        if spec["kind"] == "grid":
            rows = math.ceil(spec["capacity"] / 5)
            return self.PAD * 2 + 5 * self.BOX_W, self.WINDOW_HEAD + rows * self.BOX_H + 18
        widest = self.windowTitleFont.size(spec["title"])[0] + 70
        for label, value in spec["rows"]:
            widest = max(widest, self.windowFont.size(f"> {label}")[0] + self.windowFont.size(str(value))[0] + 40)
        if spec.get("header"):
            widest = max(widest, self.windowSmallFont.size(spec["header"])[0] + 20)
        count = len(spec["rows"]) + (1 if spec.get("header") else 0)
        return max(300, widest + self.PAD * 2), self.WINDOW_HEAD + max(1, count) * self.ROW + 14

    def defaultWindowPosition(self, windowId, w, h):
        """Where each window docks until the player drags it somewhere else."""
        W, H = self.screenWidth, self.screenHeight
        top, gap = 70, 12
        characterHeight = self.WINDOW_HEAD + 6 * self.ROW + 14
        equipmentHeight = self.WINDOW_HEAD + 8 * self.ROW + 14
        inventoryWidth = self.PAD * 2 + 5 * self.BOX_W
        match windowId:
            case "character":
                return 16, top
            case "room":
                return 16, top + characterHeight + gap
            case "equipment":
                return W - 16 - w, top
            case "levelup":
                return W - 16 - w, top + equipmentHeight + gap
            case "inventory":
                return (W - w) // 2, H - 16 - h
            case "items":
                return (W - inventoryWidth) // 2 + inventoryWidth + gap, H - 16 - h
        return (W - w) // 2, (H - h) // 2

    def drawWindow(self, spec, rect):
        """spec keys: id, title, hotkey (key name for the badge), focused, kind ("rows" or "grid"),
        rows [(label, value)], header (optional line above the rows), selectable, selected (index),
        items + capacity (for the grid)."""
        win = self.win
        focused = spec["focused"]
        panel, font, muted, select, boxLine = (self.color(c) for c in ("panel", "font", "muted", "select", "boxLine"))
        body = font if focused else themes.mix(font, panel, 0.22)
        highlight = themes.mix(panel, select, 0.14)

        pygame.draw.rect(win, panel, rect)
        pygame.draw.rect(win, select if focused else boxLine, rect, width=2)
        if focused:
            pygame.draw.rect(win, select, pygame.Rect(rect.x, rect.y, 4, self.WINDOW_HEAD))
        self.blitText(win, spec["title"], self.windowTitleFont, select if focused else font, rect.x + self.PAD + 2, rect.y + 24)
        self.blitText(win, f"[{spec['hotkey']}]", self.windowSmallFont, select if focused else muted, rect.right - self.PAD, rect.y + 24, align="right")
        pygame.draw.rect(win, boxLine, pygame.Rect(rect.x + self.PAD, rect.y + self.WINDOW_HEAD - 4, rect.w - self.PAD * 2, 1))

        if spec["kind"] == "grid":
            gx, gy = rect.x + self.PAD, rect.y + self.WINDOW_HEAD + 4
            for i in range(spec["capacity"]):
                box = pygame.Rect(gx + (i % 5) * self.BOX_W + 3, gy + (i // 5) * self.BOX_H + 3, self.BOX_W - 6, self.BOX_H - 6)
                selected = focused and i == spec["selected"]
                if selected:
                    pygame.draw.rect(win, highlight, box)
                pygame.draw.rect(win, select if selected else boxLine, box, width=2 if selected else 1)
                if i < len(spec["items"]):
                    self.blitText(win, spec["items"][i], self.windowSmallFont, select if selected else body, box.x + 8, box.bottom - 16)
            return

        y = rect.y + self.WINDOW_HEAD + self.ROW // 2 + 2
        if spec.get("header"):
            self.blitText(win, spec["header"], self.windowSmallFont, muted, rect.x + self.PAD + 2, y)
            y += self.ROW
        if not spec["rows"]:
            self.blitText(win, "Empty", self.windowFont, muted, rect.x + self.PAD + 2, y)
        for i, (label, value) in enumerate(spec["rows"]):
            rowY = y + i * self.ROW
            selected = spec.get("selectable") and focused and i == spec["selected"]
            if selected:
                pygame.draw.rect(win, highlight, pygame.Rect(rect.x + 2, rowY - self.ROW // 2, rect.w - 4, self.ROW))
            color = select if selected else body
            self.blitText(win, ("> " if selected else "") + str(label), self.windowFont, color, rect.x + self.PAD + 2, rowY)
            self.blitText(win, value, self.windowFont, muted if value == "None" else color, rect.right - self.PAD, rowY, align="right")

    # ------------------------------------------------------------ pause menu

    def DrawMenu(self, pause):
        """Field Journal: a full-height panel down the left with the options, plus the Hotkeys page beside it."""
        k = self.menuScale
        win = self.win
        W, H = self.screenWidth, self.screenHeight
        panelWidth = int(236 * k)
        pad = int(22 * k)
        panel, font, muted, select, boxLine = (self.color(c) for c in ("panel", "font", "muted", "select", "boxLine"))

        # Dim everything to the right of the panel
        self.overlay.fill((0, 0, 0, 0))
        pygame.draw.rect(self.overlay, (*self.color("fog"), 107), pygame.Rect(panelWidth, 0, W - panelWidth, H))
        win.blit(self.overlay, (0, 0))

        pygame.draw.rect(win, panel, pygame.Rect(0, 0, panelWidth, H))
        pygame.draw.rect(win, font, pygame.Rect(0, 0, panelWidth, H), width=2)

        self.blitText(win, "Menu", self.menuTitleFont, font, pad, int(42 * k))
        self.blitText(win, f"Floor {pause['level']}  -  {self.theme.name}", self.menuHintFont, muted, int(24 * k), int(76 * k))
        pygame.draw.rect(win, boxLine, pygame.Rect(pad, int(94 * k), panelWidth - pad * 2, 1))

        onJournal = pause["page"] == "journal"
        for index, (kind, label, value) in enumerate(pause["rows"]):
            y = int((124 + index * 40) * k)
            selected = index == pause["sel"]
            active = selected and (onJournal or label == "Hotkeys")
            if active:
                self.blitText(win, ">", self.menuOptionFont, select, pad, y)
            self.blitText(win, label, self.menuOptionFont, select if active else font, int(40 * k), y)
            if kind == "toggle":
                color = (select if active else font) if value else muted
                self.blitText(win, "ON" if value else "OFF", self.menuValueFont, color, panelWidth - pad, y, align="right")
            elif kind == "page":
                self.blitText(win, ">>", self.menuValueFont, select if active else muted, panelWidth - pad, y, align="right")
            elif kind == "choice":
                self.blitText(win, value, self.menuValueFont, select if active else font, panelWidth - pad, y, align="right")

        pygame.draw.rect(win, boxLine, pygame.Rect(pad, H - int(58 * k), panelWidth - pad * 2, 1))
        self.blitText(win, "Up/Down  choose", self.menuHintFont, muted, int(24 * k), H - int(40 * k))
        self.blitText(win, "Enter  select     Esc  " + ("close" if onJournal else "back"), self.menuHintFont, muted, int(24 * k), H - int(22 * k))

        if pause["page"] == "hotkeys":
            self.drawHotkeyPage(pause, panelWidth + int(14 * k), int(20 * k))

    def drawHotkeyPage(self, pause, x0, y0):
        k = self.menuScale
        win = self.win
        panel, font, muted, select, boxLine = (self.color(c) for c in ("panel", "font", "muted", "select", "boxLine"))
        w, h = int(430 * k), int(446 * k)
        pad = int(18 * k)
        rect = pygame.Rect(x0, y0, w, h)
        pygame.draw.rect(win, panel, rect)
        pygame.draw.rect(win, font, rect, width=2)

        self.blitText(win, "Hotkeys", self.menuOptionFont, font, x0 + pad, y0 + int(30 * k))
        hint = "Press a key to bind it.   Esc  cancel" if pause["rebinding"] else "Enter  change key      Esc  back"
        self.blitText(win, hint, self.menuHintFont, muted, x0 + pad, y0 + int(56 * k))
        pygame.draw.rect(win, boxLine, pygame.Rect(x0 + pad, y0 + int(72 * k), w - pad * 2, 1))

        perColumn = pause["perColumn"]
        colW = (w - pad * 3) // 2
        highlight = themes.mix(panel, select, 0.16)
        rowH = int(30 * k)
        for index, (label, keyName) in enumerate(pause["hotkeys"]):
            col, row = divmod(index, perColumn)
            cx = x0 + pad + col * (colW + pad)
            cy = y0 + int(96 * k) + row * rowH
            selected = index == pause["hotkeySel"]
            if selected:
                pygame.draw.rect(win, highlight, pygame.Rect(cx - 6, cy - rowH // 2 + 2, colW + 12, rowH - 4))
            color = select if selected else font
            self.blitText(win, label, self.menuValueFont, color, cx, cy)
            if selected and pause["rebinding"]:
                keyName = "Press a key..."
            self.blitText(win, keyName, self.menuValueFont, color if keyName else muted, cx + colW, cy, align="right")

        pygame.draw.rect(win, boxLine, pygame.Rect(x0 + pad, y0 + int(330 * k), w - pad * 2, 1))
        if pause["message"]:
            self.blitText(win, pause["message"], self.menuHintFont, select, x0 + pad, y0 + int(350 * k))
        self.blitText(win, "Fixed keys", self.menuHintFont, muted, x0 + pad, y0 + int(378 * k))
        for i, (keyName, label) in enumerate(pause["fixed"]):
            col, row = i % 2, i // 2
            cx = x0 + pad + col * (colW + pad)
            cy = y0 + int((402 + row * 22) * k)
            self.blitText(win, f"{keyName}  -  {label}", self.menuHintFont, font, cx, cy)

    def drawMessage(self, message):
        text = self.SplashScreenFont.render(message, True, self.color("font"))
        alpha = max(0, int(self.fade))
        canvas = pygame.Surface((self.screenWidth, self.screenHeight), pygame.SRCALPHA)
        canvas.fill((0, 0, 0, alpha))
        text.set_alpha(alpha)
        canvas.blit(text, (self.screenWidth // 2 - text.get_width() // 2, self.screenHeight // 2 - text.get_height() // 2))
        return canvas

    # ------------------------------------------------------------------ tiles

    def drawWall(self, wall, color) -> pygame.Surface:
        canvas = pygame.Surface((self.tileSize, self.tileSize))
        canvas.fill(color)
        brokenColor = [max(0, c - 100) for c in color]
        for point in wall.brokenPoints:
            pygame.draw.rect(canvas, brokenColor, pygame.Rect(point[0], point[1], 1, 1))
        pygame.draw.rect(canvas, brokenColor, pygame.Rect(0, 0, self.tileSize, self.tileSize), width=2)
        return canvas

    def drawAimline(self, aimLine):
        if aimLine is None:
            return
        for i in aimLine:
            self.fillTile(self.color("aim"), i % self.rowLength, i // self.rowLength)

    def fillTile(self, color, x, y):
        pygame.draw.rect(self.mapSurface, color, pygame.Rect(x * self.tileSize, y * self.tileSize, self.tileSize, self.tileSize))

    def floorColor(self, i, rooms, memorized):
        prefix = "memFloor" if memorized else "floor"
        for room in ("Stone", "Wood", "Gold"):
            if i in rooms[room]:
                return self.color(prefix + room)
        return self.color(prefix + "Sand")

    def wallColor(self, name, memorized):
        # wall names are "Stone Wall", "Wood Wall", "Sand Wall", "Gold Wall"
        room = name.split(" ")[0]
        prefix = "memWall" if memorized else "wall"
        return self.theme.colors.get(prefix + room, self.color(prefix + "Stone"))

    def renderScreen(self, grid: dict, rooms, playerDirection, playerPosition, visionRange, light=(0, 0, 1)):
        self.litTiles = []  # tiles in view, remembered so the swaying light can redraw just these
        for i in grid.keys():
            visibility = grid[i][1]
            if visibility == 0:
                continue
            if visibility == 1:
                self.litTiles.append(i)
            self.drawLitTile(grid, i, rooms, playerDirection, playerPosition, visionRange, light)

    def redrawLitTiles(self, grid, rooms, playerDirection, playerPosition, visionRange, light):
        """Only the light moved: redraw the tiles in view (from the last full draw) with the new light."""
        for i in getattr(self, "litTiles", []):
            if grid[i][1] == 1:
                self.drawLitTile(grid, i, rooms, playerDirection, playerPosition, visionRange, light)

    def drawLitTile(self, grid, i, rooms, playerDirection, playerPosition, visionRange, light):
        ts = self.tileSize
        memorized = grid[i][1] == 2
        x = i % self.rowLength
        y = i // self.rowLength
        self.drawTile(grid, i, x, y, rooms, playerDirection, memorized)
        # Dithered light only on tiles in view (remembered tiles stay as they are). The player, enemies,
        # chests and the door back up are never dithered so they stand out; pits are part of the floor, so they are.
        if not memorized and grid[i][0] not in (1, 3, 5, 6):
            offsetX, offsetY, reach = light
            lightX = playerPosition % self.rowLength + offsetX
            lightY = playerPosition // self.rowLength + offsetY
            level = self.lightLevel(x, y, lightX, lightY, visionRange * reach)
            if level is not None and self.shades:
                self.mapSurface.blit(self.shades[(level, x % 2, y % 2)], (x * ts, y * ts))

    def drawTile(self, grid, i, x, y, rooms, playerDirection, memorized):
        ts = self.tileSize
        match grid[i][0]:
            case 1:  # Player: the Torchbearer facing the way it last moved, on the floor it stands on
                self.fillTile(self.floorColor(i, rooms, memorized), x, y)
                self.mapSurface.blit(self.sprites["player"][playerDirection], (x * ts, y * ts))
            case 2:  # Wall
                w = grid[i][2]
                self.mapSurface.blit(self.drawWall(w, self.wallColor(w.name, memorized)), (x * ts, y * ts))
            # Chests and doors: the floor first (it shows through the pictures' transparent pixels and
            # shadows), then the picture. They keep their full color even when remembered.
            case 3:  # Chest: walnut, mahogany or burnt umber (the same on every floor)
                self.fillTile(self.floorColor(i, rooms, memorized), x, y)
                self.mapSurface.blit(self.sprites["chests"][sprites.chestColorFor(i)], (x * ts, y * ts))
            case 4:  # Door to the next level: a pit in the floor, randomly an open pit or a collapsed grave
                floor = self.floorColor(i, rooms, memorized)
                self.fillTile(floor, x, y)
                self.mapSurface.blit(self.pitSprite(sprites.pitStyleFor(i), floor), (x * ts, y * ts))
            case 6:  # Door back to the previous level
                self.fillTile(self.floorColor(i, rooms, memorized), x, y)
                self.mapSurface.blit(self.sprites["doorUp"], (x * ts, y * ts))
            case 5 if not memorized:  # Enemy (enemies are not remembered)
                self.fillTile(self.floorColor(i, rooms, memorized), x, y)
                name = grid[i][2].name if len(grid[i]) > 2 else ""
                if name == "Unsealed":
                    frame = sprites.shardFrameFor(getattr(self, "lightTime", 0.0))
                    self.mapSurface.blit(self.sprites["unsealed"][frame], (x * ts, y * ts))
                elif name in self.sprites["enemies"]:
                    self.mapSurface.blit(self.sprites["enemies"][name], (x * ts, y * ts))
                else:  # an enemy with no picture yet: a plain square
                    self.fillTile(self.color("enemy"), x, y)
            case _:  # Floor
                self.fillTile(self.floorColor(i, rooms, memorized), x, y)
