"""The Gray Peddler (peddler.py): a trader who turns up unannounced on a new floor, with a signpost by the arrival
spot, a room of Peddler's Stone with one entrance, a shop built like the Inventory, and a fight if you hurt him.

Integration tests; the rest are in tests/unit/test_peddler.py, tests/acceptance/test_peddler.py."""
import random
import unittest
from unittest import mock
from cruel.core import gamemanager
from cruel.entities import enemies
from cruel.inventory import recipes
from cruel.inventory import relics
from cruel.inventory import resources
from cruel.world import expansion
from cruel.world import peddler
from cruel.world import wall
from tests import support
from tests.helpers.peddler import CHEST, FLOOR, PILE, WALL, blankGrid, peddlerFloor, recipeNamed, standFacing


class StockTests(unittest.TestCase):
    """What he has for sale."""

    def setUp(self):
        random.seed(11)
        self.game = support.newGame()
        self.player = self.game.player

    def test_he_has_six_to_nine_things(self):
        for _ in range(200):
            self.assertTrue(6 <= len(peddler.rollStock(self.player)) <= 9)

    def test_there_is_always_a_station_you_do_not_have(self):
        for _ in range(200):
            stock = peddler.rollStock(self.player)
            stations = [ware for ware in stock if ware.kind == "station"]
            self.assertTrue(stations)
            self.assertFalse({ware.stationId for ware in stations} & self.player.stations)

    def test_he_never_sells_parts_relic_stations_or_double_batches(self):
        for _ in range(200):
            for ware in peddler.rollStock(self.player):
                if ware.recipe is not None:
                    self.assertNotIn(ware.recipe.kind, ("material", "plant", "setup", "pack"))
                    self.assertEqual(ware.recipe.amount, 1)
                self.assertNotIn(ware.stationId, peddler.NEVER_SOLD_STATIONS)

    def test_with_every_station_owned_he_still_has_a_full_stock(self):
        self.player.stations |= set(recipes.STATION_INFO)
        stock = peddler.rollStock(self.player)
        self.assertTrue(6 <= len(stock) <= 9)
        self.assertFalse([ware for ware in stock if ware.kind == "station"])

    def test_the_leather_pouch_is_only_sold_until_you_have_it(self):
        self.player.pouchLimit = resources.BIG_POUCH_LIMIT
        _, others = peddler.stockRecipes(self.player)
        self.assertNotIn("upgrade", {recipe.kind for recipe in others})

    def test_gear_quality_follows_the_odds(self):
        qualities = [peddler.rollQuality() for _ in range(20000)]
        for quality, percent in peddler.QUALITY_ODDS:
            self.assertAlmostEqual(qualities.count(quality) / len(qualities) * 100, percent, delta=1.5)

    def test_masterwork_gear_gets_its_free_enchantment(self):
        with mock.patch.object(peddler, "rollQuality", lambda: "Masterwork"):
            ware = peddler.wareFrom(recipeNamed("Iron Sword"))
        self.assertTrue(ware.item.name.startswith("Masterwork"))
        self.assertTrue(set(ware.item.enchants) & set(relics.MINOR_ENCHANTS))
        self.assertEqual(ware.price, 99)

    def test_a_relic_turns_up_now_and_then_but_never_the_molten_blade(self):
        relicStocks = 0
        for _ in range(2000):
            stock = peddler.rollStock(self.player)
            relicWares = [ware for ware in stock if ware.kind == "relic"]
            relicStocks += bool(relicWares)
            for ware in relicWares:
                self.assertNotEqual(ware.item.relicId, "molten_blade")
                self.assertEqual(ware.price, peddler.RELIC_PRICE)
        self.assertAlmostEqual(relicStocks / 2000, peddler.RELIC_CHANCE, delta=0.02)


