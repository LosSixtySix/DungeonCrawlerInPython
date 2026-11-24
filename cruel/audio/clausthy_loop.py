"""
clausthy_loop.py - play music exported from Clausthy's Loop Studio in pygame.

Usage in your game:

    import pygame
    from clausthy_loop import LoopingMusic

    pygame.mixer.init(frequency=44100)
    music = LoopingMusic("music/forest_level.json")
    music.play()

    while running:
        ...
        music.update()      # once per frame
        ...

The intro plays once, then the loop repeats forever with no gap. Gapless repeating
works by queueing the loop on the same mixer channel, so update() must run at
least once per loop length (any normal game loop easily does).

Try an export without a game:  python clausthy_loop.py forest_level.json
"""

import json
import os

import pygame


class LoopingMusic:
    def __init__(self, manifest_path, channel=None, volume=1.0):
        if not pygame.mixer.get_init():
            raise RuntimeError("Call pygame.mixer.init() (or pygame.init()) before creating LoopingMusic.")

        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)
        folder = os.path.dirname(os.path.abspath(manifest_path))

        self.name = manifest.get("name", "")
        self.bpm = manifest.get("bpm")
        intro_file = manifest.get("intro")
        self.intro = pygame.mixer.Sound(os.path.join(folder, intro_file)) if intro_file else None
        self.loop = pygame.mixer.Sound(os.path.join(folder, manifest["loop"]))

        self.channel = channel or pygame.mixer.find_channel(True)
        self.channel.set_volume(volume)
        self._playing = False

    def play(self):
        """Start from the beginning (intro, then loop)."""
        self.channel.stop()
        if self.intro is not None:
            self.channel.play(self.intro)
            self.channel.queue(self.loop)
        else:
            self.channel.play(self.loop, loops=-1)
        self._playing = True

    def update(self):
        """Keep the loop queued. Call once per frame."""
        if not self._playing or self.intro is None:
            return
        # Once the queued loop starts playing the queue empties; queue it again so it repeats seamlessly.
        if self.channel.get_busy() and self.channel.get_queue() is None:
            self.channel.queue(self.loop)

    def stop(self, fade_ms=0):
        self._playing = False
        if fade_ms > 0:
            self.channel.fadeout(fade_ms)
        else:
            self.channel.stop()

    def set_volume(self, volume):
        self.channel.set_volume(volume)

    @property
    def is_playing(self):
        return self._playing and self.channel.get_busy()


if __name__ == "__main__":
    import sys

    if len(sys.argv) != 2:
        print("usage: python clausthy_loop.py <exported .json>")
        sys.exit(1)

    pygame.mixer.init(frequency=44100)
    music = LoopingMusic(sys.argv[1])
    music.play()
    print(f"Playing {music.name or sys.argv[1]} - press Ctrl+C to stop.")
    clock = pygame.time.Clock()
    try:
        while True:
            music.update()
            clock.tick(60)
    except KeyboardInterrupt:
        music.stop(fade_ms=500)
        pygame.time.wait(600)
