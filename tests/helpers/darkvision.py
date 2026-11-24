"""Helpers for the tests of test_darkvision.py, shared by its unit, integration and acceptance tests."""
from cruel.inventory import recipes


WALL = 2


def recipe(recipeId):
    return next(recipe for recipe in recipes.RECIPES if recipe.id == recipeId)


def darkvisionPotion():
    return recipe("darkvision").makeItem(0, 0)


def drink(player):
    player.inventory.append(darkvisionPotion())
    player.useConsumable(len(player.inventory) - 1)
