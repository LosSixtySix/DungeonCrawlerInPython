"""The Expansion event: goblin factions, their huts, spawners, bonfires and what goblins carry (expansion.py).

Unit tests; the rest are in tests/integration/test_expansion.py."""
import unittest
from cruel.world import expansion


class HutShapeTests(unittest.TestCase):
    """The hut layout: walls, entrances, the room inside."""

    def test_a_hut_wall_ring_leaves_out_its_corners_and_doors(self):
        self.assertEqual(len(expansion.hutWalls(())), 24 - 4)
        hutWithDoors = expansion.hutWalls(expansion.HUT_SIDES)
        self.assertEqual(len(hutWithDoors), 16)
        self.assertNotIn((3, 3), hutWithDoors)
        self.assertNotIn((0, -3), hutWithDoors)

    def test_the_room_inside_a_hut_leaves_the_middle_for_the_spawner(self):
        self.assertEqual(len(expansion.HUT_INSIDE), 24)
        self.assertNotIn((0, 0), expansion.HUT_INSIDE)
        self.assertEqual(len(expansion.HUT_FLOOR), 81)


class SharedWorkTests(unittest.TestCase):
    """work(): progress kept on a hut or faction so builders add up."""

    def test_work_finishes_after_the_turns_needed_and_starts_over(self):
        hut = {}
        self.assertEqual([expansion.work(hut, "wall", 2) for _ in range(3)], [False, True, False])
        self.assertEqual(hut["progress"], {"wall": 1})

    def test_two_builders_on_the_same_thing_share_progress(self):
        faction = expansion.Faction(0, "warpaint")
        self.assertFalse(expansion.work(faction, ("bonfire", 5), 2))
        self.assertTrue(expansion.work(faction, ("bonfire", 5), 2))


if __name__ == "__main__":
    unittest.main()
