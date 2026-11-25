"""Dead bodies (design sheet: https://claude.ai/artifact/9MVevDdWTLwWfg1bo5AUEk). When a unit dies it leaves its body
instead of an item pile: a Body is an item pile (tile type 9) that looks like the unit, holding whatever it dropped,
and it stays even once it's empty. It lies face down at one of four angles, maybe mirrored, picked when it dies.
Looking through it (opening Items Here on it) rolls it over, onto its side or onto its back, picked at random.
Then it decays: the flesh rots darker and greyer, gives way to the bones, the bones crumble, and at DECAY_TURNS the
body is gone, leaving an item pile: its bones (REMAINS) and anything still on it. gameManager.worldTurn is the clock: it counts every turn
of the run and is saved, so bodies keep rotting on floors you've left."""
import random as rand

from cruel.inventory import items
from cruel.inventory import resources

FRESH_TURNS = 150      # just as it fell...
ROT_FULL_TURNS = 400   # ...rotting until here (its colors darken toward ROT_COLOR)...
SKELETAL_TURNS = 700   # ...the flesh giving way to the bones a pixel at a time until here...
CRUMBLE_TURNS = 900    # ...bones only, until they start to fade...
DECAY_TURNS = 1000     # ...and the body is gone
DECAY_STEP_TURNS = 50  # its look changes this often (each step is a picture of its own)
ROT_COLOR = (62, 66, 48)
ROT_MOST = 0.55        # how far the flesh's colors go toward ROT_COLOR
VARIANTS = 4           # which pixels give way first differs between bodies: one of this many patterns
ROLL_FRAME_MS = 140    # the roll over: each pose it passes through shows this long
POSES = ("down", "side", "up")
REMAINS = ("bone", 1)  # what a body leaves in an item pile when it has decayed all the way: (material, amount)


class Body(items.ItemPile):
    """A dead unit's body, lying on the floor with its loot (items and gold, like any pile)."""

    def __init__(self, unitName, diedTurn, things=None, gold=0):
        super().__init__(things, look=0, gold=gold)
        self.unitName = unitName
        self.diedTurn = diedTurn
        self.quarterTurns = rand.randrange(4)  # how it's turned: clockwise quarter turns
        self.mirrored = rand.random() < 0.5
        self.variant = rand.randrange(VARIANTS)
        self.pose = "down"
        self.rolledAtMs = None  # when it was rolled over (pygame ticks), for the roll animation

    def __getstate__(self):
        """Saved without its roll's start time: the clock starts over when the game loads, so a saved time could
        come round again and play the roll a second time."""
        state = dict(self.__dict__)
        state["rolledAtMs"] = None
        return state

    def age(self, worldTurn):
        return max(0, worldTurn - self.diedTurn)

    def decayed(self, worldTurn):
        return self.age(worldTurn) >= DECAY_TURNS

    def rollOver(self, nowMs):
        """Looting it: a body still face down rolls onto its side or its back. True if it rolled."""
        if self.pose != "down":
            return False
        self.pose = rand.choice(("side", "up"))
        self.rolledAtMs = nowMs
        return True

    def rollPoses(self):
        """The poses the roll passes through: down, then side (and on to up, if that's where it ends)."""
        return ["down", "side"] if self.pose == "side" else ["down", "side", "up"]

    def poseAt(self, nowMs):
        """(the pose to draw, lifted?) at this moment: partway through the roll it's in one of its poses, lifted a
        pixel between them; otherwise its pose."""
        elapsed = None if self.rolledAtMs is None else nowMs - self.rolledAtMs
        poses = self.rollPoses()
        if elapsed is None or elapsed < 0 or elapsed >= len(poses) * ROLL_FRAME_MS:
            return self.pose, False
        step = int(elapsed // ROLL_FRAME_MS)
        aboutToTurn = step < len(poses) - 1 and elapsed % ROLL_FRAME_MS >= ROLL_FRAME_MS / 2
        return poses[step], aboutToTurn

    def rolling(self, nowMs):
        elapsed = None if self.rolledAtMs is None else nowMs - self.rolledAtMs
        return elapsed is not None and 0 <= elapsed < len(self.rollPoses()) * ROLL_FRAME_MS + ROLL_FRAME_MS


def remains(body):
    """The items a body that has decayed all the way leaves in a pile: what was still on it, and its bones."""
    return list(body.items) + [resources.MaterialStack(*REMAINS)]


def isBody(thing):
    return isinstance(thing, Body)


def bodyUnder(thing):
    """The body under a plant that sprouted where something died (gameManager.buryUnderPlant), or None."""
    return getattr(thing, "bodyUnder", None)


def bodyInside(thing):
    """The body inside a wall a burrower died in (gameManager.entomb), or None."""
    return getattr(thing, "bodyInside", None)


def coveredBody(ground):
    """The body hidden by what's on this ground: under a plant (tile type 8) or inside a wall (tile type 2), or None."""
    if len(ground) < 3:
        return None
    if ground[0] == 8:
        return bodyUnder(ground[2])
    if ground[0] == 2:
        return bodyInside(ground[2])
    return None


def decayStep(age):
    """The age a body's picture is drawn at: its age rounded down to a DECAY_STEP_TURNS step."""
    return min(age, DECAY_TURNS) // DECAY_STEP_TURNS * DECAY_STEP_TURNS


def rotShare(age):
    """How far the flesh has rotted toward ROT_COLOR (0 to ROT_MOST)."""
    return max(0.0, min(1.0, (age - FRESH_TURNS) / (ROT_FULL_TURNS - FRESH_TURNS))) * ROT_MOST


def boneShare(age):
    """The share of the flesh that has given way to the bones (0 to 1)."""
    return max(0.0, min(1.0, (age - ROT_FULL_TURNS) / (SKELETAL_TURNS - ROT_FULL_TURNS)))


def fade(age):
    """How solid the body still is: 1, fading to 0 while the bones crumble."""
    if age < CRUMBLE_TURNS:
        return 1.0
    return max(0.0, 1 - (age - CRUMBLE_TURNS) / (DECAY_TURNS - CRUMBLE_TURNS))


def stageName(age):
    if age >= SKELETAL_TURNS:
        return "bones"
    if age >= FRESH_TURNS:
        return "rotting body"
    return "body"


def describe(body, worldTurn):
    """What the body is called where you stand: "Goblin body", "Goblin rotting body", "Goblin bones"."""
    return f"{displayName(body.unitName)} {stageName(body.age(worldTurn))}"


def displayName(unitName):
    return {"Goblin Chieftan": "Goblin Chieftain", "Unsealed": "Unsealed"}.get(unitName, unitName)
