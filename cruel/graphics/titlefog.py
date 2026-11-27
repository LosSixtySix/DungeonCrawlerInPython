import math
import random

import pygame

"""
The fog that rolls across the title screen ("High Fog"). Three layers of soft fog drift sideways at different
speeds, thickest at the floor and thinning out with height, up to FOG_TOP from the top of the screen.
It's tinted with the menu's text color, so it changes with the random title theme.

How it's cheap: each layer is a small noise picture made once when the game starts. It tiles left to right and
only ever slides sideways, so how thick the fog is at each height is baked into it. When the color or the
screen size changes, the layers are tinted and scaled up once; after that each frame is just a few blits.
"""

FOG_TOP = 0.12      # the fog reaches this far from the top of the screen (0.12 = 12%)
FOG_THICK = 0.5     # how much thin haze stays up high (0 = the fog fades out fast above the floor)
LOW_W = 240         # a layer's width in noise pixels: one full repeat, two screens wide
LOW_H = 68          # a layer's height in noise pixels (it's scaled up to the screen, smoothly)
SCREENS_PER_REPEAT = 2

# (lattice cells across one repeat, vertical frequency, octaves, how strong, speed in noise pixels a second;
#  minus goes left). The cell counts are whole numbers so every layer tiles without a seam.
LAYERS = [
    (8, 0.060, 4, 0.50, -1.3),
    (5, 0.045, 3, 0.42, 1.25),
    (4, 0.030, 3, 0.26, -1.1),  # the slow, wide layer that reaches highest
]


def _smooth(t):
    return t * t * (3 - 2 * t)


class _Noise:
    """Value noise that repeats every `period` cells across (and doesn't need to repeat down)."""
    def __init__(self, seed):
        rng = random.Random(seed)
        self.values = [rng.random() for _ in range(256 * 256)]

    def at(self, x, y, period):
        xi, yi = math.floor(x), math.floor(y)
        xf, yf = x - xi, y - yi
        x0, x1 = xi % period, (xi + 1) % period
        y0, y1 = yi & 255, (yi + 1) & 255
        a, b = self.values[y0 * 256 + x0], self.values[y0 * 256 + x1]
        c, d = self.values[y1 * 256 + x0], self.values[y1 * 256 + x1]
        u, w = _smooth(xf), _smooth(yf)
        return (a + (b - a) * u) * (1 - w) + (c + (d - c) * u) * w


def _shape(fy):
    """How much fog there can be at this height (fy: 0 at the top of the screen, 1 at the bottom)."""
    ground = max(0.0, (fy - FOG_TOP) / (1 - FOG_TOP))
    return ground ** 1.6 * (1 - FOG_THICK) + ground ** 0.7 * FOG_THICK * 0.55


def _makeLayer(noise, cells, freqY, octaves, strength):
    """One layer as a white picture whose alpha is the fog (tinted later)."""
    pixels = bytearray(LOW_W * LOW_H * 4)
    for y in range(LOW_H):
        shape = _shape(y / LOW_H) * strength
        if shape <= 0:
            continue
        for x in range(LOW_W):
            total, amp, norm, scale = 0.0, 0.5, 0.0, 1
            for _ in range(octaves):
                total += amp * noise.at(x * cells * scale / LOW_W, y * freqY * scale + 7.3 * scale, cells * scale)
                norm += amp
                amp *= 0.5
                scale *= 2
            density = max(0.0, (total / norm - 0.33) / 0.45)
            alpha = min(1.0, density * shape * 1.4)
            i = (y * LOW_W + x) * 4
            pixels[i:i + 4] = (255, 255, 255, int(alpha * 255))
    return pygame.image.frombuffer(bytes(pixels), (LOW_W, LOW_H), "RGBA").convert_alpha()


class TitleFog:
    def __init__(self):
        self.base = None    # the white layers, made the first time the fog is drawn
        self.ready = {}     # (color, screen size) -> the tinted, scaled layers
        self.key = None

    def build(self):
        noise = _Noise(1337)
        self.base = [_makeLayer(noise, cells, freqY, octaves, strength) for cells, freqY, octaves, strength, _ in LAYERS]

    def layersFor(self, color, size):
        key = (tuple(color[:3]), size)
        if key != self.key:  # a new theme or resolution: tint and scale once
            if self.base is None:
                self.build()
            width, height = size[0] * SCREENS_PER_REPEAT, size[1]
            layers = []
            for base in self.base:
                tinted = base.copy()
                tinted.fill((*color[:3], 255), special_flags=pygame.BLEND_RGBA_MULT)
                layers.append(pygame.transform.smoothscale(tinted, (width, height)))
            self.ready = {key: layers}
            self.key = key
        return self.ready[key]

    def draw(self, win, color, alpha=255):
        """Draws the fog over whatever is on win (call it before the menu text). alpha fades all of it."""
        size = win.get_size()
        seconds = pygame.time.get_ticks() / 1000
        for layer, (_, _, _, _, speed) in zip(self.layersFor(color, size), LAYERS):
            width = layer.get_width()
            offset = int(seconds * speed * width / LOW_W) % width
            layer.set_alpha(alpha)
            top = int(size[1] * FOG_TOP)  # nothing above the fog line, so don't blit it
            area = pygame.Rect(0, top, width, size[1] - top)
            x = offset - width
            while x < size[0]:
                win.blit(layer, (x, top), area)
                x += width
