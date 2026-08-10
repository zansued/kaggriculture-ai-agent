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

# Static crop economics used when market prices are not observable in the obs.
# Values mirror the reference/local_env.py Mechanics defaults.
CROP_ECONOMICS = {
    "WHEAT": {"seed_cost": 10.0, "sell_price": 15.0, "base_yield": 3.0},
    "CORN": {"seed_cost": 15.0, "sell_price": 26.0, "base_yield": 3.0},
}


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
    def __init__(
        self,
        crops: list[str] | None = None,
        seed_restock_threshold: int = 4,
        seed_restock_qty: int = 4,
    ) -> None:
        # Crops we are willing to grow, ranked by profitability at decision time.
        self.crops = crops or ["WHEAT", "CORN"]
        self.seed_restock_threshold = seed_restock_threshold
        self.seed_restock_qty = seed_restock_qty

    # ---- public entrypoint ------------------------------------------------- #
    def decide(self, obs: dict) -> dict:
        farm = my_farm(obs)
        private = obs.get("private", {"seeds": {}, "shed": {}})
        fx, fy = farmer_xy(obs)
        day = int(obs.get("day", 1))
        market = self._plan_market(farm, private, obs)
        target, farmer_cmd = self._plan_farmer(farm, private, day, fx, fy, obs)

        if target is None:
            return build_action([PASS], market)

        tx, ty = target
        if (fx, fy) == (tx, ty):
            return build_action(farmer_cmd, market)
        return build_action([step_toward(fx, fy, tx, ty)], market)

    # ---- market: buy seeds / sell shed, in profitability order ------------ #
    def _plan_market(self, farm: dict, private: dict, obs: dict) -> list:
        ops: list = []
        seeds = private.get("seeds", {})
        shed = private.get("shed", {})
        money = float(farm.get("money", 0.0))

        for crop in self._preferred_crops(obs):
            if seeds.get(crop, 0) >= self.seed_restock_threshold:
                continue
            seed_cost = self._seed_cost(crop)
            if seed_cost is None or seed_cost <= 0:
                continue
            qty = self.seed_restock_qty
            cost = qty * seed_cost
            if cost > money:
                affordable = int(money // seed_cost)
                if affordable <= 0:
                    continue
                qty = min(qty, affordable)
                cost = qty * seed_cost
            ops.append([BUY_SEED, crop, qty])
            money -= cost

        for crop, amount in shed.items():
            qty = _as_int_qty(amount)
            if qty > 0:
                ops.append([SELL, crop, qty])

        return ops

    # ---- farmer: harvest > water > weed > plant (preferred crop) ----------- #
    def _plan_farmer(self, farm, private, day, fx, fy, obs):
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

        if harvest:
            return _nearest(fx, fy, harvest), [HARVEST]
        if water:
            return _nearest(fx, fy, water), [WATER]
        if weed:
            return _nearest(fx, fy, weed), [DIG]
        if plant:
            for crop in self._preferred_crops(obs):
                if seeds.get(crop, 0) > 0:
                    return _nearest(fx, fy, plant), [PLANT, crop]
        return None, [PASS]

    # ---- crop selection by profitability ----------------------------------- #
    def _preferred_crops(self, obs: dict) -> list[str]:
        """Return crops sorted by profitability (best first)."""
        prices = self._market_prices(obs)
        return sorted(
            self.crops,
            key=lambda c: self._net_profit(c, prices),
            reverse=True,
        )

    def _market_prices(self, obs: dict) -> dict | None:
        """Live sell prices from the obs, if the env exposes them."""
        if not isinstance(obs, dict):
            return None
        market = obs.get("market")
        if isinstance(market, dict):
            prices = market.get("prices")
            if isinstance(prices, dict):
                return prices
        prices = obs.get("prices")
        if isinstance(prices, dict):
            return prices
        return None

    def _net_profit(self, crop: str, prices: dict | None) -> float:
        """Expected net profit per seed: sell_price * base_yield - seed_cost."""
        spec = CROP_ECONOMICS.get(crop)
        if spec is None:
            return 0.0
        sell_price = spec["sell_price"]
        if prices and crop in prices:
            try:
                sell_price = float(prices[crop])
            except (TypeError, ValueError):
                pass
        return sell_price * spec["base_yield"] - spec["seed_cost"]

    def _seed_cost(self, crop: str) -> float | None:
        spec = CROP_ECONOMICS.get(crop)
        return spec["seed_cost"] if spec else None


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
