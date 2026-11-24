"""
clausthy_sfx.py - play sound effects exported from Clausthy's SFX Lab in pygame.

    import pygame
    from clausthy_sfx import SoundVariations

    pygame.mixer.init(frequency=44100)
    jump = SoundVariations("sfx/jump_sfx.json")

    jump.play()          # plays one of the variations at random (never the same one twice in a row)

Playing slightly different versions each time stops repeated sounds (footsteps, coins, hits)
from sounding robotic.
"""

import json
import os
import random

import pygame


class SoundVariations:
    def __init__(self, manifest_path, volume=1.0):
        if not pygame.mixer.get_init():
            raise RuntimeError("Call pygame.mixer.init() (or pygame.init()) before loading sounds.")
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)
        folder = os.path.dirname(os.path.abspath(manifest_path))
        self.name = manifest.get("name", "")
        self.sounds = [pygame.mixer.Sound(os.path.join(folder, name)) for name in manifest["files"]]
        if not self.sounds:
            raise ValueError(f"{manifest_path} lists no sound files.")
        self._last = -1
        self.set_volume(volume)

    def play(self):
        """Play a random variation (not the one played last time). Returns the Channel, or None if all are busy."""
        choices = [i for i in range(len(self.sounds)) if i != self._last] or [0]
        self._last = random.choice(choices)
        return self.sounds[self._last].play()

    def set_volume(self, volume):
        for sound in self.sounds:
            sound.set_volume(volume)


if __name__ == "__main__":
    import sys

    if len(sys.argv) != 2:
        print("usage: python clausthy_sfx.py <exported _sfx.json>")
        sys.exit(1)
    pygame.mixer.init(frequency=44100)
    sfx = SoundVariations(sys.argv[1])
    for _ in range(len(sfx.sounds) * 2):
        sfx.play()
        pygame.time.wait(int(max(s.get_length() for s in sfx.sounds) * 1000) + 150)
