import math
import random as rand

import enemies
import plants
import wall

"""
Organizers: enemies that don't hunt you. Each one picks a spot near it, breaks the walls there to make room,
then builds its pattern out of new walls (in the wall type of the room it's in). When it's done it rests a
while and starts another pattern somewhere else. They only attack you when you're right beside them.

  Spiral Organizer  a square spiral of 3-5 legs, with a 1-wide corridor winding from the outside to the center
  Circle Organizer  a ring of radius 5-6, empty inside, with a one-tile doorway at one of its four compass points
  Square Organizer  a square outline 5-6 tiles wide, empty inside, with a one-tile doorway in the middle of a side
  Plant Organizer   turns a lane of floor into Wood (slowly, WOOD_TURNS a tile), then sows a Game of Life
                    glider of Organizer's Demise aimed at the nearest other Organizer. The glider crawls
                    along the wood, and any other Organizer that touches the plant (any of the 8 tiles
                    around it) becomes a Plant Organizer. Anything else standing in the plant takes
                    magic damage every turn (gameManager.stepDemise).

An organizer never breaks walls of a finished pattern (its own or another organizer's) and picks spots that
don't overlap other patterns, doors, chests or stations. Rings and squares keep their doorway open (it's cleared
like the rest of the room, never built on), and the organizer still builds every wall from a tile it can walk
out from, so it never walls itself in.
"""

BREAK_DAMAGE = 40        # an organizer's hit takes this much HP off a wall (ignoring hardness): one hit for any
                         # plain wall, two for the toughest ore veins
BUILD_TURNS = 2          # turns to build one wall
WOOD_TURNS = 3           # turns to turn one floor tile into Wood
SOW_TURNS = 2            # turns to sow a glider
REST_TURNS = (15, 35)    # a rest between patterns
SITE_TRIES = 30          # spots tried when looking for room for a new pattern
SITE_DISTANCE = (3, 12)  # how far away (in tiles, each way) a new pattern's center can be
STUCK_LIMIT = 25         # turns without getting anything done before it gives up on a pattern
SEARCH_REACH = 30        # how far (in steps) it looks for a way to walk to its work

SPIRAL_LEGS = (3, 5)
CIRCLE_RADIUS = (5, 6)
SQUARE_WIDTH = (5, 6)

DEMISE = "organizers_demise"
GLIDER = [(1, 0), (2, 1), (0, 2), (1, 2), (2, 2)]  # Conway's glider, travelling down and right
GLIDER_PAD = 2           # Wood this far around the glider...
GLIDER_LANE = 3          # ...and this many steps further along the way it travels


# ---------------------------------------------------------------- shapes (offsets from the center)

def spiralShape(legs):
    """A square spiral of walls 2 apart: each leg one longer than the last, so the gap between the arms is a
    1-wide corridor that winds from the outside to the center."""
    walls, x, y = {(-1, -1)}, -1, -1
    for leg in range(legs):
        dx, dy = ((1, 0), (0, 1), (-1, 0), (0, -1))[leg % 4]
        for _ in range(2 + leg):
            x, y = x + dx, y + dy
            walls.add((x, y))
    return walls, set()


def circleShape(radius):
    walls, inside = set(), set()
    for dy in range(-radius - 1, radius + 2):
        for dx in range(-radius - 1, radius + 2):
            d = math.hypot(dx, dy)
            if abs(d - radius) < 0.5:
                walls.add((dx, dy))
            elif d < radius:
                inside.add((dx, dy))
    walls.discard(rand.choice([(radius, 0), (-radius, 0), (0, radius), (0, -radius)]))  # a doorway
    return walls, inside


