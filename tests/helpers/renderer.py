"""Helpers for the tests of test_renderer.py, shared by its unit, integration and acceptance tests."""
from cruel.world import themes


# Every floor type's themes but the Scorched Depths (those have their own tests)
FLOOR_TYPES = [floorType for floorType in themes.THEMES if floorType != "Scorched Depths"]


def distinctColors(surface, step=16):
    """How many different colors a grid of sample points on the surface has."""
    width, height = surface.get_size()
    return {tuple(surface.get_at((pixelX, pixelY)))[:3] for pixelX in range(0, width, step) for pixelY in range(0, height, step)}
