import re

import pygame

import enemies
import events
import loot
import recipes
import relics
import resources
import wall

"""
The developer console. ~ (the key left of 1) opens and closes it while playing. Type a command and press Enter;
/help lists them. The console only adds lines to its own log: listing enemies doesn't reveal any on the map.

While it's open every key goes to the console, so nothing you type moves the player or opens windows.
Up/Down go through commands you've typed before, PgUp/PgDn and the mouse wheel scroll the log, Esc or ~ closes it.

Autofill: the best match for what you're typing (a command, or an item id after /give) shows in grey after it,
with the other matches beside it. Tab fills in the match; pressing Tab again moves on to the next one.
"""

LOG_LIMIT = 400  # oldest lines are dropped past this many
PLAY_TURN_MS = 150  # /play: how often a turn passes, unless a speed is given


def snakeCase(name):
    """GoblinChief -> goblin_chief"""
    return re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()


def oreFloorIds():
    """{"copper_lode": "Copper Lode", ...}: the ids /orefloor takes."""
    return {name.lower().replace(" ", "_"): name for name in wall.ORE_FLOORS}


def itemCatalog():
    """Everything /give can make: {id: (group, name, kind)}. kind is "material", "gold", "relic" or "recipe"."""
    catalog = {"gold": ("Gold", "Gold", "gold")}
    for materialId, (name, group, _) in resources.MATERIALS.items():
        catalog[materialId] = (f"Materials: {group}", name, "material")
    for recipe in recipes.RECIPES:
        if recipe.kind == "item":
            catalog[recipe.id] = ("Gear", recipe.name, "recipe")
        elif recipe.kind == "potion" and recipe.amount == 1:  # (x2) recipes make the same potion as another one
            catalog[recipe.id] = ("Potions", recipe.name, "recipe")
    for relicId, info in relics.RELICS.items():
        catalog[relicId] = ("Relics", info["name"], "relic")
    return catalog


ENEMY_CLASSES = enemies.lowerFloorEnemies + [enemies.Unsealed, enemies.FireGiant] + enemies.organizers


def enemyCatalog():
    """{id: enemy class} for every kind of enemy."""
    return {snakeCase(cls.__name__): cls for cls in ENEMY_CLASSES}


