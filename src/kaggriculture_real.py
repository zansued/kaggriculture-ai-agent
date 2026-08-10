"""Real Kaggriculture agent — built against the actual engine contract.

The engine ships inside `kaggle_environments` (envs/kaggriculture/). This module
is SELF-CONTAINED (stdlib only) so it can be submitted as a single `main.py`:
it inlines every protocol constant needed at decision time.

Strategy (simple, correct first):
  1. Market first: restock seeds for the crops we grow; sell everything in the
     shed (harvested produce / animal products). Both are free market orders.
  2. Pick the highest-priority tile for the farmer:
        harvest (yield_units > 0)  >  water (needs water)  >  dig weed  >  plant
     Among equal priority, choose the tile NEAREST the farmer (Manhattan).
  3. If standing on the target, act; else step toward it. Else PASS.
"""

from __future__ import annotations

# --------------------------------------------------------------------------- #
# Protocol constants (mirror the engine source — authoritative).
# --------------------------------------------------------------------------- #
CROPS = {
    "WHEAT":      {"seed": 10, "first_yield_day": 2, "max_yield_day": 4, "interval": 0, "max_yield": 6, "ongoing": False},
    "CARROT":     {"seed": 20, "first_yield_day": 2, "max_yield_day": 3, "interval": 0, "max_yield": 4, "ongoing": False},
    "TOMATO":     {"seed": 50, "first_yield_day": 8, "max_yield_day": 8, "interval": 1, "max_yield": 4, "ongoing": True},
    "STRAWBERRY": {"seed": 100, "first_yield_day": 10, "max_yield_day": 10, "interval": 2, "max_yield": 4, "ongoing": True},
    "MELON":      {"seed": 80, "first_yield_day": 10, "max_yield_day": 12, "interval": 0, "max_yield": 6, "ongoing": False},
}
ANIMALS = {
    "GOOSE": {"cost": 300, "structure": "COOP",    "first_yield_day": 4, "interval": 1, "max_held": 4, "product": "EGG"},
    "COW":   {"cost": 400, "structure": "PASTURE", "first_yield_day": 8, "interval": 2, "max_held": 6, "product": "MILK"},
    "SHEEP": {"cost": 500, "structure": "PASTURE", "first_yield_day": 6, "interval": 3, "max_held": 6, "product": "WOOL"},
}
PRODUCTS = ["WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON", "EGG", "MILK", "WOOL", "FERTILIZER"]

STARTING_MONEY = 3000
BOARD_SIZE = 10

# Actions
PASS = "PASS"; NORTH = "NORTH"; SOUTH = "SOUTH"; EAST = "EAST"; WEST = "WEST"
MOVES = (NORTH, SOUTH, EAST, WEST)
WATER = "WATER"; HARVEST = "HARVEST"; DIG = "DIG"; PLANT = "PLANT"
KIND_PLANT = "PLANT"; KIND_WEED = "WEED"
BUY_SEED = "BUY_SEED"; SELL = "SELL"


def build_action(farmer_cmd: list, market: list | None = None) -> dict:
    return {"farmer": list(farmer_cmd), "hands": [], "market": market or []}


def pass_action(market: list | None = None) -> dict:
    return build_action([PASS], market)


def step_toward(fx: int, fy: int, tx: int, ty: int) -> str:
    if fx < tx:
        return EAST
    if fx > tx:
        return WEST
    if fy < ty:
        return SOUTH
    if fy > ty:
        return NORTH
    return PASS


def my_farm(obs: dict) -> dict:
    return obs["farms"][obs["player"]]


def farmer_xy(obs: dict) -> tuple[int, int]:
    fx, fy = my_farm(obs)["farmer"]
    return int(fx), int(fy)


def _nearest(fx: int, fy: int, cells: list[tuple[int, int]]) -> tuple[int, int]:
    return min(cells, key=lambda c: abs(c[0] - fx) + abs(c[1] - fy))


