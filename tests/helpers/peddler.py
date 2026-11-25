"""Helpers for the tests of test_peddler.py, shared by its unit, integration and acceptance tests."""
import random
import pygame
from cruel.inventory import recipes
from cruel.world import peddler
from tests import support


FLOOR, PLAYER, WALL, CHEST, ENEMY, PILE = 0, 1, 2, 3, 5, 9
FACING_RIGHT = 1

# The prices on the design sheet (https://claude.ai/artifact/1rYJ3ttsSik1tghy7XhaSw), in Common quality
SHEET_PRICES = {
    "Workbench": 15, "Cooking Pot": 14, "Alchemist's Set": 20, "Portable Smelter": 27, "Jeweler's Kit": 27,
    "Cauldron": 123, "Anvil": 132, "Leather Pouch": 9, "Stone Pick": 8, "Wooden Shield": 9, "Soft-Soled Boots": 14,
    "Backpack": 21, "Copper Pick": 21, "Hide Boots": 27, "War Pick": 54, "Iron Sword": 66, "Iron Pick": 66,
    "Chainmail": 105, "Gilded Iron Sword": 126, "Void Amulet": 135, "Warded Chainmail": 180, "Roast Meat": 3,
    "Minor Healing Potion": 9, "Bomb": 12, "Potion Of Door": 12, "Healing Potion": 15, "Fire Flask": 15,
    "Greater Healing Potion": 21,
}


def recipeNamed(name):
    return next(recipe for recipe in recipes.RECIPES if recipe.name == name and recipe.amount == 1)


def blankGrid(rowLength=60, rowCount=40):
    return {spot: [FLOOR, 0] for spot in range(rowLength * rowCount)}


def peddlerFloor():
    """A game walked down to a new floor 1 that has the Peddler on it. Returns (game, his position, him)."""
    random.seed(3)
    game = support.newGame()
    game.saveGame = lambda *args, **kwargs: None
    game.peddlerNext = True
    game.goToNewLevel()
    traderSpot = next(spot for spot in game.EnemyPositions if peddler.isPeddler(game.grid[spot][2]))
    return game, traderSpot, game.grid[traderSpot][2]


def standFacing(game, targetSpot):
    """Puts the player just left of targetSpot, facing it."""
    support.placePlayer(game, targetSpot - 1)
    game.currentLocation = [FLOOR, 1]
    game.player.playerDirection = FACING_RIGHT
    game.setLookPosition()


def keyPress(game, key, modifierKeys=0):
    game.onKeyDown(pygame.event.Event(pygame.KEYDOWN, key=key, mod=modifierKeys, unicode="", scancode=0))
    game.onKeyUp(pygame.event.Event(pygame.KEYUP, key=key, mod=modifierKeys))
