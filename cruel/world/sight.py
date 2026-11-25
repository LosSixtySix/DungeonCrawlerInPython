"""
What can be seen from a tile: symmetric shadowcasting, picked on the "How Far You See" sheet
(https://claude.ai/artifact/5JWTznZ14fbJfcScRaeKvt).

  Open tiles   one is seen if the straight line from the middle of the origin to its middle passes through no
               blocking tile (each a square). The same line goes both ways, so sight is symmetric: if you can see a
               tile, someone standing there can see you. A line that only grazes the corner of one blocker gets
               past it; one that would pass between two blockers touching at a corner (a diagonal wall) doesn't,
               the way you can't walk between them.
  Blockers     anything that blocks sight is seen when the line to its middle is clear, the same as an open tile:
               so a unit (which blocks sight for anyone else) is seen symmetrically, if you can see an enemy it can
               see you. A wall (wholeFace) is also seen when it borders an open tile you can see (one of the 8 round
               it), so a wall in view shows its whole face.

It's worked out by shadowcasting: each eighth of the circle round the origin is scanned a row at a time going out,
keeping the shadows (ranges of slope, worked out exactly from each blocker square's corners) cast by the blockers in
the rows already passed. An open tile is seen if the slope to its middle is strictly inside no shadow. Shadows that
meet are joined, so nothing gets through where two blockers touch. A line straight along a diagonal (the edge of an
eighth) passes through a corner at every step, so there each corner is checked for a pinch: the two tiles across it
both blockers, one of them in the next eighth over. Slopes are kept as whole-number fractions, so it's exact.
Everything is within reach (a rounded circle: dx * dx + dy * dy <= reach * reach + reach).
"""

# the eight eighths of the circle: (column step x, column step y, row step x, row step y)
OCTANTS = ((1, 0, 0, 1), (0, 1, 1, 0), (0, -1, 1, 0), (-1, 0, 0, 1), (-1, 0, 0, -1), (0, -1, -1, 0), (0, 1, -1, 0), (1, 0, 0, -1))


def fieldOfView(origin, reach, rowLength, rowCount, blocks, wholeFace=None, looked=None):
    """The set of tiles seen from origin out to reach. blocks(spot) says whether a tile blocks sight (the map's
    edge always does); wholeFace(spot), whether a blocker shows its whole face (a wall does, a unit doesn't; without
    it, every blocker does). The origin is always seen, whatever it is. looked: a set to fill with every tile
    that was asked about (the answer depends on those alone, so it's the same until one of them changes)."""
    originColumn, originRow = origin % rowLength, origin // rowLength
    limit = reach * reach + reach
    openSeen = {origin}
    blockersSeen = set()
    known = {origin: False}  # spot: does it block (worked out once)

    def blocked(x, y):
        if not (0 <= x < rowLength and 0 <= y < rowCount):
            return True
        spot = x + y * rowLength
        found = known.get(spot)
        if found is None:
            found = known[spot] = blocks(spot)
        return found

    for columnX, columnY, rowX, rowY in OCTANTS:
        shadows = []  # joined shadows in slope order: [low top, low bottom, high top, high bottom] (bottoms > 0)
        diagonalPinched = False
        for row in range(1, reach + 1):
            step = row - 1  # (the corner the diagonal passes on its way into this row)
            if not diagonalPinched and \
                    blocked(originColumn + step * columnX + row * rowX, originRow + step * columnY + row * rowY) and \
                    blocked(originColumn + row * columnX + step * rowX, originRow + row * columnY + step * rowY):
                diagonalPinched = True
            rowShadows = []
            for column in range(row + 1):
                if column * column + row * row > limit:
                    break
                x = originColumn + column * columnX + row * rowX
                y = originRow + column * columnY + row * rowY
                isBlocker = blocked(x, y)
                if isBlocker:
                    rowShadows.append((2 * column - 1, 2 * row + 1, 2 * column + 1, 2 * row - 1))
                if column == row and diagonalPinched:
                    continue
                for lowTop, lowBottom, highTop, highBottom in shadows:  # (strictly inside one: in shadow)
                    if lowTop * row < column * lowBottom and column * highBottom < highTop * row:
                        break
                else:  # (the line to its middle is clear)
                    if isBlocker:
                        if 0 <= x < rowLength and 0 <= y < rowCount:
                            blockersSeen.add(x + y * rowLength)
                    else:
                        openSeen.add(x + y * rowLength)
            for shadow in rowShadows:  # (a blocker shadows the rows behind it, not its own)
                shadows = joined(shadows, shadow)
            if shadows and shadows[0][0] < 0 and shadows[0][2] > shadows[0][3]:
                break  # (this whole eighth is in shadow, its edges too: a line along an edge can still get by)
    seen = openSeen | blockersSeen
    around = set()
    for spot in openSeen:
        x, y = spot % rowLength, spot // rowLength
        for nearX in (x - 1, x, x + 1):
            for nearY in (y - 1, y, y + 1):
                around.add((nearX, nearY))
    for nearX, nearY in around:  # the blockers bordering what you see
        if 0 <= nearX < rowLength and 0 <= nearY < rowCount and \
                (nearX - originColumn) ** 2 + (nearY - originRow) ** 2 <= limit and blocked(nearX, nearY) and                 (wholeFace is None or wholeFace(nearX + nearY * rowLength)):
            seen.add(nearX + nearY * rowLength)
    if looked is not None:
        looked.update(known)
    return seen


def joined(shadows, shadow):
    """shadows with shadow added, overlapping or touching ones joined into one (fractions compared exactly)."""
    lowTop, lowBottom, highTop, highBottom = shadow
    kept = []
    for otherLowTop, otherLowBottom, otherHighTop, otherHighBottom in shadows:
        if otherLowTop * highBottom <= highTop * otherLowBottom and lowTop * otherHighBottom <= otherHighTop * lowBottom:
            if otherLowTop * lowBottom < lowTop * otherLowBottom:
                lowTop, lowBottom = otherLowTop, otherLowBottom
            if highTop * otherHighBottom < otherHighTop * highBottom:
                highTop, highBottom = otherHighTop, otherHighBottom
        else:
            kept.append((otherLowTop, otherLowBottom, otherHighTop, otherHighBottom))
    kept.append((lowTop, lowBottom, highTop, highBottom))
    kept.sort(key=lambda found: found[0] / found[1])
    return kept
