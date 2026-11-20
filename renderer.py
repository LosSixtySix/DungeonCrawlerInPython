import math
import random
import pygame
import pygame.ftfont
import paths
import themes
import sprites
import wall as walls
import expansion
import plants


# Dithered light: tiles in view get a pattern of dark pixels the further they are from the player.
# Each amount is the fraction of a tile's pixels darkened, used for the middle and outer part of the vision range.
DITHER_AMOUNTS = (0.125, 0.25)  # "Soft" from the Dithered Light page
# Sway: the light's center drifts slowly around the player, like a torch swinging in your hand.
SWAY_FPS = 10       # how many times a second the light moves (a stepped, retro feel)
SWAY_AMOUNT = 0.9   # how far the center can drift, in tiles (from -0.45 to +0.45)
SWAY_SPEED = 1.2    # how fast it drifts

# Firelight: each fire lights the tiles around it (gameManager.setPositionsVisible works out which ones you can
# see). They're drawn bright with a warm tint that fades with distance, and the light sways like yours does.
FIRE_LIGHT_RADIUS = 3
SMOKE_THIN_TURNS = 4          # Smoke Bomb smoke fades out over its last this many turns
FIRE_TINT = (240, 128, 40)
FIRE_TINT_ALPHA = 82          # the tint's strength on the fire's own tile (0-255); it fades to nothing at the edge

# Corrupted walls (Overgrowth): vines creeping over the top of the wall, in the corrupting plant's colors.
# c = its main color, C = its light color, s = its dark color (its main color if it has none).
VINES = [
    "..........",
    ".c.....C..",
    "..c...c...",
    "...cCc....",
    "....c...s.",
    "...c.c.c..",
    "..C...c...",
    ".c...c.C..",
    "..s.c.....",
    "..........",
]

