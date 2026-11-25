"""Where the game finds its shipped files (assets/, music/) and where it writes saves."""
import os
import unittest

import tests
from cruel.core import paths


def sameFolder(first, second):
    return os.path.normcase(first).rstrip("\\/") == os.path.normcase(second).rstrip("\\/")


class ResourcePathTests(unittest.TestCase):
    """resourcePath(): read-only files that ship with the game."""

    def test_resource_path_points_at_the_repo_root(self):
        self.assertTrue(sameFolder(paths.resourcePath(""), tests.ROOT))

    def test_the_font_icon_and_music_folder_are_found(self):
        self.assertTrue(os.path.isfile(paths.resourcePath("assets/Forgore.otf")))
        self.assertTrue(os.path.isfile(paths.resourcePath("assets/icon.png")))
        self.assertTrue(os.path.isdir(paths.resourcePath("music")))


class SavePathTests(unittest.TestCase):
    """savePath(): files written while playing, redirected to a temp folder by the tests package."""

    def test_the_save_folder_is_inside_the_temp_folder(self):
        self.assertTrue(paths.SAVE_DIR.startswith(tests.SAVE_DIR))
        self.assertEqual(paths.SAVE_DIR, os.path.join(tests.SAVE_DIR, paths.GAME_NAME))
        self.assertTrue(os.path.isdir(paths.SAVE_DIR))

    def test_every_saved_file_goes_in_the_save_folder(self):
        for savedFileName in paths.SAVED_FILES:
            self.assertEqual(os.path.dirname(paths.savePath(savedFileName)), paths.SAVE_DIR)

    def test_settings_and_attempts_files_use_the_temp_save_folder(self):
        from cruel.core import attempts, settings
        self.assertTrue(settings.SETTINGS_FILE.startswith(tests.SAVE_DIR))
        self.assertTrue(attempts.ATTEMPTS_FILE.startswith(tests.SAVE_DIR))


if __name__ == "__main__":
    unittest.main()