def squareShape(width):
    low = -(width // 2)
    high = low + width - 1
    walls, inside = set(), set()
    for dy in range(low, high + 1):
        for dx in range(low, high + 1):
            (walls if dx in (low, high) or dy in (low, high) else inside).add((dx, dy))
    middle = low + width // 2
    walls.discard(rand.choice([(middle, low), (middle, high), (low, middle), (high, middle)]))  # a doorway
    return walls, inside


def gliderShape(sx, sy):
    """The glider's cells, pointed (sx, sy), and the Wood it needs: a pad around it and a lane ahead of it."""
    cells = {(sx * (gx - 1), sy * (gy - 1)) for gx, gy in GLIDER}
    wood = set()
    for k in range(GLIDER_LANE + 1):
        for dy in range(-GLIDER_PAD, GLIDER_PAD + 1):
            for dx in range(-GLIDER_PAD, GLIDER_PAD + 1):
                wood.add((k * sx + dx, k * sy + dy))
    return cells, wood


def withMargin(offsets):
    """The offsets and every tile around them (the room an organizer clears for a pattern)."""
    return {(x + dx, y + dy) for x, y in offsets for dx in (-1, 0, 1) for dy in (-1, 0, 1)}


# ---------------------------------------------------------------- helpers

def coords(gm, i):
    return i % gm.rowLength, i // gm.rowLength


def manhattan(gm, i, j):
    (ax, ay), (bx, by) = coords(gm, i), coords(gm, j)
    return abs(ax - bx) + abs(ay - by)


def toTiles(gm, center, offsets):
    """Offsets from center -> tiles, or None if any of them falls off the map."""
    cx, cy = coords(gm, center)
    out = set()
    for dx, dy in offsets:
        if not 0 <= cx + dx < gm.rowLength:
            return None
        t = center + dx + dy * gm.rowLength
        if t not in gm.grid:
            return None
        out.add(t)
    return out


def isDemise(tile):
    return tile[0] == 8 and len(tile) > 2 and tile[2].kind == DEMISE


def reachable(gm, start):
    """Walking distances (over open floor) from start, and the tile each was reached from."""
    dist, came = {start: 0}, {}
    frontier = [start]
    while frontier:
        nxt = []
        for i in frontier:
            if dist[i] >= SEARCH_REACH:
                continue
            for j in gm.neighbors(i):
                if j not in dist and gm.grid[j][0] == 0:
                    dist[j] = dist[i] + 1
                    came[j] = i
                    nxt.append(j)
        frontier = nxt
    return dist, came


def firstStep(came, start, goal):
    while came.get(goal) != start:
        goal = came[goal]
    return goal


# ---------------------------------------------------------------- each turn

def gather(gm):
    """What every organizer on the floor has claimed, worked out once a turn: finished and planned walls
    (never broken by an organizer), every tile any plan covers (no overlapping plans), and where the
    organizers that aren't Plant Organizers are (what the gliders are aimed at)."""
    protected, claimed, targets = set(), set(), []
    for p in gm.EnemyPositions:
        tile = gm.grid.get(p)
        if not tile or tile[0] != 5 or len(tile) < 3 or not isinstance(tile[2], enemies.Organizer):
            continue
        org = tile[2]
        protected |= org.built
        claimed |= org.built
        if org.plan:
            protected |= org.plan["wallSet"]
            claimed |= org.plan["footprint"]
        if not isinstance(org, enemies.PlantOrganizer):
            targets.append(p)
    return {"protected": protected, "claimed": claimed, "targets": targets}


def takeTurn(gm, i, org, context):
    """One organizer's turn. Returns (where it is now, the enemy there): an organizer that touched
    Organizer's Demise comes back as a new Plant Organizer."""
    if not isinstance(org, enemies.PlantOrganizer) and any(gm.inDemise(n) for n in gm.eightAround(i)):
        if gm.grid[i][1] == 1:
            gm.addPopup("Overgrown!", i)
        return i, enemies.PlantOrganizer()
    if gm.playerPositionFlat in gm.neighbors(i):
        gm.hitPlayer(org, i)
        return i, org
    if org.plan is None:
        if org.rest > 0:
            org.rest -= 1
            return wander(gm, i), org
        org.plan = makePlan(gm, i, org, context)
        org.stuck = 0
        if org.plan is None:
            org.rest = 10
            return wander(gm, i), org
        context["claimed"] |= org.plan["footprint"]
        context["protected"] |= org.plan["wallSet"]
    position, finished = work(gm, i, org, context)
    if finished:
        finish(org)
    elif position == i and not org.didSomething:
        org.stuck += 1
        if org.stuck > STUCK_LIMIT:
            finish(org)
    else:
        org.stuck = 0
    return position, org


def overgrow(gm, position):
    """An Organizer at position (still on the grid) becomes a Plant Organizer. True if it changed."""
    tile = gm.grid[position]
    if isinstance(tile[2], enemies.PlantOrganizer):
        return False
    tile[2] = enemies.PlantOrganizer()
    if tile[1] == 1:
        gm.addPopup("Overgrown!", position)
    return True


def finish(org):
    """Done with (or giving up on) a pattern: its walls are kept safe from other organizers."""
    org.built |= org.plan["wallSet"]
    org.plan = None
    org.workOn, org.progress = None, 0
    org.rest = rand.randint(*REST_TURNS)


def wander(gm, i):
    if rand.random() < 0.5:
        return i
    open_ = [j for j in gm.neighbors(i) if gm.grid[j][0] == 0]
    return moveTo(gm, i, rand.choice(open_)) if open_ else i


def moveTo(gm, i, j):
    """Steps from i onto the open floor tile j (the organizer itself was already taken off i)."""
    if i in gm.enemyOccupiedItemSpaces:
        gm.grid[i] = gm.enemyOccupiedItemSpaces.pop(i)
    else:
        gm.grid[i][0] = 0
    gm.grid[j][0] = 5
    return j


# ---------------------------------------------------------------- picking a spot

def makePlan(gm, i, org, context):
    ix, iy = coords(gm, i)
    for _ in range(SITE_TRIES):
        dx = rand.randint(-SITE_DISTANCE[1], SITE_DISTANCE[1])
        dy = rand.randint(-SITE_DISTANCE[1], SITE_DISTANCE[1])
        if abs(dx) + abs(dy) < SITE_DISTANCE[0] or not 0 <= ix + dx < gm.rowLength:
            continue
        center = i + dx + dy * gm.rowLength
        if center not in gm.grid:
            continue
        plan = layOut(gm, center, org, context)
        if plan is not None:
            return plan
    return None


def layOut(gm, center, org, context):
    """The plan for this organizer's pattern at center, or None if it doesn't fit there."""
    plan = {"center": center, "walls": [], "wallSet": set(), "inside": set(), "wood": set(), "cells": set(),
            "skip": set()}
    if org.pattern == "plant":
        cx, cy = coords(gm, center)
        if context["targets"]:
            tx, ty = coords(gm, min(context["targets"], key=lambda t: manhattan(gm, t, center)))
            sx = (1 if tx >= cx else -1) if tx != cx else rand.choice((-1, 1))
            sy = (1 if ty >= cy else -1) if ty != cy else rand.choice((-1, 1))
        else:
            sx, sy = rand.choice((-1, 1)), rand.choice((-1, 1))
        cells, wood = gliderShape(sx, sy)
        plan["cells"], plan["wood"] = toTiles(gm, center, cells), toTiles(gm, center, wood)
        footprint = plan["wood"]
        if footprint is None:
            return None
    else:
        if org.pattern == "spiral":
            walls, inside = spiralShape(rand.randint(*SPIRAL_LEGS))
        elif org.pattern == "circle":
            walls, inside = circleShape(rand.randint(*CIRCLE_RADIUS))
        else:
            walls, inside = squareShape(rand.randint(*SQUARE_WIDTH))
        footprint = toTiles(gm, center, withMargin(walls | inside))
        plan["wallSet"], plan["inside"] = toTiles(gm, center, walls), toTiles(gm, center, inside)
        if footprint is None or plan["wallSet"] is None:
            return None
        plan["walls"] = sorted(plan["wallSet"])
    if footprint & context["claimed"] or gm.playerPositionFlat in footprint:
        return None
    if any(gm.grid[t][0] in (3, 4, 6, 7, 9) for t in footprint):  # no chests, item piles, doors or stations in the way
        return None
    plan["footprint"] = footprint
    plan["clear"] = footprint - plan["wallSet"]
    outside = footprint - plan["wallSet"] - plan["inside"]
    plan["outside"] = outside
    # walls with no outside tile beside them can only be built from inside the shape: they go first,
    # while there's still a gap to walk back out through
    plan["insideOnly"] = {t for t in plan["wallSet"] if not any(n in outside for n in gm.neighbors(t))}
    return plan


# ---------------------------------------------------------------- working on the plan

def work(gm, i, org, context):
    """Does the next bit of work. Returns (position, whether the pattern is finished)."""
    org.didSomething = False
    plan = org.plan
    dist, came = reachable(gm, i)

    # 1. Make room: break the walls and pull up the plants where the pattern goes
    toClear = [t for t in plan["clear"] | plan["wallSet"]
               if (gm.grid[t][0] == 2 and t not in plan["wallSet"] and t not in context["protected"])
               or (gm.grid[t][0] == 8 and not (plan["cells"] and isDemise(gm.grid[t]) and t in plan["cells"]))]
    if toClear:
        return goWork(gm, i, org, toClear, lambda t: gm.neighbors(t), clearTile, dist, came, context), False

    # 2. (Plant Organizer) turn the floor into Wood
    toWood = [t for t in plan["wood"] if plants.floorOf(t, gm.rooms) != "Wood"]
    if toWood:
        return goWork(gm, i, org, toWood, lambda t: [t] + gm.neighbors(t), woodTile, dist, came, context), False

    # 3. Build the walls
    if plan["wallSet"]:
        position, done = build(gm, i, org, dist, came, context)
        return position, done

    # 4. (Plant Organizer) sow the glider
    return sow(gm, i, org, dist, came)


def goWork(gm, i, org, targets, spotsFor, action, dist, came, context):
    """Works on a target it's standing at (one of spotsFor(target)), or walks toward the nearest one."""
    for t in targets:
        if i in spotsFor(t):
            action(gm, i, org, t)
            org.didSomething = True
            return i
    spots = [s for t in targets for s in spotsFor(t) if s in dist]
    if spots:
        return moveTo(gm, i, firstStep(came, i, min(spots, key=lambda s: dist[s])))
    return digToward(gm, i, org, min(targets, key=lambda t: manhattan(gm, i, t)), context)


def digToward(gm, i, org, target, context):
    """No open way to the work: head straight for it, breaking walls that aren't part of a pattern."""
    for j in sorted(gm.neighbors(i), key=lambda j: manhattan(gm, j, target)):
        if manhattan(gm, j, target) >= manhattan(gm, i, target):
            break
        tile = gm.grid[j]
        if tile[0] == 0:
            return moveTo(gm, i, j)
        if tile[0] == 2 and j not in context["protected"]:
            hitWall(gm, i, org, j)
            return i
    return i


def hitWall(gm, i, org, t):
    w = gm.grid[t][2]
    gm.chip(t, i)
    w.brokenPoints |= wall.getRandomPoints((1, gm.tileSize - 1), (1, gm.tileSize - 1), gm.tileSize ** 2 // 3)
    w.hp -= BREAK_DAMAGE
    if w.hp <= 0:
        gm.enemyBrokeWall(t, org)  # it may pocket the wall's materials
    org.didSomething = True
    gm.change = True


def clearTile(gm, i, org, t):
    if gm.grid[t][0] == 2:
        hitWall(gm, i, org, t)
    elif gm.grid[t][0] == 8:
        gm.grid[t] = [0, gm.grid[t][1]]
        gm.change = True


def woodTile(gm, i, org, t):
    if org.workOn != ("wood", t):
        org.workOn, org.progress = ("wood", t), 0
    org.progress += 1
    if org.progress >= WOOD_TURNS:
        for room in gm.rooms.values():
            room.discard(t)
        gm.rooms["Wood"].add(t)
        org.workOn, org.progress = None, 0
        gm.change = True


def escapes(gm, plan, spot, newWall):
    """True if, with a wall at newWall, someone at spot can still walk out of the shape."""
    seen, frontier = {spot}, [spot]
    while frontier:
        s = frontier.pop()
        if s in plan["outside"] or s not in plan["footprint"]:
            return True
        for n in gm.neighbors(s):
            if n not in seen and n != newWall and gm.grid[n][0] not in (2, 7):
                seen.add(n)
                frontier.append(n)
    return False


def build(gm, i, org, dist, came, context):
    plan = org.plan
    todo = []
    for t in plan["walls"]:
        kind = gm.grid[t][0]
        if kind == 2 or t in plan["skip"]:
            continue
        if kind in (3, 4, 6, 7, 9):  # something dropped or placed there since: leave a gap
            plan["skip"].add(t)
            continue
        todo.append(t)
    if not todo:
        return i, True
    choices = []  # (not one of the walls that has to be built from inside, distance, wall, spot)
    for t in todo:
        if gm.grid[t][0] != 0:  # someone standing there (or a plant grew back): not now
            continue
        for s in gm.neighbors(t):
            if s in dist:
                choices.append((t not in plan["insideOnly"], dist[s], t, s))
    if not choices:
        if i in todo:  # standing on the last spot where a wall goes: step off it
            off = [j for j in gm.neighbors(i) if gm.grid[j][0] == 0]
            off.sort(key=lambda j: (j in plan["wallSet"], j not in plan["outside"]))
            return (moveTo(gm, i, off[0]) if off else i), False
        open_ = [t for t in todo if gm.grid[t][0] == 0]
        if open_:
            return digToward(gm, i, org, min(open_, key=lambda t: manhattan(gm, i, t)), context), False
        return i, False
    choices.sort()
    # the first one it can build and still walk out of the shape afterwards (or, if none, the first one)
    _, _, t, s = next((c for c in choices if escapes(gm, plan, c[3], c[2])), choices[0])
    if s != i:
        return moveTo(gm, i, firstStep(came, i, s)), False
    if org.workOn != ("wall", t):
        org.workOn, org.progress = ("wall", t), 0
    org.progress += 1
    org.didSomething = True
    if org.progress >= BUILD_TURNS:
        gm.grid[t] = [2, gm.grid[t][1], gm.createWall(t, gm.rooms)]
        org.workOn, org.progress = None, 0
        gm.change = True
    return i, False


def sow(gm, i, org, dist, came):
    plan = org.plan
    cells = plan["cells"]
    if not cells or all(isDemise(gm.grid[c]) for c in cells):
        return i, True
    if any(gm.grid[c][0] not in (0, 8) and c != i for c in cells):
        return i, False  # someone's in the way: wait
    cx, cy = coords(gm, plan["center"])
    near = [t for t in plan["wood"] if t not in cells and gm.grid[t][0] == 0
            and max(abs(coords(gm, t)[0] - cx), abs(coords(gm, t)[1] - cy)) <= 2]
    if i not in cells and i in plan["wood"] and max(abs(coords(gm, i)[0] - cx), abs(coords(gm, i)[1] - cy)) <= 2:
        if org.workOn != ("sow", plan["center"]):
            org.workOn, org.progress = ("sow", plan["center"]), 0
        org.progress += 1
        org.didSomething = True
        if org.progress >= SOW_TURNS:
            for c in cells:
                gm.grid[c] = [8, gm.grid[c][1], plants.Plant(DEMISE)]
            gm.change = True
            if gm.grid[i][1] == 1:
                gm.addPopup("Sown!", i)
            return i, True
        return i, False
    spots = [t for t in near if t in dist]
    if spots:
        return moveTo(gm, i, firstStep(came, i, min(spots, key=lambda t: dist[t]))), False
    return wander(gm, i), False
