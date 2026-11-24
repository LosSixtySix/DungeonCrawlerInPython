import pickle

"""
Reading the pickled save game.

Pickle stores each object's class by its module name. Before the code moved into the cruel/ package, those
were top-level names (plants.Plant, playerClass.Player, ...), so saves made then name modules that no longer
exist. load() maps those old names to where the modules live now, so old saves keep loading.
"""

MOVED = {
    "gamemanager": "cruel.core.gamemanager",
    "EventDispatcher": "cruel.core.EventDispatcher",
    "settings": "cruel.core.settings",
    "paths": "cruel.core.paths",
    "devconsole": "cruel.core.devconsole",
    "updater": "cruel.core.updater",
    "attempts": "cruel.core.attempts",
    "version": "cruel.core.version",
    "wall": "cruel.world.wall",
    "themes": "cruel.world.themes",
    "expansion": "cruel.world.expansion",
    "organizers": "cruel.world.organizers",
    "plants": "cruel.world.plants",
    "events": "cruel.world.events",
    "connectingEmptyRooms": "cruel.world.connectingEmptyRooms",
    "playerClass": "cruel.entities.playerClass",
    "enemies": "cruel.entities.enemies",
    "items": "cruel.inventory.items",
    "loot": "cruel.inventory.loot",
    "recipes": "cruel.inventory.recipes",
    "relics": "cruel.inventory.relics",
    "resources": "cruel.inventory.resources",
    "renderer": "cruel.graphics.renderer",
    "sprites": "cruel.graphics.sprites",
    "titlefog": "cruel.graphics.titlefog",
    "sound": "cruel.audio.sound",
}


class _Unpickler(pickle.Unpickler):
    def find_class(self, module, name):
        return super().find_class(MOVED.get(module, module), name)


def load(f):
    """pickle.load for save files, old module names included."""
    return _Unpickler(f).load()