class FarmBrain:
    def __init__(
        self,
        crops: list[str] | None = None,
        seed_restock_threshold: int = 1,
        seed_restock_qty: int = 1,
    ) -> None:
        self.crops = crops or ["WHEAT", "CARROT"]
        self.seed_restock_threshold = seed_restock_threshold
        self.seed_restock_qty = seed_restock_qty

    def decide(self, obs: dict) -> dict:
        farm = my_farm(obs)
        private = obs.get("private", {})
        fx, fy = farmer_xy(obs)
        day = int(obs.get("day", 0))
        market = self._plan_market(obs, farm, private)
        target, farmer_cmd = self._plan_farmer(obs, farm, private, day, fx, fy)

        if target is None:
            return build_action([PASS], market)
        tx, ty = target
        if (fx, fy) == (tx, ty):
            return build_action(farmer_cmd, market)
        return build_action([step_toward(fx, fy, tx, ty)], market)

    def _plan_market(self, obs: dict, farm: dict, private: dict) -> list:
        ops: list = []
        seeds = private.get("seeds", {})
        shed = private.get("shed", {})
        money = float(farm.get("money", 0.0))

        for crop in self.crops:
            have = seeds.get(crop, 0)
            if have < self.seed_restock_threshold:
                cost = CROPS[crop]["seed"] * self.seed_restock_qty
                if money >= cost:
                    ops.append([BUY_SEED, crop, self.seed_restock_qty])
                    money -= cost

        for item, amount in shed.items():
            qty = int(amount)
            if qty > 0:
                ops.append([SELL, item, qty])

        return ops

    def _plan_farmer(self, obs, farm, private, day, fx, fy):
        tiles = farm.get("tiles", [])
        seeds = private.get("seeds", {})
        size = len(tiles)
        harvest, water, weed, plant = [], [], [], []

        for y in range(size):
            for x in range(size):
                tile = tiles[y][x]
                if tile is None:
                    if any(seeds.get(c, 0) > 0 for c in self.crops):
                        plant.append((x, y))
                elif isinstance(tile, dict):
                    kind = tile.get("kind")
                    if kind == KIND_PLANT:
                        crop = tile.get("crop")
                        cd = CROPS.get(crop)
                        age = day - int(tile.get("planted_day", day))
                        needs_water = not tile.get("watered_today", False)
                        if cd and cd["ongoing"]:
                            # Ongoing crops (tomato/strawberry): harvest the
                            # accumulated yield as soon as it appears.
                            if tile.get("yield_units", 0) > 0:
                                harvest.append((x, y))
                            elif needs_water:
                                water.append((x, y))
                        elif cd:
                            # One-time crops (wheat/carrot/melon): wait until
                            # max_yield_day so watering maximizes the yield,
                            # then harvest. Never harvest an immature plant.
                            if age >= cd["max_yield_day"] and tile.get("yield_units", 0) > 0:
                                harvest.append((x, y))
                            elif needs_water:
                                water.append((x, y))
                    elif kind == KIND_WEED:
                        weed.append((x, y))

        # Water first: an unwatered plant dies (2 days -> weed). Then harvest
        # (guaranteed money, about to decay), then clear weeds, then plant.
        if water:
            return _nearest(fx, fy, water), [WATER]
        if harvest:
            return _nearest(fx, fy, harvest), [HARVEST]
        if weed:
            return _nearest(fx, fy, weed), [DIG]
        if plant:
            for crop in self.crops:
                if seeds.get(crop, 0) > 0:
                    return _nearest(fx, fy, plant), [PLANT, crop]
        return None, [PASS]


_BRAIN = FarmBrain()


def agent(obs: dict, config: object = None) -> dict:
    return _BRAIN.decide(obs)


def validate_minimal_decision() -> dict:
    obs = {
        "player": 0,
        "day": 0,
        "hour": 0,
        "farms": [
            {
                "money": STARTING_MONEY,
                "farmer": [4, 4],
                "hands": [],
                "unlocked_quadrants": ["NW"],
                "hires_today": 0,
                "tiles": [
                    [None if (x < 5 and y < 5) else "LOCKED" for x in range(10)]
                    for y in range(10)
                ],
            }
        ],
        "market": {
            "inventory": {item: 10000 for item in PRODUCTS},
            "prices": {
                "WHEAT": 25, "CARROT": 35, "TOMATO": 60, "STRAWBERRY": 120,
                "MELON": 250, "EGG": 50, "MILK": 160, "WOOL": 200, "FERTILIZER": 100,
            },
        },
        "town": {"unlocked_shops": []},
        "private": {
            "shed": {item: 0 for item in PRODUCTS + list(ANIMALS)},
            "seeds": {"WHEAT": 1, "CARROT": 0},
            "inventories": [{}],
        },
    }
    return agent(obs, None)