# Ore glints ("Twinkle"): every vein tile in your light twinkles on its own timer. Three of its flecks flash
# one after another, and the first throws a tiny four-point star onto the wall around it.
GLINT_FPS = 30                # how often a twinkling tile is redrawn
GLINT_PERIOD = (3000, 7000)   # ms between one tile's twinkles (random per tile, so a wall of ore shimmers)
GLINT_LENGTH = 560            # ms one twinkle lasts
GLINT_STAGGER = 130           # ms between the three flecks
GLINT_FLASH = 240             # ms each fleck's flash takes to fade
GLINT_WHITE = (255, 255, 255)
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
    INV_DETAIL_W = 250      # the inventory's details panel, right of the slots

    def __init__(self, win):
        self.win = win
        self.screenWidth, self.screenHeight = self.win.get_size()
        self.overlay = pygame.Surface((self.screenWidth, self.screenHeight), pygame.SRCALPHA)

        self.tileSize = 0
        self.blood = {}  # set every frame by draw()
        self.bloodDry = {}
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
        font = paths.resourcePath('Forgore.otf')
        self.SplashScreenFont = pygame.ftfont.Font(font, 150)
        self.titleFont = pygame.ftfont.Font(font, int(self.screenHeight * 0.3))
        self.titleOptionFont = pygame.ftfont.Font(font, 40)
        self.titleHintFont = pygame.ftfont.Font(font, 20)
        self.windowTitleFont = pygame.ftfont.Font(font, 24)
        self.windowFont = pygame.ftfont.Font(font, 21)
        self.windowSmallFont = pygame.ftfont.Font(font, 16)
        self.hudFont = pygame.ftfont.Font(font, 20)
        self.popupFont = pygame.ftfont.Font(font, 18)
        self.consoleFont = pygame.font.SysFont("consolas,couriernew,dejavusansmono,monospace", 16)  # lines up the columns

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
        self.clearTileCaches()  # a new theme (and every new or revisited floor sets one): the cached pictures are stale
        self.drawnGrid = None    # ...and so is everything on the map: the next frame redraws every tile
        self.buildShades()

    # Pictures that cost a lot to draw and rarely change are kept between frames: walls (until they're chipped or
    # the floor changes) and blood (by its look). Twinkling ore isn't cached. Cleared with every theme/floor change.
    TILE_CACHE_LIMIT = 6000

    def clearTileCaches(self):
        self.wallCache, self.bloodCache = {}, {}

    def cached(self, cache, key, make):
        if key not in cache:
            if len(cache) > self.TILE_CACHE_LIMIT:
                cache.clear()
            cache[key] = make()
        return cache[key]

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
        self.drawnGrid = None  # a new map surface: the next frame redraws every tile
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
             lightTime=0.0, lightStyle=None, lightOnly=False, popups=(), throws=None, blood=None,bloodDry = None, openOrder=(),
             console=None, glintOnly=False, fireLight=None, smoke=None, overlayOnly=False):
        """Draws one game frame.
        hud: (health, maxHealth, gold, floor) or None to hide it.
        windows: list of window dicts (see drawWindow), drawn in order so the last one is on top.
        pause: dict describing the pause menu, or None when it's closed.
        lightTime: seconds, for the animated light. lightStyle: "sway", "flicker" or None (not animated).
        lightOnly: only the light moved, so just redraw the lit tiles instead of the whole map.
        glintOnly: only ore glints changed, so just redraw the twinkling vein tiles (see glintsDue).
        overlayOnly: nothing on the map changed (only popups, messages, flames and the like), so the map is kept
        and only its animated tiles (bonfires, the Unsealed) are brought up to date.
        Whichever it is, a tile is only redrawn when its look changed since it was last drawn (see tileSignature).
        fireLight: {tile: (the fire lighting it, its light radius)} for tiles in reach of a fire's or bonfire's light.
        Returns (message finished fading?, {window id: pygame.Rect}) so the game manager can tell which
        window the mouse is over."""
        self.win.fill(self.color("fog"))
        self.frameTicks = pygame.time.get_ticks()  # one clock reading for the whole frame (glints, bonfire flames)
        self.blood = blood or {}  # map position -> how much blood is on that floor tile (0-1)
        self.bloodDry = bloodDry or {}
        self.lightTime = lightTime  # also drives the Unsealed's circling shards
        self.lightStyleNow = lightStyle  # fires sway the same way (see fireLevel)
        self.fireLight = fireLight or {}
        self.smokeHere = smoke or {}  # Smoke Bomb smoke: whoever stands in it isn't drawn
        light = self.lightShape(lightTime, lightStyle)
        if getattr(self, "drawnGrid", None) is not grid:  # a different floor (or the first frame): start over
            self.resetMap()
            self.drawnGrid = grid
            glintOnly = lightOnly = overlayOnly = False
        oldAim = getattr(self, "aimDrawn", set())
        for t in oldAim:  # the aim line is painted on the map: the tiles it covered get redrawn
            self.tileSigs.pop(t, None)
        args = (grid, rooms, player.playerDirection, playerPosition, player.getVisionRange(), light)
        if lightOnly:
            self.redrawLitTiles(*args)  # (every tile in view: that covers the animated ones too)
        elif glintOnly or overlayOnly:  # time moves on: twinkling ore, bonfire flames and the Unsealed keep moving
            for i in set(getattr(self, "animatedTiles", ())) | set(getattr(self, "litVeins", ())):
                self.refreshTile(*args[:1], i, *args[1:])
        else:
            self.renderScreen(*args)
        for t in oldAim:  # put back what the last aim line covered (whatever kind of frame this is)
            if t in grid:
                if grid[t][1] == 0:
                    self.fillTile(self.color("fog"), t % self.rowLength, t // self.rowLength)
                else:
                    self.refreshTile(*args[:1], t, *args[1:])
        self.drawAimline(aimLine)
        self.aimDrawn = set(aimLine or ())
        self.win.blit(self.mapSurface, self.mapOffset)
        if throws is not None:
            self.drawThrows(throws)

        self.drawPopups(popups)
        if hud is not None:
            self.drawHud(*hud)

        rects = self.layoutWindows(windows, openOrder, playerPosition)
        for spec in windows:
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
        if console is not None:
            self.drawConsole(console)

        pygame.display.flip()
        return messageFinished, rects

    # -------------------------------------------------------- developer console
    # Its own fixed colors (not the floor's theme), so it reads the same on every floor.
    CONSOLE_COLORS = {"input": (236, 236, 236), "info": (188, 194, 204), "good": (130, 210, 120),
                      "error": (236, 104, 96), "head": (232, 192, 96)}

    def drawConsole(self, console):
        """A dark panel over the top of the screen: the log, newest at the bottom, and the line being typed."""
        W, H = self.screenWidth, int(self.screenHeight * 0.45)
        font, colors = self.consoleFont, self.CONSOLE_COLORS
        lineH = font.get_linesize() + 2
        self.overlay.fill((0, 0, 0, 0))
        self.overlay.fill((12, 12, 16, 232), pygame.Rect(0, 0, W, H))
        self.win.blit(self.overlay, (0, 0))
        pygame.draw.line(self.win, colors["head"], (0, H), (W, H), 2)

        inputY = H - lineH - 8
        pygame.draw.line(self.win, (60, 62, 70), (0, inputY - 6), (W, inputY - 6), 1)
        typed = font.render("> " + console["text"], True, colors["input"])
        self.win.blit(typed, (12, inputY))
        x = 12 + typed.get_width()
        pygame.draw.line(self.win, colors["input"], (x + 1, inputY + 1), (x + 1, inputY + font.get_height() - 2), 2)  # caret
        if console["ghost"]:  # the rest of the best match, in grey: Tab fills it in
            ghost = font.render(console["ghost"], True, (110, 114, 124))
            self.win.blit(ghost, (x + 3, inputY))
            x += ghost.get_width()
        if console["others"]:  # the other matches, so you can see what Tab would step through
            shown = console["others"][:8]
            more = len(console["others"]) - len(shown)
            listed = "   Tab: " + "  ".join(shown) + (f"  +{more} more" if more else "")
            self.win.blit(font.render(listed, True, (84, 88, 98)), (x + 3, inputY))

        log = console["log"]
        rows = max(1, (inputY - 18) // lineH)
        end = len(log) - console["scroll"]
        start = max(0, end - rows)
        y = inputY - 10 - (end - start) * lineH
        for style, text in log[start:end]:
            self.win.blit(font.render(text, True, colors.get(style, colors["info"])), (12, y))
            y += lineH
        noteY = 8
        if console["peaceful"]:
            tag = font.render("PEACEFUL", True, colors["good"])
            self.win.blit(tag, (W - tag.get_width() - 12, noteY))
            noteY += lineH
        if console["scroll"]:
            note = font.render(f"scrolled up {console['scroll']} lines (PgDn)", True, colors["head"])
            self.win.blit(note, (W - note.get_width() - 12, noteY))

    # ----------------------------------------------------------- title screen

    def drawTitle(self, options, selectedIndex, message="", fade=255, heading="", hint="Up/Down  choose      Enter  select", note=""):
        """fade (0-255) is how far "CRUEL" has faded in. It's drawn the same way as the splash messages
        (drawMessage), run in reverse: a black veil and the title text both go from invisible to full together.
        The menu only appears once the fade reaches 255, and the veil stays so nothing jumps when it does.
        heading names the page under the title (e.g. "Settings"); note is a muted line above the hint."""
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
        if heading:
            self.blitText(self.win, heading.upper(), self.titleHintFont, font, W // 2, ruleY + 28, align="center")
        if message:
            self.blitText(self.win, message, self.titleHintFont, self.color("enemy"), W // 2, ruleY + (56 if heading else 34), align="center")

        startY = max(int(H * 0.62), ruleY + 100) if heading else int(H * 0.62)  # leave room for the heading and message
        bottom = H - 90 - (32 if note else 0)
        spacing = min(58, (bottom - startY) // max(1, len(options) - 1))  # squeeze together on short screens
        for index, option in enumerate(options):
            y = startY + index * spacing
            selected = index == selectedIndex
            label = f">  {option}  <" if selected else option
            self.blitText(self.win, label, self.titleOptionFont, select if selected else font, W // 2, y, align="center")

        if note:
            self.blitText(self.win, note, self.titleHintFont, muted, W // 2, H - 72, align="center")
        self.blitText(self.win, hint, self.titleHintFont, muted, W // 2, H - 40, align="center")
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

    def drawPopups(self, popups):
        """Rising "+2 Wood" texts over the map: each floats up from its tile and fades out (age goes 0 to 1)."""
        for text, position, age in popups:
            x = self.mapOffset[0] + (position % self.rowLength) * self.tileSize + self.tileSize // 2
            y = self.mapOffset[1] + (position // self.rowLength) * self.tileSize - int(age * 26) - 4
            alpha = int(255 * (1 - age))
            shadow = self.popupFont.render(text, True, (0, 0, 0))
            label = self.popupFont.render(text, True, self.color("select"))
            shadow.set_alpha(alpha // 2)
            label.set_alpha(alpha)
            rect = label.get_rect(midbottom=(x, y))
            self.win.blit(shadow, rect.move(1, 1))
            self.win.blit(label, rect)

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
        if spec["kind"] == "craft":
            return self.CRAFT_W, self.WINDOW_HEAD + self.ROW + 4 + self.craftAreaHeight(spec) + self.ROW + 10
        if spec["kind"] == "sections":
            widest = self.windowTitleFont.size(spec["title"])[0] + 70
            count = 1 if spec.get("tabs") else 0
            if spec.get("tabs"):
                widest = max(widest, sum(self.windowSmallFont.size(t)[0] + 28 for t in spec["tabs"]))
            for section in spec["sections"]:
                if section.get("title"):
                    count += 1
                    widest = max(widest, self.windowFont.size(section["title"])[0] + 10)
                if section.get("note"):
                    count += 1
                    widest = max(widest, self.windowSmallFont.size(section["note"])[0] + 10)
                for label, value, color in section["rows"]:
                    count += 1
                    widest = max(widest, 22 + self.windowFont.size(str(label))[0] + self.windowFont.size(str(value))[0] + 40)
            return max(300, widest + self.PAD * 2), self.WINDOW_HEAD + max(1, count) * self.ROW + 14
        if spec["kind"] == "grid":
            rows = math.ceil(spec["capacity"] / 5)
            return self.PAD * 2 + 5 * self.BOX_W + self.INV_DETAIL_W, self.WINDOW_HEAD + rows * self.BOX_H + 18
        widest = self.windowTitleFont.size(spec["title"])[0] + 70
        for label, value in spec["rows"]:
            widest = max(widest, self.windowFont.size(f"> {label}")[0] + self.windowFont.size(str(value))[0] + 40)
        if spec.get("header"):
            widest = max(widest, self.windowSmallFont.size(spec["header"])[0] + 20)
        count = len(spec["rows"]) + (1 if spec.get("header") else 0)
        height = self.WINDOW_HEAD + max(1, count) * self.ROW + 14
        if spec.get("id") == "equipment":
            self.equipmentHeight = height  # Level Up docks right under it, so it moves down when a swap adds a line
        return max(300, widest + self.PAD * 2), height

    LAYOUT_STEP = 16     # how finely the screen is searched for a free spot for a window
    LAYOUT_GAP = 8       # space kept between windows
    LAYOUT_SHIFT = 48    # when two windows must overlap, they're offset at least this much from each other

    def layoutWindows(self, windows, openOrder, playerPosition):
        """Where every open window goes. Windows you dragged stay where you put them. Any other window gets
        its spot when it opens and keeps it while it's open: its usual spot if that's free, otherwise the
        nearest spot that doesn't overlap a window already on screen (staying off you if it can). If there's
        nowhere free, it goes where it overlaps least, shifted so it never sits squarely on top of another."""
        sizes = {}
        for spec in windows:  # size Equipment first: Level Up docks under it
            if spec["id"] == "equipment":
                sizes["equipment"] = self.windowSize(spec)
        for spec in windows:
            sizes[spec["id"]] = sizes.get(spec["id"]) or self.windowSize(spec)
        W, H = self.screenWidth, self.screenHeight
        self.autoPlaced = {k: v for k, v in getattr(self, "autoPlaced", {}).items() if k in sizes}  # forget closed ones
        rects = {}

        def clamp(x, y, w, h):
            return pygame.Rect(max(0, min(W - w, x)), max(0, min(H - h, y)), w, h)

        for spec in windows:  # windows that already have a spot
            w, h = sizes[spec["id"]]
            if spec.get("position"):
                self.autoPlaced.pop(spec["id"], None)
                rects[spec["id"]] = clamp(*spec["position"], w, h)
            elif spec["id"] in self.autoPlaced:
                rects[spec["id"]] = clamp(*self.autoPlaced[spec["id"]], w, h)
        rank = {windowId: i for i, windowId in enumerate(openOrder)}
        new = sorted((s for s in windows if s["id"] not in rects), key=lambda s: rank.get(s["id"], len(rank)))
        player = self.screenTile(playerPosition).inflate(self.tileSize * 4, self.tileSize * 4) if playerPosition is not None else None
        for spec in new:
            w, h = sizes[spec["id"]]
            spot = self.findSpot(spec["id"], w, h, list(rects.values()), player)
            self.autoPlaced[spec["id"]] = (spot.x, spot.y)
            rects[spec["id"]] = spot
        return rects

    def findSpot(self, windowId, w, h, others, player):
        W, H, gap = self.screenWidth, self.screenHeight, self.LAYOUT_GAP
        x, y = self.defaultWindowPosition(windowId, w, h)
        home = pygame.Rect(max(0, min(W - w, x)), max(0, min(H - h, y)), w, h)
        padded = [r.inflate(gap * 2, gap * 2) for r in others]
        if home.collidelist(padded) == -1 and not (player and home.colliderect(player)):
            return home
        best, bestScore = home, None
        for cy in range(0, max(1, H - h + 1), self.LAYOUT_STEP):
            for cx in range(0, max(1, W - w + 1), self.LAYOUT_STEP):
                spot = pygame.Rect(cx, cy, w, h)
                overlap = 0
                for o in padded:
                    c = spot.clip(o)
                    overlap += c.w * c.h
                score = (overlap, bool(player and spot.colliderect(player)), abs(cx - home.x) + abs(cy - home.y))
                if bestScore is None or score < bestScore:
                    best, bestScore = spot, score
        if bestScore and bestScore[0] > 0:  # nowhere free: keep it clearly offset from what it overlaps
            shift = self.LAYOUT_SHIFT
            for _ in range(len(others) + 1):
                clash = next((r for r in others if abs(r.x - best.x) < shift and abs(r.y - best.y) < shift), None)
                if clash is None:
                    break
                nx = clash.x + shift if clash.x + shift + w <= W else clash.x - shift
                ny = clash.y + shift if clash.y + shift + h <= H else clash.y - shift
                best = pygame.Rect(max(0, nx), max(0, ny), w, h)
        return best

    def defaultWindowPosition(self, windowId, w, h):
        """Where each window docks until the player drags it somewhere else."""
        W, H = self.screenWidth, self.screenHeight
        top, gap = 70, 12
        characterHeight = self.WINDOW_HEAD + 8 * self.ROW + 14
        equipmentHeight = getattr(self, "equipmentHeight", self.WINDOW_HEAD + 8 * self.ROW + 14)
        inventoryWidth = self.PAD * 2 + 5 * self.BOX_W + self.INV_DETAIL_W
        inventoryHeight = self.WINDOW_HEAD + 2 * self.BOX_H + 18
        sideColumn = 340  # room for the widest left/right column window (Character, Room, Equipment, Level Up)
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
            case "items":  # above the right end of the inventory (beside it there's no room for both)
                return (W - inventoryWidth) // 2 + inventoryWidth - w, H - 16 - inventoryHeight - gap - h
            # Materials and Loot Table dock in the gaps beside the side columns (left of center and right of
            # center), at the top, so they don't cover the player in the middle or the other windows
            case "materials":
                return 16 + sideColumn + gap, 16
            case "loot":
                return W - 16 - sideColumn - gap - w, 16
            case "crafting":  # top middle, above the player
                return (W - w) // 2, 16
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

        if spec["kind"] == "sections":
            self.drawSections(spec, rect, focused, body)
            return
        if spec["kind"] == "craft":
            self.drawCraft(spec, rect, focused, body)
            return
        if spec["kind"] == "grid":
            gx, gy = rect.x + self.PAD, rect.y + self.WINDOW_HEAD + 4
            for i in range(spec["capacity"]):
                box = pygame.Rect(gx + (i % 5) * self.BOX_W + 3, gy + (i // 5) * self.BOX_H + 3, self.BOX_W - 6, self.BOX_H - 6)
                selected = focused and i == spec["selected"]
                if selected:
                    pygame.draw.rect(win, highlight, box)
                pygame.draw.rect(win, select if selected else boxLine, box, width=2 if selected else 1)
                if i < len(spec["items"]):  # long names ("Masterwork Wooden Shield") wrap onto lines above
                    lines = self.wrapText(spec["items"][i], self.windowSmallFont, box.w - 14)[-3:]
                    for n, line in enumerate(reversed(lines)):
                        self.blitText(win, line, self.windowSmallFont, select if selected else body, box.x + 8, box.bottom - 16 - n * 18)
            if spec.get("detail"):
                self.drawItemDetail(win, spec["detail"], pygame.Rect(gx + 5 * self.BOX_W + 8, gy, self.INV_DETAIL_W - 16, rect.bottom - gy - 10))
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
            color = select if selected else (muted if i in spec.get("dimRows", ()) else body)
            self.blitText(win, ("> " if selected else "") + str(label), self.windowFont, color, rect.x + self.PAD + 2, rowY)
            self.blitText(win, value, self.windowFont, muted if value == "None" else color, rect.right - self.PAD, rowY, align="right")
        if spec.get("preview"):
            self.drawPreview(spec["preview"], rect)

    BETTER = (130, 210, 120)

    def drawPreview(self, preview, beside):
        """A panel attached to the Level Up window while it's focused: what one more point in the selected
        stat changes. preview = {"title", "rows": [(what, now, after)], "note"}. It sits to the left of the
        window, or to the right when there's no room."""
        win = self.win
        panel, font, muted, select = (self.color(c) for c in ("panel", "font", "muted", "select"))
        gap, colGap = 8, 18
        rows = preview["rows"]
        labelW = max([self.windowFont.size(what)[0] for what, _, _ in rows] or [0])
        nowW = max([self.windowFont.size(now)[0] for _, now, _ in rows] or [0])
        afterW = max([self.windowFont.size(after)[0] for _, _, after in rows] or [0])
        arrowW = self.windowFont.size("->")[0]
        w = max(self.windowTitleFont.size(preview["title"])[0], self.windowFont.size("Does nothing yet")[0], labelW + colGap + nowW + colGap + arrowW + colGap + afterW,
                self.windowSmallFont.size(preview.get("note", ""))[0]) + self.PAD * 2 + 4
        h = self.WINDOW_HEAD + max(1, len(rows)) * self.ROW + (self.ROW if preview.get("note") else 0) + 14
        x = beside.x - gap - w if beside.x - gap - w >= 0 else beside.right + gap
        rect = pygame.Rect(x, beside.y, w, h)
        pygame.draw.rect(win, panel, rect)
        pygame.draw.rect(win, select, rect, width=2)
        self.blitText(win, preview["title"], self.windowTitleFont, select, rect.x + self.PAD + 2, rect.y + 24)
        pygame.draw.rect(win, self.color("boxLine"), pygame.Rect(rect.x + self.PAD, rect.y + self.WINDOW_HEAD - 4, rect.w - self.PAD * 2, 1))
        y = rect.y + self.WINDOW_HEAD + self.ROW // 2 + 2
        if not rows:
            self.blitText(win, "Does nothing yet", self.windowFont, muted, rect.x + self.PAD + 2, y)
            y += self.ROW
        right = rect.right - self.PAD
        for what, now, after in rows:
            changes = now != after
            self.blitText(win, what, self.windowFont, font, rect.x + self.PAD + 2, y)
            self.blitText(win, after, self.windowFont, self.BETTER if changes else muted, right, y, align="right")
            self.blitText(win, "->", self.windowFont, muted, right - afterW - colGap, y, align="right")
            self.blitText(win, now, self.windowFont, muted, right - afterW - colGap - arrowW - colGap, y, align="right")
            y += self.ROW
        if preview.get("note"):
            self.blitText(win, preview["note"], self.windowSmallFont, muted, rect.x + self.PAD + 2, y)

    def drawItemDetail(self, win, lines, area):
        """The inventory's details panel: the selected item's slot, bonuses, effects and how it compares."""
        muted, body, select = self.color("muted"), self.color("font"), self.color("select")
        pygame.draw.line(win, self.color("boxLine"), (area.x - 6, area.y), (area.x - 6, area.bottom))
        y = area.y + 10
        styles = {"title": (self.windowFont, select), "label": (self.windowSmallFont, muted), "row": (self.windowSmallFont, body),
                  "muted": (self.windowSmallFont, muted), "body": (self.windowSmallFont, body), "hint": (self.windowSmallFont, muted),
                  "ench": (self.windowSmallFont, (200, 168, 255)), "better": (self.windowSmallFont, (130, 210, 120)),
                  "worse": (self.windowSmallFont, self.color("enemy"))}
        for style, text, value in lines:
            font, color = styles.get(style, styles["body"])
            for part in self.wrapText(text, font, area.w - (90 if value else 4)):
                if y > area.bottom - 6:
                    return
                self.blitText(win, part, font, color, area.x, y)
                if value:
                    self.blitText(win, str(value), self.windowSmallFont, select if style == "row" else muted, area.right, y, align="right")
                    value = ""
                y += 22 if style == "title" else 18

    # Crafting window layout
    CRAFT_W = 640        # whole window width
    CRAFT_LIST_W = 220   # the recipe list on the left
    DETAIL_ROW = 21      # line height in the details on the right
    DETAIL_LINES = 11    # the details area is at least this tall, so the window doesn't jump around
    LIST_ROW = 26        # row height in the recipe list (it scrolls when there are more than fit)

    def craftAreaHeight(self, spec):
        return max(self.DETAIL_LINES, len(self.craftDetailLines(spec))) * self.DETAIL_ROW

    def wrapText(self, text, font, width):
        """Splits text into lines that fit in width pixels."""
        lines, line = [], ""
        for word in str(text).split(" "):
            attempt = word if not line else line + " " + word
            if line and font.size(attempt)[0] > width:
                lines.append(line)
                line = word
            else:
                line = attempt
        return lines + [line]

    def craftDetailLines(self, spec):
        """The details as drawn: (style, text, value) with long text already wrapped."""
        width = self.CRAFT_W - self.PAD * 2 - self.CRAFT_LIST_W - 20
        lines = []
        for style, text, value in spec["detail"]:
            if style in ("muted", "body", "warn", "ench"):
                lines += [(style, part, "") for part in self.wrapText(text, self.windowSmallFont, width)]
            else:
                lines.append((style, text, value))
        return lines

    def drawCraft(self, spec, rect, focused, body):
        """Station tabs along the top, the recipe list on the left, details on the right, a status line below."""
        win = self.win
        muted, select, boxLine, short = self.color("muted"), self.color("select"), self.color("boxLine"), self.color("enemy")
        highlight = themes.mix(self.color("panel"), select, 0.14)
        x = rect.x + self.PAD + 2
        y = rect.y + self.WINDOW_HEAD + self.ROW // 2 + 2
        tx = x
        for i, name in enumerate(spec["tabs"]):
            selected = i == spec["tab"]
            locked = spec.get("tabsLocked", [False] * len(spec["tabs"]))[i]
            w = self.windowSmallFont.size(name)[0] + 16
            box = pygame.Rect(tx, y - 11, w, 22)
            if locked and not selected:
                pygame.draw.rect(win, themes.mix(self.color("panel"), boxLine, 0.5), box, width=1)
                self.blitText(win, name, self.windowSmallFont, themes.mix(self.color("panel"), muted, 0.55), tx + 8, y)
            else:
                pygame.draw.rect(win, select if selected else boxLine, box, width=1)
                self.blitText(win, name, self.windowSmallFont, select if selected else body, tx + 8, y)
            tx += w + 6
        top = y + self.ROW // 2 + 4

        # recipe list
        listRight = rect.x + self.PAD + self.CRAFT_LIST_W
        areaHeight = self.craftAreaHeight(spec)
        rows = spec["list"]
        fit = areaHeight // self.LIST_ROW
        start = max(0, min(spec["selected"] - fit // 2, len(rows) - fit))  # keep the selected row in view
        if not rows:
            self.blitText(win, "Nothing here yet", self.windowFont, muted, x, top + self.LIST_ROW // 2)
        for i in range(start, min(len(rows), start + fit)):
            name, value, ready = rows[i]
            rowY = top + (i - start) * self.LIST_ROW + self.LIST_ROW // 2
            selected = focused and i == spec["selected"]
            if selected:
                pygame.draw.rect(win, highlight, pygame.Rect(rect.x + 2, rowY - self.LIST_ROW // 2, listRight - rect.x - 2, self.LIST_ROW))
            color = select if selected else (body if ready else muted)
            label = ("> " if selected else "") + name
            while self.windowFont.size(label)[0] > self.CRAFT_LIST_W - 46 and len(label) > 4:
                label = label[:-2] + "."  # long names (a relic's) get cut short
            self.blitText(win, label, self.windowFont, color, x, rowY)
            self.blitText(win, value, self.windowSmallFont, color, listRight - 8, rowY, align="right")
        arrowX = listRight - 4
        if start > 0:  # more above / below: small arrows on the divider
            pygame.draw.polygon(win, muted, [(arrowX - 4, top + 6), (arrowX + 4, top + 6), (arrowX, top + 1)])
        if start + fit < len(rows):
            bottom = top + areaHeight
            pygame.draw.polygon(win, muted, [(arrowX - 4, bottom - 6), (arrowX + 4, bottom - 6), (arrowX, bottom - 1)])
        pygame.draw.rect(win, boxLine, pygame.Rect(listRight + 6, top, 1, areaHeight))

        # details
        dx, right = listRight + 20, rect.right - self.PAD
        for i, (style, text, value) in enumerate(self.craftDetailLines(spec)):
            lineY = top + i * self.DETAIL_ROW + self.DETAIL_ROW // 2
            if style == "title":
                self.blitText(win, text, self.windowFont, body, dx, lineY)
            elif style == "label":
                self.blitText(win, text, self.windowSmallFont, select if focused else muted, dx, lineY)
                if value:
                    self.blitText(win, value, self.windowSmallFont, body, right, lineY, align="right")
            elif style in ("need", "short"):
                color = body if style == "need" else short
                self.blitText(win, text, self.windowSmallFont, color, dx + 10, lineY)
                self.blitText(win, value, self.windowSmallFont, color, right, lineY, align="right")
            elif style == "hint":
                self.blitText(win, text, self.windowSmallFont, muted, dx, lineY)
            elif style == "warn":
                self.blitText(win, text, self.windowSmallFont, short, dx, lineY)
            elif style == "ench":
                self.blitText(win, text, self.windowSmallFont, (200, 168, 255), dx, lineY)
            else:
                self.blitText(win, text, self.windowSmallFont, muted if style == "muted" else body, dx, lineY)

        # status line, with a progress bar while crafting
        statusY = top + areaHeight + self.ROW // 2 + 2
        pygame.draw.rect(win, boxLine, pygame.Rect(rect.x + self.PAD, statusY - self.ROW // 2, rect.w - self.PAD * 2, 1))
        if spec.get("progress") is not None:
            barW = rect.w - self.PAD * 2
            pygame.draw.rect(win, highlight, pygame.Rect(rect.x + self.PAD, statusY - 9, barW, 18))
            pygame.draw.rect(win, themes.mix(self.color("panel"), select, 0.45), pygame.Rect(rect.x + self.PAD, statusY - 9, int(barW * spec["progress"]), 18))
        if spec.get("status"):
            self.blitText(win, spec["status"], self.windowSmallFont, body, x, statusY)

    def drawSections(self, spec, rect, focused, body):
        """A window made of titled groups of rows, each row with an optional color swatch (Materials, Loot Table)."""
        win = self.win
        muted, select, boxLine = self.color("muted"), self.color("select"), self.color("boxLine")
        y = rect.y + self.WINDOW_HEAD + self.ROW // 2 + 2
        x = rect.x + self.PAD + 2
        if spec.get("tabs"):
            tx = x
            for i, name in enumerate(spec["tabs"]):
                selected = i == spec["tab"]
                w = self.windowSmallFont.size(name)[0] + 16
                box = pygame.Rect(tx, y - 11, w, 22)
                pygame.draw.rect(win, select if selected else boxLine, box, width=1)
                self.blitText(win, name, self.windowSmallFont, (select if selected else muted), tx + 8, y)
                tx += w + 8
            y += self.ROW
        for section in spec["sections"]:
            if section.get("title"):
                self.blitText(win, section["title"], self.windowFont, muted if section["title"] == "???" else body, x, y)
                y += self.ROW
            indent = x + (12 if section.get("title") else 0)
            for label, value, color in section["rows"]:
                textX = indent
                if color is not None:
                    pygame.draw.rect(win, color, pygame.Rect(indent, y - 5, 10, 10))
                    textX = indent + 18
                unknown = label == "???"
                self.blitText(win, label, self.windowFont, muted if unknown else body, textX, y)
                self.blitText(win, value, self.windowFont, muted if unknown else body, rect.right - self.PAD, y, align="right")
                y += self.ROW
            if section.get("note"):
                self.blitText(win, section["note"], self.windowSmallFont, muted, indent, y)
                y += self.ROW

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
        perColumn = pause["perColumn"]
        listBottom = 96 + perColumn * 30  # where the hotkey rows end (in k units); everything below follows it
        w, h = int(430 * k), int((listBottom + 116) * k)
        pad = int(18 * k)
        rect = pygame.Rect(x0, y0, w, h)
        pygame.draw.rect(win, panel, rect)
        pygame.draw.rect(win, font, rect, width=2)

        self.blitText(win, "Hotkeys", self.menuOptionFont, font, x0 + pad, y0 + int(30 * k))
        hint = "Press a key to bind it.   Esc  cancel" if pause["rebinding"] else "Enter  change key      Esc  back"
        self.blitText(win, hint, self.menuHintFont, muted, x0 + pad, y0 + int(56 * k))
        pygame.draw.rect(win, boxLine, pygame.Rect(x0 + pad, y0 + int(72 * k), w - pad * 2, 1))

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

        pygame.draw.rect(win, boxLine, pygame.Rect(x0 + pad, y0 + int((listBottom - 6) * k), w - pad * 2, 1))
        if pause["message"]:
            self.blitText(win, pause["message"], self.menuHintFont, select, x0 + pad, y0 + int((listBottom + 14) * k))
        self.blitText(win, "Fixed keys", self.menuHintFont, muted, x0 + pad, y0 + int((listBottom + 42) * k))
        for i, (keyName, label) in enumerate(pause["fixed"]):
            col, row = i % 2, i // 2
            cx = x0 + pad + col * (colW + pad)
            cy = y0 + int((listBottom + 66 + row * 22) * k)
            self.blitText(win, f"{keyName}  -  {label}", self.menuHintFont, font, cx, cy)

    def drawMessage(self, message):
        """A big centered message; a second line (after a newline) is drawn smaller under it."""
        first, _, second = message.partition("\n")
        alpha = max(0, int(self.fade))
        canvas = getattr(self, "messageCanvas", None)
        if canvas is None or canvas.get_size() != (self.screenWidth, self.screenHeight):
            canvas = self.messageCanvas = pygame.Surface((self.screenWidth, self.screenHeight), pygame.SRCALPHA)
        canvas.fill((0, 0, 0, alpha))
        key = (message, tuple(self.color("font")), tuple(self.color("select")))
        if getattr(self, "messageText", (None,))[0] != key:
            self.messageText = (key, self.SplashScreenFont.render(first, True, self.color("font")),
                                self.titleOptionFont.render(second, True, self.color("select")) if second else None)
        _, text, sub = self.messageText
        text.set_alpha(alpha)
        total = text.get_height() + (sub.get_height() + 6 if sub else 0)
        top = self.screenHeight // 2 - total // 2
        canvas.blit(text, (self.screenWidth // 2 - text.get_width() // 2, top))
        if sub:
            sub.set_alpha(alpha)
            canvas.blit(sub, (self.screenWidth // 2 - sub.get_width() // 2, top + text.get_height() + 6))
        return canvas

    # ------------------------------------------------------------------ tiles

    # where the ore flecks sit in a vein tile: (x, y, also draw the pixel to the right, highlight above)
    VEIN_FLECKS = [(3, 3, True, True), (6, 4, False, True), (4, 6, True, True), (2, 5, False, False), (6, 7, True, False), (5, 2, False, False)]

    def drawWall(self, wall, color, memorized=False, glintAt=None) -> pygame.Surface:
        """glintAt: the tile's position, for a vein in view (it twinkles, see GLINT_*). The picture is cached
        until the wall gets chipped (the cache holds the wall too, so its id can't be reused by another)."""
        if glintAt is not None and isinstance(wall, walls.OreVein):
            return self.paintWall(wall, color, memorized, glintAt)
        if not hasattr(self, "wallCache"):
            self.clearTileCaches()
        key = (id(wall), tuple(color), memorized, len(wall.brokenPoints), getattr(wall, "corruptedBy", None),
               getattr(wall, "paint", None), self.tileSize)
        return self.cached(self.wallCache, key, lambda: (wall, self.paintWall(wall, color, memorized, None)))[1]

    def paintWall(self, wall, color, memorized, glintAt) -> pygame.Surface:
        canvas = pygame.Surface((self.tileSize, self.tileSize))
        canvas.fill(color)
        if isinstance(wall, walls.OreVein):
            ore, shine = wall.oreColor, wall.oreHighlight
            if memorized:  # out of sight: the flecks dim like everything else that's remembered
                fog = self.theme.colors["fog"]
                ore, shine = themes.remembered(list(ore), fog), themes.remembered(list(shine), fog)
            for x, y, wide, lit in self.VEIN_FLECKS:
                canvas.fill(ore, pygame.Rect(x, y, 2 if wide else 1, 1))
                if lit:
                    canvas.fill(shine, pygame.Rect(x, y - 1, 1, 1))
            if glintAt is not None and not memorized:
                self.drawGlint(canvas, glintAt, ore, shine, color)
        kind = getattr(wall, "corruptedBy", None)
        if kind:
            self.drawVines(canvas, kind, memorized)
        brokenColor = [max(0, c - 100) for c in color]
        # (the edge goes on before the cracks: they're the same color, so a crack on the edge looks the same)
        pygame.draw.rect(canvas, brokenColor, pygame.Rect(0, 0, self.tileSize, self.tileSize), width=2)
        paint = getattr(wall, "paint", None)
        if paint:  # over the edge, so the joints run on from one wall tile to the next
            self.drawMortar(canvas, paint, memorized)
        for point in wall.brokenPoints:
            pygame.draw.rect(canvas, brokenColor, pygame.Rect(point[0], point[1], 1, 1))
        return canvas

    # A painted hut wall (expansion.paintHutWall) is drawn as laid stone blocks with the joints between them in its
    # faction's cloak color. On a 10x10 grid, as for the hut's north wall (u along the wall, v from the outside in):
    # a joint 2 wide along the whole wall, and one across it in each half, alternating with parity. Turned for the
    # other sides.
    MORTAR = {0: ((0, 4, 10, 2), (6, 0, 2, 4), (2, 6, 2, 4)), 1: ((0, 4, 10, 2), (2, 0, 2, 4), (6, 6, 2, 4))}

    def drawMortar(self, canvas, paint, memorized):
        look, side, parity = paint
        looks = sprites.EXPANSION_LOOKS
        color = list(looks.get(look, looks[expansion.LOOKS[0]])["goblin"]["c"])
        if memorized:
            color = themes.remembered(color, self.theme.colors["fog"])
        ts = self.tileSize
        cell = lambda n: round(n * ts / 10)
        for u, v, w, h in self.MORTAR[parity]:
            if side == "n":
                x, y, W, H = u, v, w, h
            elif side == "s":
                x, y, W, H = 10 - u - w, 10 - v - h, w, h
            elif side == "w":
                x, y, W, H = v, 10 - u - w, h, w
            else:
                x, y, W, H = 10 - v - h, u, h, w
            canvas.fill(color, pygame.Rect(cell(x), cell(y), cell(x + W) - cell(x), cell(y + H) - cell(y)))

    # ------------------------------------------------------------ ore glints

    def glintTimer(self, i):
        """(period, phase, fleck order) for the tile at i: random, but always the same for that tile."""
        timers = self.__dict__.setdefault("glintTimers", {})
        if i not in timers:
            rng = random.Random(i)
            order = list(range(len(self.VEIN_FLECKS)))
            rng.shuffle(order)
            timers[i] = (rng.uniform(*GLINT_PERIOD), rng.uniform(0, GLINT_PERIOD[1]), order)
        return timers[i]

    def glintPhase(self, i, now):
        """(cycle, ms into the twinkle) if the tile at i is twinkling at time now, else None."""
        period, phase, _ = self.glintTimer(i)
        t = (now + phase) % period
        return (int((now + phase) // period), t) if t < GLINT_LENGTH else None

    def drawGlint(self, canvas, i, ore, shine, wallColor):
        state = self.glintPhase(i, getattr(self, "frameTicks", pygame.time.get_ticks()))
        if state is None:
            return
        cycle, t = state
        order = self.glintTimer(i)[2]
        start = (cycle * 3) % len(order)  # a different three flecks each time

        def light(base, b):  # brighten toward the shine color, then on to white
            return themes.mix(list(base), list(shine), b * 2) if b < 0.5 else themes.mix(list(shine), list(GLINT_WHITE), b * 2 - 1)

        for k in range(3):
            u = (t - k * GLINT_STAGGER) / GLINT_FLASH
            if not 0 < u < 1:
                continue
            b = (1 - u) ** 2  # flash, then fade
            x, y, wide, lit = self.VEIN_FLECKS[order[(start + k) % len(order)]]
            canvas.fill(light(ore, b), pygame.Rect(x, y, 2 if wide else 1, 1))
            if lit:
                canvas.fill(light(shine, b), pygame.Rect(x, y - 1, 1, 1))
            if k == 0 and b > 0.35:  # the star, blended over the wall around the first fleck
                star = themes.mix(list(wallColor), themes.mix(list(shine), list(GLINT_WHITE), b), b)
                points = [(-1, 0), (1, 0), (0, -1), (0, 1)] + ([(-2, 0), (2, 0), (0, -2), (0, 2)] if b > 0.8 else [])
                for dx, dy in points:
                    if 0 <= x + dx < self.tileSize and 0 <= y + dy < self.tileSize:
                        canvas.fill(star, pygame.Rect(x + dx, y + dy, 1, 1))

    def glintsDue(self, grid, now):
        """Called every frame: True when a vein tile in view has started, is in the middle of, or just finished
        a twinkle at this GLINT_FPS step (those are the tiles redrawGlints redraws)."""
        step = now * GLINT_FPS // 1000
        if step == getattr(self, "glintStep", None):
            return False
        self.glintStep = step
        active = {i for i in getattr(self, "litVeins", ()) if grid.get(i, (None, 0))[1] == 1 and self.glintPhase(i, now) is not None}
        self.glintDirty = active | getattr(self, "glintActive", set())
        self.glintActive = active
        return bool(self.glintDirty)

    def redrawGlints(self, grid, rooms, playerDirection, playerPosition, visionRange, light):
        for i in getattr(self, "glintDirty", ()):
            if grid.get(i, (None, 0))[1] == 1:
                self.refreshTile(grid, i, rooms, playerDirection, playerPosition, visionRange, light)

    def drawVines(self, canvas, kind, memorized):
        plantColors = plants.PLANTS[kind]["colors"]
        palette = {"c": plantColors["c"], "C": plantColors.get("C", plantColors["c"]), "s": plantColors.get("s", plantColors["c"])}
        if memorized:
            fog = self.theme.colors["fog"]
            palette = {k: themes.remembered(list(v), fog) for k, v in palette.items()}
        scale = self.tileSize / 10
        for y, row in enumerate(VINES):
            for x, ch in enumerate(row):
                if ch != ".":
                    canvas.fill(palette[ch], pygame.Rect(int(x * scale), int(y * scale), max(1, int(scale)), max(1, int(scale))))

    def drawAimline(self, aimLine):
        if aimLine is None:
            return
        for i in aimLine:
            self.fillTile(self.color("aim"), i % self.rowLength, i // self.rowLength)

    # Thrown potions. Drawn straight onto the window after the map (the window is cleared every frame), so the
    # see-through tints never pile up on tiles the light-only redraw skips.

    def screenTile(self, position):
        return pygame.Rect(self.mapOffset[0] + (position % self.rowLength) * self.tileSize,
                           self.mapOffset[1] + (position // self.rowLength) * self.tileSize, self.tileSize, self.tileSize)

    def tint(self, color, alpha):
        surface = pygame.Surface((self.tileSize, self.tileSize), pygame.SRCALPHA)
        surface.fill((*color[:3], alpha))
        return surface

    MAGIC_PURPLE, MAGIC_LIGHT = (176, 84, 196), (236, 190, 244)

    def effectColor(self, effect):
        if effect == "Magic":
            return self.MAGIC_PURPLE
        return self.color("enemy") if effect in ("Fire","Explosive") else self.color("font")

    FIRE_RED, FIRE_ORANGE, FIRE_YELLOW = (196, 48, 28), (240, 128, 40), (255, 222, 120)

    def drawBlast(self, landing, area, effect, turns, alpha, time):
        """A potion's reach: the round splash tinted with its outer edge traced, the landing tile boxed, and how
        many turns until it lands over it. A throw that lands at once shows a little looping burst instead."""
        color = self.effectColor(effect)
        fill = self.tint(color, alpha)
        tiles = set(area)
        for position in area:
            rect = self.screenTile(position)
            self.win.blit(fill, rect)
            # trace only the outside edge, so the splash reads as one round shape
            x = position % self.rowLength
            if x == 0 or position - 1 not in tiles:
                pygame.draw.line(self.win, color, rect.topleft, rect.bottomleft)
            if x == self.rowLength - 1 or position + 1 not in tiles:
                pygame.draw.line(self.win, color, (rect.right - 1, rect.top), (rect.right - 1, rect.bottom - 1))
            if position - self.rowLength not in tiles:
                pygame.draw.line(self.win, color, rect.topleft, (rect.right - 1, rect.top))
            if position + self.rowLength not in tiles:
                pygame.draw.line(self.win, color, (rect.left, rect.bottom - 1), (rect.right - 1, rect.bottom - 1))
        rect = self.screenTile(landing)
        pygame.draw.rect(self.win, color, rect.inflate(2, 2), width=2)
        if turns == 0:
            self.drawBurst(rect.center, self.tileSize * 0.9, effect, (time * 1.6) % 1)
            return
        label = str(turns)
        shadow = self.popupFont.render(label, True, (0, 0, 0))
        text = self.popupFont.render(label, True, color)
        textRect = text.get_rect(midbottom=(rect.centerx, rect.top - 2))
        self.win.blit(shadow, textRect.move(1, 1))
        self.win.blit(text, textRect)

    def drawBurst(self, center, reach, effect, age):
        """An explosion (fire) or a puff (smoke) growing out from center to reach pixels as age goes 0 to 1."""
        age = max(0.0, min(1.0, age))
        size = int(reach * 2.4) + 4
        surface = pygame.Surface((size, size), pygame.SRCALPHA)
        c = size // 2
        grow = 1 - (1 - age) ** 3  # fast out, slow at the end
        fade = int(255 * (1 - age))
        if effect in ("Fire","Explosive"):
            if age < 0.6:  # the bright core
                coreAge = age / 0.6
                core = self.FIRE_YELLOW if coreAge < 0.4 else self.FIRE_ORANGE
                pygame.draw.circle(surface, (*core, int(230 * (1 - coreAge))), (c, c), max(1, int(reach * 0.85 * grow)))
            pygame.draw.circle(surface, (*self.FIRE_RED, fade // 2), (c, c), max(1, int(reach * grow)))
            pygame.draw.circle(surface, (*self.FIRE_ORANGE, fade), (c, c), max(2, int(reach * grow)), width=max(1, int(reach / 6)))
            for k in range(8):  # sparks flying out
                angle = k * math.pi / 4 + 0.4
                d = reach * (0.4 + 0.75 * grow)
                spot = (int(c + math.cos(angle) * d), int(c + math.sin(angle) * d))
                pygame.draw.circle(surface, (*self.FIRE_YELLOW, fade), spot, max(1, int(reach / 10)))
        elif effect == "Magic":  # a ring of purple thorns bursting out from a pale flash
            pygame.draw.circle(surface, (*self.MAGIC_LIGHT, int(200 * (1 - age))), (c, c), max(1, int(reach * 0.6 * (1 - grow) + 1)))
            pygame.draw.circle(surface, (*self.MAGIC_PURPLE, fade), (c, c), max(2, int(reach * grow)), width=max(1, int(reach / 6)))
            for k in range(6):
                angle = k * math.pi / 3 + 0.5 * grow
                inner, outer = reach * 0.3 * grow, reach * (0.5 + 0.6 * grow)
                start = (int(c + math.cos(angle) * inner), int(c + math.sin(angle) * inner))
                end = (int(c + math.cos(angle) * outer), int(c + math.sin(angle) * outer))
                pygame.draw.line(surface, (*self.MAGIC_LIGHT, fade), start, end, max(1, int(reach / 8)))
        else:
            gray = themes.desaturate(list(self.color("font")), 0.9)
            for k in range(7):
                angle = k * 2 * math.pi / 7
                d = reach * 0.55 * grow
                spot = (int(c + math.cos(angle) * d), int(c + math.sin(angle) * d))
                pygame.draw.circle(surface, (*gray[:3], int(fade * 0.6)), spot, max(1, int(reach * (0.25 + 0.3 * grow))))
        self.win.blit(surface, (center[0] - c, center[1] - c))

    def drawFlames(self, rect, time, phase, creature=False):
        """Fire seen from above, see-through so the floor shows: a flickering ring of red lobes round an orange
        middle and a yellow core, with an ember drifting out. Something on fire (creature) gets four small
        flames circling its edge instead, so you can still see what it is."""
        w = self.tileSize
        layer = pygame.Surface((w * 2, w * 2), pygame.SRCALPHA)
        cx = cy = w
        if creature:
            for k in range(4):
                a = k * math.pi / 2 + time * 2.2 + phase
                flick = 0.7 + 0.3 * math.sin(time * 13 + k * 1.9 + phase)
                spot = (cx + math.cos(a) * w * 0.45, cy + math.sin(a) * w * 0.45)
                pygame.draw.circle(layer, (*self.FIRE_RED, 190), spot, max(1, w * 0.13 * flick))
                pygame.draw.circle(layer, (*self.FIRE_ORANGE, 200), spot, max(1, w * 0.07 * flick))
        else:
            for spin, color, ring, size, count in ((-0.9, (*self.FIRE_RED, 170), 0.2, 0.18, 5),
                                                   (1.3, (*self.FIRE_ORANGE, 190), 0.1, 0.13, 4)):
                for k in range(count):
                    a = k * 2 * math.pi / count + time * spin + phase
                    flick = 0.75 + 0.25 * math.sin(time * 12 + k * 2.4 + phase * 3)
                    pygame.draw.circle(layer, color, (cx + math.cos(a) * w * ring, cy + math.sin(a) * w * ring), max(1, w * size * flick))
            pygame.draw.circle(layer, (*self.FIRE_YELLOW, 210), (cx, cy), max(1, w * (0.08 + 0.03 * math.sin(time * 15 + phase))))
            t = (time * 1.4 + phase * 0.13) % 1  # an ember drifting outward
            a = phase * 5 + t * 0.8
            d = w * (0.2 + 0.55 * t)
            pygame.draw.circle(layer, (*(self.FIRE_YELLOW if t < 0.5 else self.FIRE_ORANGE), 200),
                               (cx + math.cos(a) * d, cy + math.sin(a) * d), 1)
        self.win.blit(layer, (rect.centerx - w, rect.centery - w))

    # Blood, seen from above. Pools are drawn as part of the floor (under sprites, dimmed with the floor when
    # remembered). Each tile's blob shape is fixed by its position, so pools grow without wobbling.
    BLOOD_DARK, BLOOD, BLOOD_LIGHT = (92, 6, 10), (138, 14, 20), (186, 52, 52)
    DRIED_DARK, DRIED = (48, 28, 22), (82, 44, 32)

    def floorFill(self, i, rooms, memorized, x, y):
        self.fillTile(self.floorColor(i, rooms, memorized), x, y)
        amount = self.blood.get(i, 0) if self.blood else 0
        if amount > 0:
            ts = self.tileSize
            self.drawBlood(pygame.Rect(x * ts, y * ts, ts, ts), min(1.0, amount), i, memorized, self.bloodDry.get(i, 0))

    def drawBlood(self, rect, amount, seed, memorized, dry=0):
        """Blood on a floor tile. Its picture is cached by look (rounded a little, so it changes in small steps
        as it dries)."""
        if not hasattr(self, "bloodCache"):
            self.clearTileCaches()
        key = (seed, round(amount, 2), round(dry, 2), memorized, rect.w)

        def make():
            picture = pygame.Surface((rect.w, rect.h), pygame.SRCALPHA)
            self.paintBlood(picture, pygame.Rect(0, 0, rect.w, rect.h), key[1], seed, memorized, key[2])
            return picture
        self.mapSurface.blit(self.cached(self.bloodCache, key, make), rect)

    def paintBlood(self, surface, rect, amount, seed, memorized, dry):
        rng = random.Random(seed)
        w = rect.w
        colors = (themes.mix(self.BLOOD_DARK, self.DRIED_DARK, dry),
                  themes.mix(self.BLOOD, self.DRIED, dry),
                  self.BLOOD_LIGHT)
        if memorized:
            fog = self.theme.colors["fog"]
            colors = tuple(themes.remembered(list(c), fog) for c in colors)
        dark, mid, light = colors
        old = surface.get_clip()
        surface.set_clip(rect)
        spots = [(rect.x + w * rng.uniform(0.2, 0.8), rect.y + w * rng.uniform(0.2, 0.8), rng.uniform(0.6, 1.0))
                 for _ in range(2 + int(amount * 4))]
        for x, y, size in spots:
            pygame.draw.circle(surface, dark, (x, y), max(1, w * (0.12 + 0.4 * amount) * size))
        for x, y, size in spots:
            pygame.draw.circle(surface, mid, (x, y), max(1, w * (0.08 + 0.32 * amount) * size))
        if amount > 0.35 and dry < .5:
            x, y, _ = spots[0]
            pygame.draw.circle(surface, light, (x - w * 0.08, y - w * 0.08), 1)
        surface.set_clip(old)

    def drawParticles(self, spurts, flecks):
        """Blood spurts (a few red specks flying off whatever was hurt) and wall flecks (chips flying off the
        face of a wall that was hit, out to both sides of whoever hit it). Ages go 0 to 1."""
        for tile, age, seed in spurts:
            rng = random.Random(seed)
            rect = self.screenTile(tile)
            ease = 1 - (1 - age) ** 2
            color = (200, 30, 34) if age < 0.5 else self.BLOOD
            for _ in range(5):
                a = rng.uniform(0, 2 * math.pi)
                d = self.tileSize * rng.uniform(0.6, 1.1) * ease
                self.win.fill(color, pygame.Rect(int(rect.centerx + math.cos(a) * d), int(rect.centery + math.sin(a) * d), 1, 1))
        for tile, age, seed, (dx, dy), colors in flecks:
            rng = random.Random(seed)
            rect = self.screenTile(tile)
            ox, oy = rect.centerx + dx * rect.w * 0.5, rect.centery + dy * rect.h * 0.5
            facing = math.atan2(dy, dx)
            ease = 1 - (1 - age) ** 2
            for k in range(5):
                side = 1 if k % 2 else -1
                a = facing + side * rng.uniform(0.55, 1.35)
                d = self.tileSize * rng.uniform(0.4, 1.1) * ease
                color = colors[rng.randrange(len(colors))]
                if age > 0.6:
                    color = themes.mix(list(color), [0, 0, 0], 0.4)
                size = 2 if k == 0 and age < 0.5 else 1
                self.win.fill(color, pygame.Rect(int(ox + math.cos(a) * d), int(oy + math.sin(a) * d), size, size))

    def drawThrows(self, throws):
        time = throws["time"]
        if throws["fires"]:
            glow = self.tint(self.FIRE_RED, 35)
            for position in throws["fires"]:
                rect = self.screenTile(position)
                self.win.blit(glow, rect)
                self.drawFlames(rect, time, position * 1.7)
        for position in throws["burning"]:  # something on fire: small flames circling it
            self.drawFlames(self.screenTile(position), time, position * 2.9, creature=True)
        if throws["smoke"]:
            smoke = self.smokeTile()
            for position, turns in throws["smoke"].items():
                tile = smoke[position % len(smoke)]
                if turns < SMOKE_THIN_TURNS:  # thinning out over its last few turns
                    tile = tile.copy()
                    tile.set_alpha(int(255 * turns / SMOKE_THIN_TURNS))
                self.win.blit(tile, self.screenTile(position))
        for shot in throws["flying"]:
            self.drawBlast(shot["landing"], shot["area"], shot["effect"], shot["turns"], 40, time)
            rect = self.screenTile(shot["at"])  # the potion itself, partway along its arc
            pygame.draw.circle(self.win, (0, 0, 0), rect.center, max(2, self.tileSize // 4) + 1)
            pygame.draw.circle(self.win, self.effectColor(shot["effect"]), rect.center, max(2, self.tileSize // 4))
        for landing, radius, effect, age in throws["explosions"]:
            self.drawBurst(self.screenTile(landing).center, (radius + 0.5) * self.tileSize, effect, age)
        self.drawParticles(throws.get("spurts", ()), throws.get("flecks", ()))
        aim = throws["aim"]
        if aim is not None:
            self.drawBlast(aim["landing"], aim["area"], aim["effect"], aim["turns"], 70, time)

    def smokeTile(self):
        """A few see-through grey haze tiles with soft puffs, so a cloud doesn't look like a repeating stamp.
        Rebuilt when the theme or the tile size changes."""
        key = (self.tileSize, id(self.theme))
        if getattr(self, "smokeKey", None) != key:
            fog = self.theme.colors["fog"]
            gray = themes.mix(themes.desaturate(list(self.color("font")), 0.9), fog, 0.25)
            light = themes.mix(gray, [255, 255, 255], 0.25)
            s = self.tileSize
            puffs = [((0.25, 0.3), (0.7, 0.6)), ((0.65, 0.25), (0.3, 0.7)), ((0.5, 0.5), (0.2, 0.2))]
            self.smokeTiles = []
            for spots in puffs:
                tile = pygame.Surface((s, s), pygame.SRCALPHA)
                tile.fill((*gray[:3], 125))
                for fx, fy in spots:
                    pygame.draw.circle(tile, (*light[:3], 70), (int(s * fx), int(s * fy)), max(2, s * 2 // 5))
                self.smokeTiles.append(tile)
            self.smokeKey = key
        return self.smokeTiles

    def fillTile(self, color, x, y):
        pygame.draw.rect(self.mapSurface, color, pygame.Rect(x * self.tileSize, y * self.tileSize, self.tileSize, self.tileSize))

    ROOM_ORDER = ("Stone", "Wood", "Gold")  # a tile in none of these is Sand
    COLOR_NAMES = {(prefix, memorized): {room: ("mem" + prefix.capitalize() if memorized else prefix) + room
                                         for room in ("Stone", "Wood", "Gold", "Sand")}
                   for prefix in ("floor", "wall") for memorized in (False, True)}

    def roomOf(self, i, rooms):
        for room in self.ROOM_ORDER:
            if i in rooms[room]:
                return room
        return "Sand"

    def floorColor(self, i, rooms, memorized):
        return self.colorDict[self.COLOR_NAMES[("floor", memorized)][self.roomOf(i, rooms)]]

    def roomWallColor(self, i, rooms, memorized):
        """The wall color of the room a tile is in (veins are drawn in their room's wall color)."""
        return self.colorDict[self.COLOR_NAMES[("wall", memorized)][self.roomOf(i, rooms)]]

    WALL_ROOMS = {}  # wall name -> its room ("Stone Wall" -> "Stone"), filled in as walls are seen

    def wallColor(self, name, memorized):
        # wall names are "Stone Wall", "Wood Wall", "Sand Wall", "Gold Wall"
        room = self.WALL_ROOMS.get(name)
        if room is None:
            room = self.WALL_ROOMS[name] = name.split(" ")[0]
        names = self.COLOR_NAMES[("wall", memorized)]
        return self.colorDict.get(names.get(room, ""), self.colorDict[names["Stone"]])

    # The map surface is kept from frame to frame. Each tile remembers a signature of everything that decides how
    # it looks (tileSignature); a frame only redraws the tiles whose signature changed. A new floor, theme or tile
    # size starts over (resetMap). Anything drawn on the map outside this (the aim line) clears its tiles' signatures.
    LIGHT_EXEMPT = (1, 3, 5, 6, 7, 8, 9, expansion.CAMP)  # never dithered by the light, so they stand out

    def resetMap(self):
        self.tileSigs = {}
        self.aimDrawn = set()
        self.animatedTiles = []
        if self.mapSurface is not None and getattr(self, "theme", None) is not None:
            self.mapSurface.fill(self.color("fog"))

    def renderScreen(self, grid: dict, rooms, playerDirection, playerPosition, visionRange, light=(0, 0, 1)):
        if not hasattr(self, "tileSigs"):
            self.resetMap()
        self.litTiles = []  # tiles in view, remembered so the swaying light can redraw just these
        animated = []
        sigs = self.tileSigs
        for i, tile in grid.items():
            visibility = tile[1]
            if visibility == 0:
                if i in sigs:  # (seen before, unseen now: back to fog)
                    del sigs[i]
                    self.fillTile(self.color("fog"), i % self.rowLength, i // self.rowLength)
                continue
            if visibility == 1:
                self.litTiles.append(i)
                if tile[0] == 5 and len(tile) > 2 and tile[2].name == "Unsealed":
                    animated.append(i)
            if tile[0] == expansion.CAMP and tile[2].kind == "bonfire":  # its flames move, seen or remembered
                animated.append(i)
            self.refreshTile(grid, i, rooms, playerDirection, playerPosition, visionRange, light)
        self.animatedTiles = animated
        # the ore veins in view: these twinkle (see glintsDue)
        self.litVeins = [i for i in self.litTiles if grid[i][0] == 2 and isinstance(grid[i][2], walls.OreVein)]

    def redrawLitTiles(self, grid, rooms, playerDirection, playerPosition, visionRange, light):
        """Only the light moved: bring the tiles in view (from the last full draw) up to date with the new light."""
        for i in getattr(self, "litTiles", []):
            if grid[i][1] == 1:
                self.refreshTile(grid, i, rooms, playerDirection, playerPosition, visionRange, light)

    def refreshTile(self, grid, i, rooms, playerDirection, playerPosition, visionRange, light):
        """Redraws tile i if its look changed since it was last drawn."""
        signature, lighting = self.tileSignature(grid, i, rooms, playerDirection, playerPosition, visionRange, light)
        if self.tileSigs.get(i) != signature:
            self.paintTile(grid, i, rooms, playerDirection, lighting)
            self.tileSigs[i] = signature

    def drawLitTile(self, grid, i, rooms, playerDirection, playerPosition, visionRange, light):
        """Redraws tile i whatever its signature says."""
        signature, lighting = self.tileSignature(grid, i, rooms, playerDirection, playerPosition, visionRange, light)
        self.paintTile(grid, i, rooms, playerDirection, lighting)
        self.tileSigs[i] = signature

    def crackedPicture(self, picture, piece, kind):
        """A spawner's or warcamp chest's picture with the cracks its hits made (expansion.crack: piece.brokenPoints),
        drawn like a wall's: each chipped pixel of the picture is its own color darkened by 100. Pixels where the
        picture is see-through (the floor shows) stay as they are. Cached per piece and crack count."""
        points = getattr(piece, "brokenPoints", None)
        if not points:
            return picture
        cache = self.__dict__.setdefault("crackCache", {})
        key = (id(piece), kind, len(points), self.tileSize)
        hit = cache.get(key)
        if hit is not None and hit[0] is piece:
            return hit[1]
        out = picture.copy()
        w, h = out.get_size()
        for px, py in points:
            if 0 <= px < w and 0 <= py < h:
                r, g, b, a = out.get_at((px, py))
                if a > 0:
                    out.set_at((px, py), (max(0, r - 100), max(0, g - 100), max(0, b - 100), a))
        if len(cache) > 512:
            cache.clear()
        cache[key] = (piece, out)
        return out

    def plantPicture(self, plant):
        """A plant's picture for its stage (plants.Plant.stage): a sprout, a young plant (growing), or full grown
        (wild, or ripe), with seed pods when it has gone to seed."""
        if plant.staged and not plant.ready:
            return self.sprites["sprouts" if plant.stage == "planted" else "youngPlants"].get(plant.kind)
        picture = self.sprites["plants"].get(plant.kind)
        if picture is not None and plant.staged and plant.stage == "seed":
            picture = picture.copy()
            picture.blit(self.sprites["seedPods"], (0, 0))
        return picture

    def tileLighting(self, i, x, y, playerPosition, visionRange, light):
        """(dither level, fire tint alpha) for a tile in view: the brighter of your light and any fire's."""
        offsetX, offsetY, reach = light
        lightX = playerPosition % self.rowLength + offsetX
        lightY = playerPosition // self.rowLength + offsetY
        level = self.lightLevel(x, y, lightX, lightY, visionRange * reach)
        alpha = 0
        fire = getattr(self, "fireLight", {}).get(i)
        if fire is not None:  # firelight: whichever light is brighter here wins
            fireLevel, distance = self.fireLevel(x, y, fire)
            level = None if level is None or fireLevel is None else min(level, fireLevel)
            alpha = int(FIRE_TINT_ALPHA * max(0.0, 1 - distance / (fire[1] + 1)))
        return level, alpha

    def tileSignature(self, grid, i, rooms, playerDirection, playerPosition, visionRange, light):
        """(signature, lighting) for tile i. The signature holds everything paintTile's result depends on, so two
        equal signatures always mean the same picture."""
        tile = grid[i]
        kind, visibility = tile[0], tile[1]
        memorized = visibility == 2
        obj = tile[2] if len(tile) > 2 else None
        blood = self.blood.get(i) if self.blood else None
        extra = None
        if kind == 1:
            extra = (playerDirection, getattr(obj, "look", None), getattr(obj, "kind", None))
        elif kind == 2:
            glint = self.glintPhase(i, self.frameTicks) if not memorized and isinstance(obj, walls.OreVein) else None
            extra = (obj.name, len(obj.brokenPoints), getattr(obj, "corruptedBy", None), getattr(obj, "paint", None), glint)
        elif kind == 3:
            extra = (getattr(obj, "look", None), len(getattr(obj, "brokenPoints", ())))
        elif kind == 9:
            extra = obj.look
        elif kind == 7:
            extra = (obj.id, obj.hp, obj.claimed)
        elif kind == 8:
            extra = (obj.kind, getattr(obj, "stage", None), obj.ready if obj.staged else None)
        elif kind == expansion.CAMP:
            extra = (obj.kind, obj.hp, len(getattr(obj, "brokenPoints", ())),
                     self.frameTicks // sprites.BONFIRE_FRAME_MS % len(self.sprites["bonfire"]) if obj.kind == "bonfire" else None)
        elif kind == 5 and not memorized and obj is not None:
            extra = (obj.name, getattr(obj, "look", None), i in getattr(self, "smokeHere", {}),
                     sprites.shardFrameFor(getattr(self, "lightTime", 0.0)) if obj.name == "Unsealed" else None)
        lighting = None
        if not memorized and kind not in self.LIGHT_EXEMPT:
            lighting = self.tileLighting(i, i % self.rowLength, i // self.rowLength, playerPosition, visionRange, light)
        signature = (kind, visibility, id(obj), self.roomOf(i, rooms), blood,
                     self.bloodDry.get(i) if blood else None, extra, lighting)
        return signature, lighting

    def paintTile(self, grid, i, rooms, playerDirection, lighting):
        ts = self.tileSize
        memorized = grid[i][1] == 2
        x = i % self.rowLength
        y = i // self.rowLength
        self.drawTile(grid, i, x, y, rooms, playerDirection, memorized)
        # Dithered light only on tiles in view (remembered tiles stay as they are). The player, enemies,
        # chests and the door back up are never dithered so they stand out; pits are part of the floor, so they are.
        if lighting is not None:
            level, alpha = lighting
            if alpha > 0:
                self.mapSurface.blit(self.fireTint(alpha), (x * ts, y * ts))
            if level is not None and self.shades:
                self.mapSurface.blit(self.shades[(level, x % 2, y % 2)], (x * ts, y * ts))

    def fireLevel(self, x, y, fire):
        """(dither level, distance) for tile x, y in the light of fire: (its position, its light radius). Each fire's
        light sways like yours (lightShape, with the same Light Style), on its own timing so they don't all move together."""
        source, radius = fire
        offsetX, offsetY, reach = self.lightShape(self.lightTime + (source % 97) * 0.37, getattr(self, "lightStyleNow", None))
        fx, fy = source % self.rowLength + offsetX, source // self.rowLength + offsetY
        distance = math.hypot(x - fx, y - fy)
        return self.lightLevel(x, y, fx, fy, (radius + 0.5) * reach), distance

    def fireTint(self, alpha):
        cache = self.__dict__.setdefault("fireTints", {})
        alpha = alpha // 6 * 6  # a handful of steps is plenty, and keeps the cache small
        if (alpha, self.tileSize) not in cache:
            cache[(alpha, self.tileSize)] = self.tint(FIRE_TINT, alpha)
        return cache[(alpha, self.tileSize)]

    def drawTile(self, grid, i, x, y, rooms, playerDirection, memorized):
        ts = self.tileSize
        match grid[i][0]:
            case 1:  # Player: the Torchbearer facing the way it last moved, on the floor it stands on
                self.floorFill(i, rooms, memorized, x, y)
                standingIn = grid[i][2] if len(grid[i]) > 2 else None
                if standingIn is not None and hasattr(standingIn, "look"):  # on an item pile: it's under your feet
                    self.mapSurface.blit(self.sprites["piles"][standingIn.look], (x * ts, y * ts))
                self.mapSurface.blit(self.sprites["player"][playerDirection], (x * ts, y * ts))
                if standingIn is not None and hasattr(standingIn, "kind"):  # in a plant: it's drawn over you, see-through
                    picture = self.plantPicture(standingIn)
                    if picture is not None:
                        picture = picture.copy()
                        picture.set_alpha(150)
                        self.mapSurface.blit(picture, (x * ts, y * ts))
            case 2:  # Wall
                w = grid[i][2]
                color = self.roomWallColor(i, rooms, memorized) if isinstance(w, walls.OreVein) else self.wallColor(w.name, memorized)
                self.mapSurface.blit(self.drawWall(w, color, memorized, None if memorized else i), (x * ts, y * ts))
            # Chests and doors: the floor first (it shows through the pictures' transparent pixels and
            # shadows), then the picture. They keep their full color even when remembered.
            case 3:  # Chest: walnut, mahogany or burnt umber (the same on every floor), or an Expansion warcamp chest
                self.floorFill(i, rooms, memorized, x, y)
                look = getattr(grid[i][2], "look", None)
                if look in self.sprites["campChests"]:
                    self.mapSurface.blit(self.crackedPicture(self.sprites["campChests"][look], grid[i][2], ("chest", look)), (x * ts, y * ts))
                else:
                    self.mapSurface.blit(self.sprites["chests"][sprites.chestColorFor(i)], (x * ts, y * ts))
            case 9:  # An item pile: one of the pile pictures, picked when the pile was made
                self.floorFill(i, rooms, memorized, x, y)
                self.mapSurface.blit(self.sprites["piles"][grid[i][2].look], (x * ts, y * ts))
            case 4:  # Door to the next level: a pit in the floor, randomly an open pit or a collapsed grave
                floor = self.floorColor(i, rooms, memorized)
                self.fillTile(floor, x, y)
                self.mapSurface.blit(self.pitSprite(sprites.pitStyleFor(i), floor), (x * ts, y * ts))
            case 7:  # A set-up crafting station (kept in full color when remembered, like chests)
                self.floorFill(i, rooms, memorized, x, y)
                station = grid[i][2]
                picture = self.sprites["stations"].get(station.id)
                if picture is not None:
                    self.mapSurface.blit(picture, (x * ts, y * ts))
                if station.claimed and station.hp < station.maxHp:  # a damage bar along the bottom
                    pygame.draw.rect(self.mapSurface, (40, 10, 10), pygame.Rect(x * ts + 1, y * ts + ts - 2, ts - 2, 1))
                    pygame.draw.rect(self.mapSurface, self.color("enemy"), pygame.Rect(x * ts + 1, y * ts + ts - 2, max(1, (ts - 2) * station.hp // station.maxHp), 1))
            case 8:  # A plant: the floor, then the plant (kept in full color when remembered, like chests)
                self.floorFill(i, rooms, memorized, x, y)
                picture = self.plantPicture(grid[i][2])
                if picture is not None:
                    self.mapSurface.blit(picture, (x * ts, y * ts))
            case expansion.CAMP:  # A spawner or a bonfire (kept in full color when remembered, like stations)
                self.floorFill(i, rooms, memorized, x, y)
                piece = grid[i][2]
                if piece.kind == "bonfire":
                    frame = self.frameTicks // sprites.BONFIRE_FRAME_MS % len(self.sprites["bonfire"])
                    self.mapSurface.blit(self.sprites["bonfire"][frame], (x * ts, y * ts))
                else:  # (cracked as it's hit, like a wall: no damage bar)
                    self.mapSurface.blit(self.crackedPicture(self.sprites["spawner"], piece, ("spawner",)), (x * ts, y * ts))
            case 6:  # Door back to the previous level
                self.floorFill(i, rooms, memorized, x, y)
                self.mapSurface.blit(self.sprites["doorUp"], (x * ts, y * ts))
            case 5 if not memorized:  # Enemy (enemies are not remembered)
                self.floorFill(i, rooms, memorized, x, y)
                name = grid[i][2].name if len(grid[i]) > 2 else ""
                if i in getattr(self, "smokeHere", {}):
                    pass  # hidden in smoke: only the smoke shows
                elif name == "Unsealed":
                    frame = sprites.shardFrameFor(getattr(self, "lightTime", 0.0))
                    self.mapSurface.blit(self.sprites["unsealed"][frame], (x * ts, y * ts))
                elif (name, getattr(grid[i][2], "look", None)) in self.sprites["factions"]:  # an Expansion faction's colors
                    self.mapSurface.blit(self.sprites["factions"][(name, grid[i][2].look)], (x * ts, y * ts))
                elif name in self.sprites["enemies"]:
                    self.mapSurface.blit(self.sprites["enemies"][name], (x * ts, y * ts))
                else:  # an enemy with no picture yet: a plain square
                    self.fillTile(self.color("enemy"), x, y)
            case _:  # Floor
                self.floorFill(i, rooms, memorized, x, y)
