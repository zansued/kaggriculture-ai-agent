"""FarmBrain — the real-protocol decision policy.

Pure, dependency-free logic (stdlib only) so it can be inlined into a Kaggle
submission. Given a real `obs`, it returns a real action dict.

Strategy (a generalized, tidied version of the reference agent):
  1. Market first (free, no movement): keep each crop's seeds stocked, and sell
     anything sitting in the shed.
  2. Pick the highest-priority tile to work:
        harvest-ready  >  needs-water  >  weed  >  plantable (if seeds on hand)
     Among equal priority, choose the tile NEAREST the farmer (Manhattan) so we
     waste fewer of the 720 turns walking.
  3. If standing on the target, do the tile action; otherwise take one step
     toward it. If there is nothing to do, PASS.
"""

from __future__ import annotations

from . import protocol as P


class FarmBrain:
    def __init__(
        self,
        crops: list[str] | None = None,
        seed_restock_threshold: int = 4,
        seed_restock_qty: int = 4,
    ) -> None:
        # Priority order of crops to grow/stock (first is preferred for planting).
        self.crops = crops or ["WHEAT"]
        self.seed_restock_threshold = seed_restock_threshold
        self.seed_restock_qty = seed_restock_qty

    # ---- public entrypoint ------------------------------------------------- #
    def decide(self, obs: dict) -> dict:
        farm = P.my_farm(obs)
        private = obs["private"]
        fx, fy = P.farmer_xy(obs)
        day = obs["day"]

        market = self._plan_market(farm, private)
        target, farmer_cmd = self._plan_farmer(farm, private, day, fx, fy)

        if target is None:
            return P.build_action([P.PASS], market)
        tx, ty = target
        if (fx, fy) == (tx, ty):
            return P.build_action(farmer_cmd, market)
        return P.build_action([P.step_toward(fx, fy, tx, ty)], market)

    # ---- 1. market --------------------------------------------------------- #
    def _plan_market(self, farm: dict, private: dict) -> list:
        ops: list = []
        seeds = private["seeds"]
        shed = private["shed"]
        money = farm["money"]

        # Restock the cheapest-affordable seeds we are low on (preferred first).
        for crop in self.crops:
            have = seeds.get(crop, 0)
            if have < self.seed_restock_threshold:
                ops.append([P.BUY_SEED, crop, self.seed_restock_qty])

        # Sell everything harvested — cash now beats crop sitting idle.
        for crop, amount in shed.items():
            qty = _as_int_qty(amount)
            if qty > 0:
                ops.append([P.SELL, crop, qty])
        return ops

    # ---- 2+3. choose a tile and the command to work it --------------------- #
    def _plan_farmer(self, farm, private, day, fx, fy):
        tiles = farm["tiles"]
        seeds = private["seeds"]
        size = len(tiles)

        harvest, water, weed, plant = [], [], [], []
        for y in range(size):
            for x in range(size):
                tile = tiles[y][x]
                if tile is None:
                    plant.append((x, y))
                elif isinstance(tile, dict):
                    kind = tile.get("kind")
                    if kind == P.KIND_PLANT:
                        if day - tile["planted_day"] >= 2:  # mature (confirmed)
                            harvest.append((x, y))
                        elif not tile.get("watered_today", False):
                            water.append((x, y))
                    elif kind == P.KIND_WEED:
                        weed.append((x, y))

        have_seed = any(seeds.get(c, 0) > 0 for c in self.crops)

        if harvest:
            return _nearest(fx, fy, harvest), [P.HARVEST]
        if water:
            return _nearest(fx, fy, water), [P.WATER]
        if weed:
            return _nearest(fx, fy, weed), [P.DIG]
        if plant and have_seed:
            crop = next(c for c in self.crops if seeds.get(c, 0) > 0)
            return _nearest(fx, fy, plant), [P.PLANT, crop]
        return None, [P.PASS]


# ---- helpers --------------------------------------------------------------- #
def _nearest(fx: int, fy: int, cells: list[tuple[int, int]]) -> tuple[int, int]:
    return min(cells, key=lambda c: abs(c[0] - fx) + abs(c[1] - fy))


def _as_int_qty(amount: float) -> int:
    """Market quantities are whole units; never over-sell a fractional shed."""
    return int(amount)
