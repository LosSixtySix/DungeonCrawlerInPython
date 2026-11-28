"""The game's music and sound effects, run under SDL's dummy audio driver (no real sound plays)."""
import os
import shutil
import tempfile
import unittest
from unittest import mock

import pygame

import tests  # noqa: F401
from cruel.audio import sound
from cruel.core import paths, settings


class SoundManifestTests(unittest.TestCase):
    """The manifests the sound system names must ship with the game."""

    def test_the_menu_theme_and_effect_manifests_exist(self):
        for manifest in (sound.MENU_THEME, sound.EXPLOSION, sound.HIT):
            with self.subTest(manifest=manifest):
                self.assertTrue(os.path.isfile(paths.resourcePath(manifest)))

    def test_the_music_and_ambience_folders_exist(self):
        self.assertTrue(os.path.isdir(paths.resourcePath(sound.GAME_MUSIC)))
        self.assertTrue(os.path.isdir(paths.resourcePath(sound.AMBIENCE)))


class SoundSystemTests(unittest.TestCase):
    """Building the Sound system and driving it the way the game does."""

    def setUp(self):
        self.tempFolder = tempfile.mkdtemp()
        self.playerSettings = settings.Settings(os.path.join(self.tempFolder, "settings.json"))
        self.gameSound = sound.Sound(self.playerSettings)

    def tearDown(self):
        shutil.rmtree(self.tempFolder, ignore_errors=True)

    def test_the_menu_theme_effects_and_ambience_load(self):
        self.assertEqual(self.gameSound.problem, "")
        self.assertIsNotNone(self.gameSound.menuTheme)
        self.assertIsNotNone(self.gameSound.menuTheme.intro)
        self.assertIsNotNone(self.gameSound.explosion)
        self.assertIsNotNone(self.gameSound.hit)
        self.assertTrue(self.gameSound.ambience)

    def test_volumes_follow_the_settings(self):
        self.playerSettings.masterVolume, self.playerSettings.musicVolume, self.playerSettings.effectsVolume = 50, 50, 20
        self.assertAlmostEqual(self.gameSound.musicVolume(), 0.25)
        self.assertAlmostEqual(self.gameSound.effectsVolume(), 0.10)
        self.playerSettings.muted = True
        self.assertEqual(self.gameSound.musicVolume(), 0.0)
        self.assertEqual(self.gameSound.effectsVolume(), 0.0)
        self.gameSound.applyVolume()

    def test_menu_and_game_music_start_and_stop_without_crashing(self):
        self.gameSound.playMenuTheme()
        self.gameSound.update()
        self.gameSound.stopMenuTheme()
        self.gameSound.playGameTheme()
        self.assertTrue(self.gameSound.inRun)
        self.assertIsNotNone(self.gameSound.nextAmbience)
        self.gameSound.update()
        self.gameSound.stopGameTheme()
        self.assertFalse(self.gameSound.inRun)

    def test_the_metropolis_music_loads(self):
        self.assertTrue(os.path.isdir(paths.resourcePath(sound.CITY_MUSIC)))
        self.assertTrue(self.gameSound.cityTracks)

    def test_in_a_city_the_playlist_is_the_metropolis_music(self):
        self.assertIs(self.gameSound.playlist(), self.gameSound.gameTracks)
        self.gameSound.setCity(True)
        self.assertIs(self.gameSound.playlist(), self.gameSound.cityTracks)
        self.gameSound.setCity(False)
        self.assertIs(self.gameSound.playlist(), self.gameSound.gameTracks)

    def test_walking_into_a_city_fades_the_game_track_out_for_a_city_track(self):
        self.gameSound.playGameTheme()
        self.assertIn(self.gameSound.gameTheme, self.gameSound.gameTracks)
        self.gameSound.setCity(True)
        self.assertTrue(self.gameSound.switching, "the game track fades out")
        self.gameSound.startNextTrack()  # (what update does once it's quiet)
        self.assertIn(self.gameSound.gameTheme, self.gameSound.cityTracks)

    def test_leaving_the_city_goes_back_to_the_game_music(self):
        self.gameSound.setCity(True)
        self.gameSound.playGameTheme()
        self.assertIn(self.gameSound.gameTheme, self.gameSound.cityTracks)
        self.gameSound.setCity(False)
        self.assertTrue(self.gameSound.switching)
        self.gameSound.startNextTrack()
        self.assertIn(self.gameSound.gameTheme, self.gameSound.gameTracks)

    def test_staying_in_the_city_keeps_the_track_playing(self):
        self.gameSound.setCity(True)
        self.gameSound.playGameTheme()
        self.gameSound.setCity(True)
        self.assertFalse(self.gameSound.switching)

    def test_effects_play_without_crashing(self):
        self.gameSound.playHit()
        self.gameSound.playExplosion()
        self.gameSound.playExplosion(sample=True)

    def test_no_audio_device_means_silence_not_a_crash(self):
        pygame.mixer.quit()
        try:
            with mock.patch("pygame.mixer.init", side_effect=pygame.error("no device")):
                silentSound = sound.Sound(self.playerSettings)
            self.assertEqual(silentSound.problem, "No audio device found")
            silentSound.playHit()
            silentSound.playExplosion()
            silentSound.playMenuTheme()
            silentSound.playGameTheme()
            silentSound.update()
            silentSound.applyVolume()
        finally:
            pygame.mixer.init(frequency=44100)


if __name__ == "__main__":
    unittest.main()
