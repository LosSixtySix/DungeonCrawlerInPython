"""The Clausthy players: LoopingMusic for music tracks and SoundVariations for sound effects, on real manifests."""
import json
import os
import shutil
import tempfile
import unittest

import pygame

import tests  # noqa: F401
from cruel.audio.clausthy_loop import LoopingMusic
from cruel.audio.clausthy_sfx import SoundVariations
from cruel.core import paths

MENU_THEME = paths.resourcePath("music/mainMenuTheme/dungeon_depths.json")
HIT_EFFECT = paths.resourcePath("music/soundEffects/hit/hit_sfx.json")


def setUpModule():
    if not pygame.mixer.get_init():
        pygame.mixer.init(frequency=44100)


class LoopingMusicTests(unittest.TestCase):
    """LoopingMusic: the intro once, then the loop forever."""

    def test_the_menu_theme_loads_its_intro_and_loop(self):
        menuTheme = LoopingMusic(MENU_THEME, volume=0.0)
        self.assertEqual(menuTheme.name, "Dungeon Depths")
        self.assertEqual(menuTheme.bpm, 84)
        self.assertIsNotNone(menuTheme.intro)
        self.assertGreater(menuTheme.loop.get_length(), 0)

    def test_play_queues_the_loop_and_stop_ends_it(self):
        menuTheme = LoopingMusic(MENU_THEME, volume=0.0)
        menuTheme.play()
        menuTheme.update()
        menuTheme.set_volume(0.5)
        menuTheme.stop()
        self.assertFalse(menuTheme.is_playing)

    def test_a_track_without_an_intro_loads(self):
        tempFolder = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tempFolder, True)
        # A manifest next to a copy of the menu theme's loop, with "intro": null like the game tracks.
        shutil.copy(paths.resourcePath("music/mainMenuTheme/dungeon_depths_loop.wav"), tempFolder)
        manifest = os.path.join(tempFolder, "loop_only.json")
        with open(manifest, "w") as manifestFile:
            json.dump({"name": "Loop Only", "intro": None, "loop": "dungeon_depths_loop.wav"}, manifestFile)
        loopOnlyTrack = LoopingMusic(manifest, volume=0.0)
        self.assertIsNone(loopOnlyTrack.intro)
        loopOnlyTrack.play()
        loopOnlyTrack.update()
        loopOnlyTrack.stop()

    def test_a_missing_manifest_raises(self):
        with self.assertRaises(OSError):
            LoopingMusic(paths.resourcePath("music/no_such_track.json"))


class SoundVariationsTests(unittest.TestCase):
    """SoundVariations: a random variation each time, never the same twice in a row."""

    def test_the_hit_effect_loads_every_variation(self):
        hitSound = SoundVariations(HIT_EFFECT, volume=0.0)
        with open(HIT_EFFECT) as manifestFile:
            listedFiles = json.load(manifestFile)["files"]
        self.assertEqual(hitSound.name, "hit")
        self.assertEqual(len(hitSound.sounds), len(listedFiles))

    def test_the_same_variation_never_plays_twice_in_a_row(self):
        hitSound = SoundVariations(HIT_EFFECT, volume=0.0)
        variationsPlayed = []
        for _ in range(30):
            hitSound.play()
            variationsPlayed.append(hitSound._last)
        for previous, current in zip(variationsPlayed, variationsPlayed[1:]):
            self.assertNotEqual(previous, current)

    def test_a_manifest_with_no_files_is_rejected(self):
        tempFolder = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tempFolder, True)
        emptyManifest = os.path.join(tempFolder, "empty_sfx.json")
        with open(emptyManifest, "w") as manifestFile:
            json.dump({"name": "empty", "files": []}, manifestFile)
        with self.assertRaises(ValueError):
            SoundVariations(emptyManifest)


if __name__ == "__main__":
    unittest.main()
