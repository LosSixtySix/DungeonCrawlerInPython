"""Player settings (hotkeys, windows, display, sound, map zoom) kept in settings.json."""
import json
import os
import shutil
import tempfile
import unittest

import pygame

import tests  # noqa: F401
from cruel.core import settings


class SettingsFileTests(unittest.TestCase):
    """Loading, saving and validating settings.json, and rebinding hotkeys."""

    def setUp(self):
        self.tempFolder = tempfile.mkdtemp()
        self.settingsFile = os.path.join(self.tempFolder, "settings.json")

    def tearDown(self):
        shutil.rmtree(self.tempFolder, ignore_errors=True)

    def writeSettingsFile(self, text):
        with open(self.settingsFile, "w") as settingsFile:
            settingsFile.write(text)

    def assertAreDefaults(self, playerSettings):
        self.assertEqual(playerSettings.hotkeys, settings.DEFAULT_HOTKEYS)
        self.assertEqual(playerSettings.windowPositions, {})
        self.assertEqual(playerSettings.lightStyle, "sway")
        self.assertIsNone(playerSettings.resolution)
        self.assertTrue(playerSettings.fullscreen)
        self.assertEqual((playerSettings.masterVolume, playerSettings.musicVolume, playerSettings.effectsVolume), (80, 70, 80))
        self.assertFalse(playerSettings.muted)
        self.assertEqual(playerSettings.mapZoom, 1)

    def test_a_missing_file_gives_the_defaults_without_creating_it(self):
        self.assertAreDefaults(settings.Settings(self.settingsFile))
        self.assertFalse(os.path.exists(self.settingsFile))

    def test_a_corrupt_file_gives_the_defaults(self):
        self.writeSettingsFile("{not json")
        self.assertAreDefaults(settings.Settings(self.settingsFile))

    def test_an_empty_file_gives_the_defaults(self):
        self.writeSettingsFile("")
        self.assertAreDefaults(settings.Settings(self.settingsFile))

    def test_saved_settings_load_back_the_same(self):
        changedSettings = settings.Settings(self.settingsFile)
        changedSettings.hotkeys["interact"] = pygame.K_f
        changedSettings.windowPositions = {"inventory": [10, 20]}
        changedSettings.lightStyle = "flicker"
        changedSettings.resolution = [1280, 720]
        changedSettings.fullscreen = False
        changedSettings.masterVolume, changedSettings.musicVolume, changedSettings.effectsVolume = 50, 40, 30
        changedSettings.muted = True
        changedSettings.mapZoom = 3
        changedSettings.save()

        savedSettings = settings.Settings(self.settingsFile)
        self.assertEqual(savedSettings.hotkeys["interact"], pygame.K_f)
        self.assertEqual(savedSettings.windowPositions, {"inventory": [10, 20]})
        self.assertEqual(savedSettings.lightStyle, "flicker")
        self.assertEqual(savedSettings.resolution, [1280, 720])
        self.assertFalse(savedSettings.fullscreen)
        self.assertEqual((savedSettings.masterVolume, savedSettings.musicVolume, savedSettings.effectsVolume), (50, 40, 30))
        self.assertTrue(savedSettings.muted)
        self.assertEqual(savedSettings.mapZoom, 3)

    def test_invalid_values_are_ignored_and_volumes_are_clamped(self):
        self.writeSettingsFile(json.dumps({
            "hotkeys": {"interact": "f", "bogus": 5}, "lightStyle": "disco", "resolution": [0, 5],
            "fullscreen": "yes", "masterVolume": 500, "musicVolume": -3, "effectsVolume": True,
            "muted": 1, "mapZoom": 9, "windowPositions": {"broken": [1], "inventory": [2, 3]},
            "hotkeyVersion": settings.HOTKEY_VERSION}))
        loadedSettings = settings.Settings(self.settingsFile)
        self.assertEqual(loadedSettings.hotkeys, settings.DEFAULT_HOTKEYS)
        self.assertEqual(loadedSettings.lightStyle, "sway")
        self.assertIsNone(loadedSettings.resolution)
        self.assertTrue(loadedSettings.fullscreen)
        self.assertEqual((loadedSettings.masterVolume, loadedSettings.musicVolume, loadedSettings.effectsVolume), (100, 0, 80))
        self.assertFalse(loadedSettings.muted)
        self.assertEqual(loadedSettings.mapZoom, 1)
        self.assertEqual(loadedSettings.windowPositions, {"inventory": [2, 3]})

    def test_an_old_pouch_hotkey_moves_to_its_new_default(self):
        oldHotkeys = dict(settings.DEFAULT_HOTKEYS, materials=pygame.K_m)
        self.writeSettingsFile(json.dumps({"hotkeys": oldHotkeys, "hotkeyVersion": 1}))
        self.assertEqual(settings.Settings(self.settingsFile).hotkeys["materials"], pygame.K_p)

    def test_rebinding_to_a_used_key_swaps_the_two_and_saves(self):
        playerSettings = settings.Settings(self.settingsFile)
        inventoryKey = settings.DEFAULT_HOTKEYS["inventory"]
        worked, message = playerSettings.rebind("interact", inventoryKey)
        self.assertTrue(worked)
        self.assertIn("Swapped", message)
        self.assertEqual(playerSettings.hotkeys["inventory"], settings.DEFAULT_HOTKEYS["interact"])
        self.assertEqual(settings.Settings(self.settingsFile).hotkeys["interact"], inventoryKey)

    def test_a_fixed_key_cannot_be_bound(self):
        playerSettings = settings.Settings(self.settingsFile)
        worked, _ = playerSettings.rebind("interact", pygame.K_ESCAPE)
        self.assertFalse(worked)
        self.assertEqual(playerSettings.hotkeys["interact"], settings.DEFAULT_HOTKEYS["interact"])

    def test_resetting_hotkeys_restores_and_saves_the_defaults(self):
        playerSettings = settings.Settings(self.settingsFile)
        playerSettings.rebind("interact", pygame.K_f)
        playerSettings.resetHotkeys()
        self.assertEqual(settings.Settings(self.settingsFile).hotkeys, settings.DEFAULT_HOTKEYS)


if __name__ == "__main__":
    unittest.main()
