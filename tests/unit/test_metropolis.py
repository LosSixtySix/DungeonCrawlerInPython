"""The Metropolis floor (metropolis.py, dwellers.py): a whole floor that is a city of insectoid Dwellers, its streets,
buildings, chests and themes, when it turns up, and the Dwellers going about their day.

Unit tests; the rest are in tests/integration/test_metropolis.py, tests/acceptance/test_metropolis.py."""
import math
import unittest
from cruel.world import metropolis
from tests.helpers.metropolis import ROW_LENGTH, middleSpot, newCity


class DwellerPlacementTests(unittest.TestCase):
    """Who lives where."""

    def setUp(self):
        self.city = newCity(3)

    def ofRole(self, role):
        """The Dwellers of a role (guards: the city's own, not the Queen's Royal Guards)."""
        return [(spot, dweller) for spot, dweller in self.city.dwellers.items()
                if dweller.role == role and not getattr(dweller, "royal", False)]

    def test_the_numbers_of_each_dweller(self):
        self.assertTrue(metropolis.CITIZENS[0] <= len(self.ofRole("citizen")) <= metropolis.CITIZENS[1])
        self.assertTrue(len(self.ofRole("noble")) <= metropolis.NOBLES[1])
        self.assertTrue(metropolis.GUARD_POSTS[0] <= len(self.ofRole("guard")) <= metropolis.GUARD_POSTS[1])
        self.assertEqual(len(self.ofRole("merchant")), len(self.city.shops))

    def test_guards_stand_at_posts_spread_over_the_roads(self):
        guards = self.ofRole("guard")
        for spot, guard in guards:
            self.assertEqual(guard.home, spot)
            self.assertIn(spot, self.city.roads)
        closest = min(math.hypot(spot % ROW_LENGTH - other % ROW_LENGTH, spot // ROW_LENGTH - other // ROW_LENGTH)
                      for spot, _ in guards for other, _ in guards if other != spot)
        self.assertGreater(closest, 8, "posts are spread out over the city")

    def test_each_merchant_keeps_a_shop_at_its_counter(self):
        counters = {shop["counter"]: shop["kind"] for shop in self.city.shops}
        for spot, merchant in self.ofRole("merchant"):
            self.assertEqual(counters[spot], merchant.shopKind)

    def test_citizens_start_on_streets_and_live_in_houses(self):
        houseTiles = {spot for inside, _ in self.city.houses for spot in inside}
        for spot, citizen in self.ofRole("citizen"):
            self.assertIn(spot, self.city.rooms[metropolis.STREET])
            self.assertIn(citizen.home, houseTiles)

    def test_nobles_live_in_the_noble_quarter(self):
        for spot, noble in self.ofRole("noble"):
            self.assertIn(noble.home, self.city.rooms[metropolis.NOBLE])

    def test_nobody_starts_on_or_beside_you(self):
        playerSpot = middleSpot()
        self.assertNotIn(playerSpot, self.city.dwellers)
        for besideYou in metropolis.neighborsOf(self.city, playerSpot):
            self.assertNotIn(besideYou, self.city.dwellers)


if __name__ == "__main__":
    unittest.main()
