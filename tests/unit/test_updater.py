"""The self-updater: version comparison, and the background check that only the packaged game runs.
No test here reaches the network or starts a process."""
import io
import json
import sys
import unittest
from unittest import mock

import tests  # noqa: F401
from cruel.core import updater


class ParseVersionTests(unittest.TestCase):
    """parseVersion() turns version text into something that compares correctly."""

    def test_version_text_becomes_a_tuple_of_numbers(self):
        self.assertEqual(updater.parseVersion("1.2.3"), (1, 2, 3))
        self.assertEqual(updater.parseVersion(" 0.1.45\n"), (0, 1, 45))

    def test_text_that_is_not_a_version_becomes_empty(self):
        for notAVersion in ("", "abc", "1.x.3", None):
            self.assertEqual(updater.parseVersion(notAVersion), ())

    def test_versions_compare_by_number_not_by_text(self):
        self.assertGreater(updater.parseVersion("0.1.10"), updater.parseVersion("0.1.9"))
        self.assertGreater(updater.parseVersion("1.0.0"), updater.parseVersion("0.99.99"))
        self.assertLess(updater.parseVersion("junk"), updater.parseVersion("0.0.0"))


class ServerReply(io.BytesIO):
    """Stands in for urlopen's response: a version.json body."""

    def __init__(self, versionJson):
        super().__init__(json.dumps(versionJson).encode())


class UpdaterTests(unittest.TestCase):
    """Updater: when it checks, what it does with the answer, and failing quietly when offline."""

    def setUp(self):
        # Any real network request or launched installer fails the test, unless a test patches it on purpose.
        for target in ("urllib.request.urlopen", "subprocess.Popen"):
            patcher = mock.patch(target, side_effect=AssertionError(f"{target} was called"))
            patcher.start()
            self.addCleanup(patcher.stop)

    def makeUpdaterWithoutThread(self):
        with mock.patch("threading.Thread"):
            return updater.Updater()

    def test_running_from_source_never_checks_for_updates(self):
        self.assertFalse(getattr(sys, "frozen", False))
        with mock.patch("threading.Thread") as backgroundThread:
            gameUpdater = updater.Updater()
        backgroundThread.assert_not_called()
        self.assertIsNone(gameUpdater.latest)
        self.assertFalse(gameUpdater.takeChange())

    def test_the_packaged_game_checks_in_the_background(self):
        with mock.patch.object(sys, "frozen", True, create=True), mock.patch("threading.Thread") as backgroundThread:
            gameUpdater = updater.Updater()
        backgroundThread.assert_called_once()
        self.assertEqual(backgroundThread.call_args.kwargs["target"], gameUpdater.check)
        backgroundThread.return_value.start.assert_called_once()

    def test_a_newer_server_version_is_offered_once(self):
        gameUpdater = self.makeUpdaterWithoutThread()
        with mock.patch("urllib.request.urlopen", return_value=ServerReply({"version": "999.0.0"})) as urlopen:
            gameUpdater.check()
        self.assertTrue(urlopen.call_args.args[0].endswith("version.json"))
        self.assertEqual(gameUpdater.latest, "999.0.0")
        self.assertTrue(gameUpdater.takeChange())
        self.assertFalse(gameUpdater.takeChange())

    def test_the_same_older_or_unreadable_version_is_not_offered(self):
        gameUpdater = self.makeUpdaterWithoutThread()
        for serverVersion in (updater.VERSION, "0.0.1", "garbage"):
            with mock.patch("urllib.request.urlopen", return_value=ServerReply({"version": serverVersion})):
                gameUpdater.check()
        self.assertIsNone(gameUpdater.latest)
        self.assertFalse(gameUpdater.takeChange())

    def test_an_unreachable_server_is_ignored(self):
        gameUpdater = self.makeUpdaterWithoutThread()
        with mock.patch("urllib.request.urlopen", side_effect=OSError("offline")):
            gameUpdater.check()
        self.assertIsNone(gameUpdater.latest)

    def test_updating_while_offline_explains_and_launches_nothing(self):
        gameUpdater = self.makeUpdaterWithoutThread()
        with mock.patch("urllib.request.urlopen", side_effect=OSError("offline")), \
                mock.patch("subprocess.Popen") as installer:
            errorMessage = gameUpdater.startUpdate()
        self.assertIsInstance(errorMessage, str)
        installer.assert_not_called()


if __name__ == "__main__":
    unittest.main()
