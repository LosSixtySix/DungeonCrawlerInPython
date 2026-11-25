"""Loading pickled save games, including saves made before the code moved into the cruel/ package."""
import importlib
import io
import os
import pickle
import unittest

import tests  # noqa: F401
from cruel.core import savefile
from cruel.world import plants


def saveBytesWithOldModuleName(gameObject, newModule, oldModule):
    """Pickle gameObject, then rename its module the way a save from before the move would name it."""
    newSaveBytes = pickle.dumps(gameObject, protocol=2)
    oldSaveBytes = newSaveBytes.replace(f"{newModule}\n".encode(), f"{oldModule}\n".encode())
    assert oldSaveBytes != newSaveBytes, "the module name should have been in the pickle"
    return oldSaveBytes


class OldSaveTests(unittest.TestCase):
    """load() maps the old top-level module names to their new place."""

    def test_a_save_from_before_the_move_still_loads(self):
        plantedCrop = plants.Plant("wheat", planted=True, faction="goblins")
        oldSaveBytes = saveBytesWithOldModuleName(plantedCrop, "cruel.world.plants", "plants")
        self.assertIn(b"cplants\nPlant\n", oldSaveBytes)

        loadedCrop = savefile.load(io.BytesIO(oldSaveBytes))
        self.assertIs(type(loadedCrop), plants.Plant)
        self.assertEqual((loadedCrop.kind, loadedCrop.planted, loadedCrop.faction), ("wheat", True, "goblins"))

    def test_a_hand_written_old_pickle_names_the_new_class(self):
        oldSaveBytes = b"cplants\nPlant\n."  # protocol 0: just the class plants.Plant
        self.assertIs(savefile.load(io.BytesIO(oldSaveBytes)), plants.Plant)

    def test_plain_pickle_cannot_read_an_old_save(self):
        oldSaveBytes = saveBytesWithOldModuleName(plants.Plant("wheat"), "cruel.world.plants", "plants")
        with self.assertRaises(ModuleNotFoundError):
            pickle.loads(oldSaveBytes)

    def test_a_save_made_after_the_move_loads_unchanged(self):
        saveData = {"level": 3, "crops": [plants.Plant("wheat")], "visited": {1, 2}}
        loadedData = savefile.load(io.BytesIO(pickle.dumps(saveData)))
        self.assertEqual(loadedData["level"], 3)
        self.assertEqual(loadedData["visited"], {1, 2})
        self.assertIs(type(loadedData["crops"][0]), plants.Plant)


class MovedModuleTableTests(unittest.TestCase):
    """Every entry in MOVED must point at a real module whose file still has the old name."""

    def test_every_new_location_can_be_imported(self):
        for oldName, newName in savefile.MOVED.items():
            with self.subTest(oldName=oldName):
                importlib.import_module(newName)

    def test_every_old_name_matches_its_module_file(self):
        for oldName, newName in savefile.MOVED.items():
            with self.subTest(oldName=oldName):
                movedModule = importlib.import_module(newName)
                self.assertEqual(newName.rsplit(".", 1)[-1], oldName)
                self.assertEqual(os.path.basename(movedModule.__file__), oldName + ".py")


if __name__ == "__main__":
    unittest.main()
