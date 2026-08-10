"""Real Kaggriculture protocol adapter.

This module mirrors the real community contract in a self-contained way so we
can test the agent locally without Kaggle.
"""

from __future__ import annotations

PASS = "PASS"
NORTH = "NORTH"
SOUTH = "SOUTH"
EAST = "EAST"
WEST = "WEST"
MOVES = (NORTH, SOUTH, EAST, WEST)
WATER = "WATER"
HARVEST = "HARVEST"
DIG = "DIG"
PLANT = "PLANT"
KIND_PLANT = "PLANT"
KIND_WEED = "WEED"
BUY_SEED = "BUY_SEED"
SELL = "SELL"


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


def _as_int_qty(amount: float) -> int:
    return int(amount)


class FarmBrain:
    def __init__(self, crops: list[str] | None = None, seed_restock_threshold: int = 4, seed_restock_qty: int = 4) -> None:
        self.crops = crops or ["WHEAT"]
        self.seed_restock_threshold = seed_restock_threshold
        self.seed_restock_qty = seed_restock_qty

    def decide(self, obs: dict) -> dict:
        farm = my_farm(obs)
        private = obs.get("private", {"seeds": {}, "shed": {}})
        fx, fy = farmer_xy(obs)
        day = int(obs.get("day", 1))

        prices = obs.get("prices")
        seed_costs = obs.get("seed_costs", {})
        if prices:
            preferred_crops = sorted(prices.keys(), key=lambda k: prices[k], reverse=True)
        else:
            preferred_crops = self.crops

        market = self._plan_market(private, farm, preferred_crops, seed_costs)
        target, farmer_cmd = self._plan_farmer(farm, private, day, fx, fy, preferred_crops)

        if target is None:
            return build_action([PASS], market)

        tx, ty = target
        if (fx, fy) == (tx, ty):
            return build_action(farmer_cmd, market)
        return build_action([step_toward(fx, fy, tx, ty)], market)

    def _plan_market(self, private: dict, farm: dict, preferred_crops: list[str], seed_costs: dict) -> list:
        ops: list = []
        seeds = private.get("seeds", {})
        shed = private.get("shed", {})
        available_money = farm.get("money", 0.0)

        for crop in preferred_crops:
            if seeds.get(crop, 0) < self.seed_restock_threshold:
                cost = self.seed_restock_qty * seed_costs.get(crop, 15.0)
                if available_money >= cost:
                    ops.append([BUY_SEED, crop, self.seed_restock_qty])
                    available_money -= cost

        for crop, amount in shed.items():
            qty = _as_int_qty(amount)
            if qty > 0:
                ops.append([SELL, crop, qty])

        return ops

    def _plan_farmer(self, farm, private, day, fx, fy, preferred_crops):
        tiles = farm.get("tiles", [])
        seeds = private.get("seeds", {})
        size = len(tiles)
        harvest, water, weed, plant = [], [], [], []

        for y in range(size):
            for x in range(len(tiles[y])):
                tile = tiles[y][x]
                if tile is None:
                    plant.append((x, y))
                    continue
                if not isinstance(tile, dict):
                    continue
                kind = tile.get("kind")
                if kind == KIND_PLANT:
                    if day - int(tile.get("planted_day", day)) >= 2:
                        harvest.append((x, y))
                    elif not tile.get("watered_today", False):
                        water.append((x, y))
                elif kind == KIND_WEED:
                    weed.append((x, y))

        have_seed = any(seeds.get(c, 0) > 0 for c in preferred_crops)
        if harvest:
            return _nearest(fx, fy, harvest), [HARVEST]
        if water:
            return _nearest(fx, fy, water), [WATER]
        if weed:
            return _nearest(fx, fy, weed), [DIG]
        if plant and have_seed:
            crop = next(c for c in preferred_crops if seeds.get(c, 0) > 0)
            return _nearest(fx, fy, plant), [PLANT, crop]
        return None, [PASS]


_BRAIN = FarmBrain()


def agent(obs: dict, config: object = None) -> dict:
    return _BRAIN.decide(obs)


def validate_minimal_decision() -> dict:
    obs = {
        "player": 0,
        "day": 1,
        "farms": [
            {
                "farmer": [0, 0],
                "money": 100.0,
                "tiles": [[None, None], [None, None]],
            }
        ],
        "private": {"seeds": {"WHEAT": 1}, "shed": {}},
    }
    return agent(obs, None)
