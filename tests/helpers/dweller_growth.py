"""Helpers for the tests of test_dweller_growth.py, shared by its unit, integration and acceptance tests."""
from cruel.entities import enemies
from cruel.world import dwellerwork
from cruel.world import mineshafts
from cruel.world import wall
from tests.helpers.dweller_work import WorkTest


FLOOR, WALL, CHEST, ENEMY, PLANT = 0, 2, 3, 5, 8


class PenTest(WorkTest):
    """An open floor where each test fences pens (PEN_WIDTH x PEN_HEIGHT, the gate in the middle of the top side)
    and puts grubs and farmers in them."""

    def setUp(self):
        super().setUp()
        self.pens = []
        self.plans = []

    def pen(self, left, top):
        inside = frozenset(self.spot(column, row) for column in range(left + 1, left + mineshafts.PEN_WIDTH - 1)
                           for row in range(top + 1, top + mineshafts.PEN_HEIGHT - 1))
        gate = self.spot(left + mineshafts.PEN_WIDTH // 2, top)
        fence = set()
        for column in range(left, left + mineshafts.PEN_WIDTH):
            for row in range(top, top + mineshafts.PEN_HEIGHT):
                spot = self.spot(column, row)
                if spot not in inside and spot != gate:
                    self.wallAt(column, row, wall.PenFence)
                    fence.add(spot)
        pen = {"fence": fence, "inside": inside, "gate": gate}
        self.pens.append(pen)
        return pen

    def grub(self, spot, pen, grown=True):
        grub = enemies.DewGrub(grown=grown)
        grub.pen = pen["inside"]
        self.game.grid[spot] = [ENEMY, 1, grub]
        self.game.EnemyPositions.add(spot)
        return grub

    def fill(self, pen, count, grown=True):
        """count grubs in the pen, filling it from the back."""
        spots = sorted(pen["inside"], reverse=True)[:count]
        return [self.grub(spot, pen, grown) for spot in spots]

    def farmer(self, column, row):
        farmer = self.worker(column, row, work="farm")
        farmer.fields = {}
        farmer.pens = self.pens
        farmer.plans = self.plans
        return farmer

    def grubsIn(self, pen):
        return [grub for spot, grub in dwellerwork.grubsHere(self.game) if spot in pen["inside"] and grub.pen == pen["inside"]]