class TradingTests(unittest.TestCase):
    """Buying from him and selling to him."""

    def setUp(self):
        random.seed(5)
        self.game = support.newGame()
        self.player = self.game.player
        self.trader = enemies.GrayPeddler()

    def stock(self, *wares):
        self.trader.wares = list(wares)

    def test_buying_gear_takes_the_gold_and_puts_it_in_your_pack(self):
        ironSword = peddler.Ware("gear", 66, item=recipeNamed("Iron Sword").build("Common"), recipeId="iron_sword")
        self.stock(ironSword)
        self.player.gold = 100
        bought, message = peddler.buy(self.player, self.trader, 0)
        self.assertTrue(bought, message)
        self.assertEqual(self.player.gold, 34)
        self.assertIn(ironSword.item, self.player.inventory)
        self.assertEqual(self.trader.wares, [], "his stock doesn't refill")

    def test_you_cannot_buy_what_you_cannot_afford(self):
        self.stock(peddler.Ware("relic", 200, item=relics.make("lantern")))
        self.player.gold = 150
        bought, message = peddler.buy(self.player, self.trader, 0)
        self.assertFalse(bought)
        self.assertEqual(message, "You need 50 more gold")
        self.assertEqual(self.player.gold, 150)

    def test_you_cannot_buy_with_a_full_pack(self):
        self.stock(peddler.Ware("relic", 200, item=relics.make("lantern")))
        self.player.gold = 500
        while self.player.addItemToInventory(recipeNamed("Stone Pick").build("Common")):
            pass
        bought, message = peddler.buy(self.player, self.trader, 0)
        self.assertFalse(bought)
        self.assertEqual(message, "No room in your pack")

    def test_buying_a_station_opens_its_crafting_tab(self):
        smelter = recipeNamed("Portable Smelter")
        self.stock(peddler.Ware("station", 27, recipeId=smelter.id, stationId="smelter"))
        self.player.gold = 30
        bought, _ = peddler.buy(self.player, self.trader, 0)
        self.assertTrue(bought)
        self.assertIn("smelter", self.player.stations)

    def test_buying_the_leather_pouch_makes_your_stacks_bigger(self):
        self.stock(peddler.Ware("pouch", 9, recipeId="leather_pouch"))
        self.player.gold = 9
        peddler.buy(self.player, self.trader, 0)
        self.assertEqual(self.player.pouchLimit, resources.BIG_POUCH_LIMIT)

    def test_selling_an_item_pays_his_offer(self):
        fineChainmail = recipeNamed("Chainmail").build("Fine")
        self.player.addItemToInventory(fineChainmail)
        goldBefore = self.player.gold
        message = peddler.sellItem(self.player, 0)
        self.assertEqual(self.player.gold, goldBefore + peddler.offerFor(fineChainmail))
        self.assertEqual(self.player.inventory, [])
        self.assertIn("Sold Fine Chainmail", message)

    def test_selling_a_stacked_potion_sells_one(self):
        healingPotion = recipeNamed("Healing Potion").makeItem(0, 0)
        healingPotion.count = 3
        self.player.inventory.append(healingPotion)
        peddler.sellItem(self.player, 0)
        self.assertEqual(self.player.inventory[0].count, 2)

    def test_selling_a_material_sells_eleven_or_every_whole_lot(self):
        self.player.materials["stone"] = 40
        goldBefore = self.player.gold
        peddler.sellMaterial(self.player, "stone")
        self.assertEqual((self.player.materials["stone"], self.player.gold - goldBefore), (29, 1))
        peddler.sellMaterial(self.player, "stone", everything=True)
        self.assertEqual((self.player.materials["stone"], self.player.gold - goldBefore), (7, 3))

    def test_fewer_than_eleven_will_not_sell(self):
        self.player.materials["iron_ore"] = 7
        sold, message = peddler.sellMaterial(self.player, "iron_ore", everything=True)
        self.assertFalse(sold)
        self.assertEqual(self.player.materials["iron_ore"], 7)
        self.assertIn("11 at a time", message)

    def test_selling_your_last_eleven_empties_that_pouch_slot(self):
        self.player.materials["wood"] = 11
        peddler.sellMaterial(self.player, "wood")
        self.assertNotIn("wood", self.player.materials)
        self.assertNotIn("wood", peddler.sellableMaterials(self.player))