class DevConsole():
    def __init__(self, gm):
        self.gm = gm
        self.open = False
        self.text = ""          # what's being typed
        self.log = []           # (style, text): style is "input", "info", "good", "error" or "head"
        self.scroll = 0         # lines scrolled up from the bottom
        self.history = []       # commands typed before, newest last
        self.historyIndex = None
        self.tabbing = None     # (matches, index) while Tab is stepping through the autofill matches
        self.commands = {
            "help": (self.cmdHelp, "/help", "Lists the commands"),
            "give": (self.cmdGive, "/give <id> [amount]", "Adds an item, material or gold (ids: /items). Also /additem"),
            "items": (self.cmdItems, "/items [filter]", "Lists every item id, or only those matching filter"),
            "enemy": (self.cmdEnemy, "/enemy", "Lists every kind of enemy and its id. Also /enemies"),
            "peaceful": (self.cmdPeaceful, "/peaceful [on|off]", "Enemies ignore you and never attack (toggles with no word)"),
            "reveal": (self.cmdReveal, "/reveal [on|off]", "See the whole floor, enemies included (toggles with no word)"),
            "play": (self.cmdPlay, "/play [off|ms]", "Turns pass on their own so you can watch (Esc or /play stops; ms per turn, default 150)"),
            "events": (self.cmdEvents, "/events", "Lists the floor events and this floor's event, if any"),
            "event": (self.cmdEvent, "/event <id>", "Starts a floor event now (ids: /events)"),
            "orefloor": (self.cmdOreFloor, "/orefloor <type> [mother]", "Makes the next new floor an ore floor (types: /orefloor)"),
            "moltenvault": (self.cmdMoltenVault, "/moltenvault", "Makes the next new floor All Gold with the Molten Vault theme"),
            "scorched": (self.cmdScorched, "/scorched", "Goes straight to a new Scorched Depths floor (starts a new track)"),
            "patience": (self.cmdPatience, "/patience", "Skips the 5 minute wait: on the first floor's center tile, the floor gives way"),
            "clear": (self.cmdClear, "/clear", "Clears the console"),
        }
        self.aliases = {"additem": "give", "add": "give", "enemies": "enemy", "item": "items", "aggro": "peaceful", "map": "reveal", "seeall": "reveal", "?": "help"}
        self.arguments = {"give": lambda: list(itemCatalog()), "peaceful": lambda: ["on", "off"],
                          "reveal": lambda: ["on", "off"], "play": lambda: ["off"],
                          "event": lambda: list(events.EVENTS),
                          "orefloor": lambda: list(oreFloorIds())}  # what autofill offers
        self.write("info", "Developer console. Type /help for the commands")

    # ------------------------------------------------------------------ open / close

    def toggle(self):
        self.open = not self.open
        self.text = ""
        self.historyIndex = None
        self.tabbing = None
        self.scroll = 0
        if self.open:
            pygame.key.start_text_input()
        else:
            pygame.key.stop_text_input()
        self.gm.change = True

    # ------------------------------------------------------------------ input

    def onTextInput(self, event):
        if not self.open:
            return
        typed = event.text.replace("`", "").replace("~", "")  # the key that opens the console isn't typed
        if typed:
            self.text += typed
            self.tabbing = None
            self.gm.change = True

    def onKey(self, event):
        """Every key while the console is open comes here."""
        key = event.key
        if key == pygame.K_TAB:
            self.autofill()
            self.gm.change = True
            return
        self.tabbing = None
        if key in (pygame.K_ESCAPE, pygame.K_BACKQUOTE):
            self.toggle()
        elif key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            self.submit()
        elif key == pygame.K_BACKSPACE:
            self.text = self.text[:-1]
        elif key == pygame.K_UP and self.history:
            self.historyIndex = len(self.history) - 1 if self.historyIndex is None else max(0, self.historyIndex - 1)
            self.text = self.history[self.historyIndex]
        elif key == pygame.K_DOWN and self.historyIndex is not None:
            self.historyIndex += 1
            if self.historyIndex >= len(self.history):
                self.historyIndex, self.text = None, ""
            else:
                self.text = self.history[self.historyIndex]
        elif key == pygame.K_PAGEUP:
            self.scrollBy(10)
        elif key == pygame.K_PAGEDOWN:
            self.scrollBy(-10)
        self.gm.change = True

    # ------------------------------------------------------------------ autofill

    def matches(self):
        """[(full line it would become, the word it fills in)] for what's typed so far, best first. The command
        is the first word; after it, commands in self.arguments offer their second word (e.g. /give's item ids)."""
        text = self.text
        if not text.strip():
            return []
        slash = "/" if text.startswith("/") else ""
        body = text[len(slash):]
        if " " not in body:  # still typing the command
            word = body.lower()
            names = [n for n in list(self.commands) + list(self.aliases) if n.isalpha()]
            return [(f"{slash}{n} ", n) for n in names if n.startswith(word)]
        command, _, rest = body.partition(" ")
        name = self.aliases.get(command.lower(), command.lower())
        if name not in self.arguments or " " in rest.lstrip():  # (no autofill past the second word, e.g. /give's amount)
            return []
        word = rest.strip().lower()
        options = self.arguments[name]()
        starts = [o for o in options if o.startswith(word)]
        inside = [o for o in options if word and word in o and o not in starts]  # "sword" still finds iron_sword
        return [(f"{slash}{command} {o}" + (" " if name == "give" else ""), o) for o in starts + inside]

    def autofill(self):
        """Tab: fill in the best match, or, pressed again, swap it for the next one."""
        if self.tabbing is not None:
            matches, index = self.tabbing
            index = (index + 1) % len(matches)
        else:
            matches, index = self.matches(), 0
            if not matches:
                return
        self.tabbing = (matches, index)
        self.text = matches[index][0]

    def scrollBy(self, lines):
        self.scroll = max(0, min(len(self.log) - 1, self.scroll + lines))
        self.gm.change = True

    def write(self, style, text):
        self.log.append((style, text))
        del self.log[:-LOG_LIMIT]

    def submit(self):
        line = self.text.strip()
        self.text = ""
        self.historyIndex = None
        self.scroll = 0
        if not line:
            return
        if not self.history or self.history[-1] != line:
            self.history.append(line)
        self.write("input", "> " + line)
        words = line.lstrip("/").split()
        if not words:
            return
        name = words[0].lower()
        name = self.aliases.get(name, name)
        if name not in self.commands:
            self.write("error", f"Unknown command \"{words[0]}\". Type /help")
            return
        self.commands[name][0](words[1:])

    # ------------------------------------------------------------------ commands

    def cmdHelp(self, _args):
        self.write("head", "Commands")
        for _, usage, about in self.commands.values():
            self.write("info", f"  {usage:<22} {about}")
        self.write("info", "  Tab: autofill   Up/Down: earlier commands   PgUp/PgDn or wheel: scroll   Esc or ~: close")

    def cmdItems(self, args):
        filter = " ".join(args).lower()
        group = None
        shown = 0
        for itemId, (itemGroup, name, _) in itemCatalog().items():
            if filter and filter not in itemId and filter not in name.lower() and filter not in itemGroup.lower():
                continue
            if itemGroup != group:
                group = itemGroup
                self.write("head", group)
            self.write("info", f"  {itemId:<26} {name}")
            shown += 1
        if not shown:
            self.write("error", f"No items match \"{filter}\"")

    def cmdEnemy(self, _args):
        self.write("head", "Enemies")
        for enemyId, cls in enemyCatalog().items():
            enemy = cls()
            self.write("info", f"  {enemyId:<20} {loot.displayName(enemy.name):<20} HP {enemy.hp:<3} Damage {enemy.damage}")

    def cmdGive(self, args):
        if not args:
            self.write("error", "Usage: /give <id> [amount]")
            return
        itemId = args[0].lower()
        amount = 1
        if len(args) > 1:
            if not args[1].isdigit() or int(args[1]) < 1:
                self.write("error", f"\"{args[1]}\" isn't an amount")
                return
            amount = int(args[1])
        catalog = itemCatalog()
        if itemId not in catalog:
            self.write("error", f"No item \"{itemId}\". Type /items to see the ids")
            return
        _, name, kind = catalog[itemId]
        player = self.gm.player
        if kind == "gold":
            player.gold += amount
            self.write("good", f"+{amount} Gold")
        elif kind == "material":
            added = player.addMaterial(itemId, amount)
            message = f"+{added} {name}"
            self.write("good" if added == amount else "error", message if added == amount else message + " (pouch full)")
        else:
            added = 0
            for _ in range(amount):
                if not player.addItemToInventory(self.makeItem(itemId, kind)):
                    break
                added += 1
            if added == amount:
                self.write("good", f"+{added} {name}")
            else:
                self.write("error", f"+{added} {name} (inventory full)")
        self.gm.change = True

    def makeItem(self, itemId, kind):
        if kind == "relic":
            return relics.make(itemId)
        recipe = recipes.RECIPES_BY_ID[itemId]
        if recipe.kind == "potion":
            item = recipe.makeItem(0, 0)
            item.recipeId = recipe.id
            return item
        return recipe.build("Common")

    def cmdPeaceful(self, args):
        gm = self.gm
        if args and args[0].lower() in ("on", "off"):
            gm.peaceful = args[0].lower() == "on"
        elif args:
            self.write("error", "Usage: /peaceful [on|off]")
            return
        else:
            gm.peaceful = not gm.peaceful
        if gm.peaceful:  # anything already chasing you forgets where you are
            for position in gm.EnemyPositions:
                tile = gm.grid.get(position)
                if tile and tile[0] == 5 and len(tile) > 2:
                    tile[2].lastPlayerPosition = None
        self.write("good", "Peaceful: enemies ignore you" if gm.peaceful else "Peaceful off: enemies hunt you again")

    def cmdEvents(self, _args):
        self.write("head", f"Floor events ({events.EVENT_CHANCE:.0%} of floors from floor {events.FIRST_FLOOR}, one picked at random)")
        for eventId, event in events.EVENTS.items():
            self.write("info", f"  {eventId:<20} {event['name']:<20} {event.get('description', '')}")
        current = self.gm.floorEvents.get(self.gm.level)
        if current is None:
            self.write("info", "  This floor has no event")
        elif current["active"]:
            self.write("good", f"  This floor: {events.name(current['id'])} (active)")
        else:
            self.write("good", f"  This floor: {events.name(current['id'])} (in {current['turnsLeft']} turns)")

    def cmdEvent(self, args):
        if not args or args[0].lower() not in events.EVENTS:
            if args:
                self.write("error", f"No event \"{args[0]}\"")
            return self.cmdEvents(args)
        eventId = args[0].lower()
        gm = self.gm
        gm.floorEvents[gm.level] = {"id": eventId, "turnsLeft": 0, "active": True}
        gm.messageBools["eventMessage"] = True
        gm.painter.fade = 255
        gm.change = True
        self.write("good", f"{events.name(eventId)} has started on this floor")

    def cmdOreFloor(self, args):
        ids = oreFloorIds()
        if not args or args[0].lower() not in ids:
            if args:
                self.write("error", f"No ore floor \"{args[0]}\"")
            self.write("head", "Ore floors (add \"mother\" for a Motherlode)")
            for floorId, name in ids.items():
                self.write("info", f"  {floorId:<20} {name} (from floor {wall.ORE_FLOORS[name]['first']})")
            return
        name = ids[args[0].lower()]
        motherlode = len(args) > 1 and args[1].lower() in ("mother", "motherlode")
        self.gm.forcedOreFloor = (name, motherlode)
        self.write("good", f"The next new floor will be {'a Motherlode ' if motherlode else ''}{name}. Take the stairs down")

    def cmdReveal(self, args):
        gm = self.gm
        if args and args[0].lower() in ("on", "off"):
            gm.revealMap = args[0].lower() == "on"
        elif args:
            self.write("error", "Usage: /reveal [on|off]")
            return
        else:
            gm.revealMap = not getattr(gm, "revealMap", False)
        gm.setPositionsVisible()
        gm.change = True
        self.write("good", "Whole floor revealed" if gm.revealMap else "Back to your own sight (what you saw stays remembered)")

    def cmdPlay(self, args):
        gm = self.gm
        word = args[0].lower() if args else None
        if word == "off" or (word is None and getattr(gm, "autoPlay", None) is not None):
            gm.autoPlay = None
            self.write("good", "Stopped: your turn again")
            return
        ms = PLAY_TURN_MS
        if word not in (None, "on"):
            try:
                ms = max(10, int(word))
            except ValueError:
                self.write("error", "Usage: /play [off|ms per turn]")
                return
        gm.autoPlay = {"ms": ms, "next": 0}
        self.write("good", f"Watching: a turn every {ms} ms. Esc or /play stops")

    def cmdMoltenVault(self, _args):
        self.gm.forceMoltenVault()
        self.write("good", "The next new floor will be an All Gold Molten Vault. Take the stairs down, then break 10 gold walls")

    def cmdScorched(self, _args):
        self.gm.enterScorched()
        self.write("good", "Into the Scorched Depths. The Molten Blade is in the chest at the center")

    def cmdPatience(self, _args):
        gameManager = self.gm
        if gameManager.level != 0:
            self.write("error", "Only works on the first floor")
            return
        if gameManager.playerPositionFlat != gameManager.centerTile():
            self.write("error", "Stand on the center tile (where you started) first")
            return
        gameManager.patienceFall()
        self.write("good", f"You fell onto a {gameManager.floorTypeName()}")

    def cmdClear(self, _args):
        self.log = []
        self.scroll = 0

    # ------------------------------------------------------------------ drawing

    def view(self):
        """What the renderer needs, or None while it's closed."""
        if not self.open:
            return None
        if self.tabbing is not None:  # stepping through with Tab: show where we are in the list
            matches, index = self.tabbing
            ghost = ""
            others = [word for _, word in matches[index + 1:] + matches[:index]]
        else:
            matches = self.matches()
            first = matches[0][0] if matches else ""
            ghost = first[len(self.text):] if first.lower().startswith(self.text.lower()) else ""
            others = [word for _, word in matches[1:]]
        return {"log": self.log, "text": self.text, "scroll": self.scroll, "peaceful": self.gm.peaceful,
                "ghost": ghost, "others": others}