class RoomTests(unittest.TestCase):
    """His room and the signpost."""

    def setUp(self):
        random.seed(7)
        self.rowLength = 60
        self.grid = blankGrid(self.rowLength)
        self.trader = enemies.GrayPeddler()

    def ringAround(self, center):
        insideColumns, insideRows = peddler.ROOM_INSIDE
        halfWidth, halfHeight = insideColumns // 2 + 1, insideRows // 2 + 1
        ring = []
        for rowOffset in range(-halfHeight, halfHeight + 1):
            for columnOffset in range(-halfWidth, halfWidth + 1):
                if abs(rowOffset) == halfHeight or abs(columnOffset) == halfWidth:
                    ring.append(center + columnOffset + rowOffset * self.rowLength)
        return ring

    def test_the_room_is_a_ring_of_peddlers_stone_with_one_entrance(self):
        traderSpot = peddler.placeRoom(self.grid, self.rowLength, 0, self.trader)
        self.assertIs(self.grid[traderSpot][2], self.trader)
        ring = self.ringAround(traderSpot)
        gaps = [spot for spot in ring if self.grid[spot][0] != WALL]
        self.assertEqual(len(gaps), 1, "exactly one way in")
        self.assertTrue(all(isinstance(self.grid[spot][2], wall.PeddlerWall) for spot in ring if spot not in gaps))

    def test_the_room_is_away_from_where_you_arrive(self):
        playerSpot = 30 + 20 * self.rowLength
        for _ in range(20):
            grid = blankGrid(self.rowLength)
            traderSpot = peddler.placeRoom(grid, self.rowLength, playerSpot, enemies.GrayPeddler())
            walkingDistance = abs(traderSpot % self.rowLength - playerSpot % self.rowLength) + \
                abs(traderSpot // self.rowLength - playerSpot // self.rowLength)
            self.assertGreaterEqual(walkingDistance, peddler.ROOM_DISTANCE)

    def test_the_entrance_faces_the_open_floor(self):
        for spot in self.grid:  # solid rock, except open floor down the right-hand side
            if spot % self.rowLength < 40:
                self.grid[spot] = [WALL, 0, wall.StoneWall()]
        with mock.patch.object(random, "randint", side_effect=[28, 15]):  # the room's top-left corner
            traderSpot = peddler.placeRoom(self.grid, self.rowLength, 0, self.trader)
        rightSideGap = traderSpot + 4
        self.assertEqual(self.grid[rightSideGap][0], FLOOR)
        self.assertEqual(self.grid[traderSpot - 4][0], WALL, "the left side stays shut")

    def test_the_room_is_never_built_over_chests_doors_or_enemies(self):
        for spot in self.grid:
            if spot % 7 == 0:
                self.grid[spot] = [CHEST, 0, []]
        self.assertIsNone(peddler.placeRoom(self.grid, self.rowLength, 0, self.trader))

    def test_the_signpost_goes_on_free_floor_beside_you(self):
        besideYou = [101, 99, 160, 40]
        self.grid[101] = [WALL, 0, wall.StoneWall()]
        signpostSpot = peddler.placeSignpost(self.grid, besideYou)
        self.assertEqual(signpostSpot, 99)
        self.assertEqual(self.grid[99][0], peddler.SIGNPOST)

    def test_walled_in_the_signpost_replaces_a_wall(self):
        besideYou = [101, 99]
        for spot in besideYou:
            self.grid[spot] = [WALL, 0, wall.StoneWall()]
        self.assertEqual(peddler.placeSignpost(self.grid, besideYou), 101)

    def test_peddlers_stone_takes_about_150_swings_or_15_bombs(self):
        stone = wall.PeddlerWall()
        swings = 0
        while stone.hp > 0:
            stone.takeDamage(50, 10)  # a huge swing still only takes off its hardness
            swings += 1
        self.assertEqual(swings, 150)
        self.assertEqual(-(-wall.PeddlerWall().hp // recipes.BOMB_WALL_DAMAGE), 15)

    def test_a_bomb_ignores_hardness(self):
        game = support.newGame()
        landing = support.openTile(game)
        stone = wall.PeddlerWall()
        game.grid[landing + 1] = [WALL, 1, stone]
        with mock.patch.object(gamemanager, "FLOOR_BREAK_CHANCE", 0):
            game.land({"landing": landing, "effect": "Explosive", "power": 3})
        self.assertEqual(stone.hp, wall.PeddlerWall().hp - recipes.BOMB_WALL_DAMAGE)


class AppearingTests(unittest.TestCase):
    """When he turns up."""

    def newFloorWith(self, chance):
        random.seed(2)
        game = support.newGame()
        game.saveGame = lambda *args, **kwargs: None
        with mock.patch.object(peddler, "APPEAR_CHANCE", chance):
            game.goToNewLevel()
        return game

    def peddlersOn(self, game):
        return [spot for spot in game.EnemyPositions if peddler.isPeddler(game.grid[spot][2])]

    def test_by_chance_a_new_floor_gets_him_and_a_signpost_beside_you(self):
        game = self.newFloorWith(1.0)
        self.assertEqual(len(self.peddlersOn(game)), 1)
        signposts = [spot for spot, tile in game.grid.items() if tile[0] == peddler.SIGNPOST]
        self.assertEqual(len(signposts), 1)
        self.assertIn(signposts[0], game.neighbors(game.playerPositionFlat))

    def test_he_comes_with_no_announcement(self):
        game = self.newFloorWith(1.0)
        self.assertEqual([popup[0] for popup in game.popups if "Peddler" in popup[0]], [])

    def test_most_floors_do_not_have_him(self):
        game = self.newFloorWith(0.0)
        self.assertEqual(self.peddlersOn(game), [])
        self.assertFalse(any(tile[0] == peddler.SIGNPOST for tile in game.grid.values()))

    def test_never_on_the_scorched_depths(self):
        random.seed(2)
        game = support.newGame(level=1)
        game.saveGame = lambda *args, **kwargs: None
        game.peddlerNext = True
        game.enterScorched()
        self.assertEqual(self.peddlersOn(game), [])

    def test_the_console_puts_him_on_the_next_new_floor(self):
        random.seed(2)
        game = support.newGame()
        game.saveGame = lambda *args, **kwargs: None
        game.console.cmdPeddler([])
        with mock.patch.object(peddler, "APPEAR_CHANCE", 0.0):
            game.goToNewLevel()
        self.assertEqual(len(self.peddlersOn(game)), 1)
        self.assertFalse(game.peddlerNext, "only the one floor")


class FightingTests(unittest.TestCase):
    """He can be hurt, he fights back, and he drops his stock when he dies."""

    def setUp(self):
        self.game, self.traderSpot, self.trader = peddlerFloor()
        standFacing(self.game, self.traderSpot)

    def test_while_calm_he_never_moves(self):
        for _ in range(20):
            self.game.enemyTurn()
        self.assertIs(self.game.grid[self.traderSpot][2], self.trader)

    def test_goblin_factions_leave_him_alone(self):
        faction = expansion.newFaction(self.game, "warpaint", neutral=False)
        goblin = enemies.Goblin()
        expansion.setFaction(goblin, faction)
        self.assertFalse(expansion.hostile(goblin, self.trader))

    def test_shift_interact_attacks_him_and_turns_him_hostile(self):
        game = self.game
        game.enemyDodge = lambda target, damage, position: damage  # the swing always lands
        game.player.DealDamage = lambda: 3  # (and always does some damage)
        game.onInteract()
        self.assertEqual(game.focus, "shop")
        game.onInteract(forceAttack=True)
        self.assertLess(self.trader.hp, self.trader.maxHp)
        self.assertTrue(self.trader.hostile)
        self.assertNotIn("shop", game.openWindows, "the shop closes")
        self.assertIn("The Peddler turns on you!", [popup[0] for popup in game.popups])

    def test_a_bomb_on_him_turns_him_hostile(self):
        with mock.patch.object(gamemanager, "FLOOR_BREAK_CHANCE", 0):
            self.game.land({"landing": self.traderSpot, "effect": "Explosive", "power": 3})
        self.assertTrue(self.trader.hostile)

    def test_once_hostile_he_fights_you(self):
        game = self.game
        peddler.provoke(game, self.trader, self.traderSpot)
        game.player.evasion = lambda: 0
        game.player.damageTaken = 0
        for _ in range(5):
            game.MoveEnemies()
        self.assertGreater(game.player.damageTaken, 0)

    def test_once_hostile_interact_hits_him_instead_of_trading(self):
        game = self.game
        peddler.provoke(game, self.trader, self.traderSpot)
        game.enemyDodge = lambda target, damage, position: damage
        game.player.DealDamage = lambda: 3  # (a swing that always does some damage)
        game.onInteract()
        self.assertNotIn("shop", game.openWindows)
        self.assertLess(self.trader.hp, self.trader.maxHp)

    def test_killed_he_pays_his_gold_and_drops_his_stock(self):
        game = self.game
        itemsInStock = [ware.item for ware in self.trader.wares if ware.item is not None]
        goldBefore = game.player.gold
        game.killEnemy(self.traderSpot)
        self.assertGreaterEqual(game.player.gold - goldBefore, 200)
        grounds = [game.groundAt(spot) for spot in game.grid]  # (on his body, and spilled anywhere: under you too)
        dropped = [item for ground in grounds if ground[0] == PILE for item in ground[2].items]
        self.assertEqual(sorted(item.name for item in dropped), sorted(item.name for item in itemsInStock))


if __name__ == "__main__":
    unittest.main()
