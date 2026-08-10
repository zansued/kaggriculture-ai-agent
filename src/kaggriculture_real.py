"""Real Kaggriculture agent — built against the actual engine contract.

The engine ships inside `kaggle_environments` (envs/kaggriculture/). This module
is SELF-CONTAINED (stdlib only) so it can be submitted as a single `main.py`:
it inlines every protocol constant needed at decision time.

Strategy:
  1. Market: sell everything in the shed; buy seeds for the most profitable
     crop we can afford (price-aware via obs.market.prices); HIRE farm hands
     at the start of each day (cheap: fib 1,1,2,3,5...).
  2. Coordinate the farmer + hired hands on the highest-priority tasks:
        water (plants die after 2 unwatered days)  >  harvest  >  dig weed  >  plant
     Each unit takes the nearest unassigned task so work is spread.
  3. Harvest one-time crops only at max_yield_day (watering through the bonus
     window maximizes yield); harvest ongoing crops as soon as yield appears.
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
TURNS_PER_DAY = 24
SEASON_DAYS = 30
SHED_CAPACITY = 100
MAX_MARKET_ORDERS = 10

# Actions
PASS = "PASS"; NORTH = "NORTH"; SOUTH = "SOUTH"; EAST = "EAST"; WEST = "WEST"
MOVES = (NORTH, SOUTH, EAST, WEST)
WATER = "WATER"; HARVEST = "HARVEST"; DIG = "DIG"; PLANT = "PLANT"
KIND_PLANT = "PLANT"; KIND_WEED = "WEED"
BUY_SEED = "BUY_SEED"; SELL = "SELL"; HIRE = "HIRE"; BUY_LAND = "BUY_LAND"


def build_action(farmer_cmd: list, hands_cmds: list | None = None, market: list | None = None) -> dict:
    return {"farmer": list(farmer_cmd), "hands": [list(c) for c in (hands_cmds or [])], "market": market or []}


def pass_action(market: list | None = None) -> dict:
    return build_action([PASS], [], market)


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


def _manhattan(a: tuple[int, int], b: tuple[int, int]) -> int:
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def _fib(n: int) -> int:
    """Engine HIRE cost: fib starts 1,1,2,3,5... _fib(0)=1, _fib(1)=1, _fib(2)=2."""
    a, b = 1, 1
    for _ in range(n):
        a, b = b, a + b
    return a


def _unfertilized_yield(crop: str) -> int:
    """Max harvestable units for a one-time crop watered daily through its bonus window."""
    cd = CROPS[crop]
    if cd["ongoing"]:
        return cd["max_yield"]  # total scheduled productions
    window_start = (cd["max_yield_day"] + 1) // 2
    bonus_days = cd["max_yield_day"] - window_start + 1
    return min(cd["max_yield"], 1 + bonus_days)


class FarmBrain:
    # Products whose market price crashes hard when we oversell (base > 100,
    # with a sharp above-I0 shape). Selling too many of these per turn floods
    # the shared market and drives the price to the $1 floor.
    PREMIUM = {"MELON", "STRAWBERRY"}

    def __init__(
        self,
        crops: list[str] | None = None,
        max_hands: int = 2,
        seed_buffer: int = 6,
        buy_land_day: int | None = None,
        premium_sell_per_turn: int = 2,
        max_premium_plants: int | None = None,
    ) -> None:
        # Candidate crops (price-aware selection picks the best among these).
        self.crops = crops or list(CROPS.keys())
        self.max_hands = max_hands
        self.seed_buffer = seed_buffer  # keep at least this many seeds per crop
        self.buy_land_day = buy_land_day  # buy NE quadrant on this day if affordable
        self.premium_sell_per_turn = premium_sell_per_turn  # cap premium units/turn
        # Max simultaneous premium plants on the field. Capping production
        # avoids flooding the shared market (town drains only ~1 premium/day).
        self.max_premium_plants = max_premium_plants

    # ---- public entrypoint ------------------------------------------------- #
    def decide(self, obs: dict) -> dict:
        farm = my_farm(obs)
        private = obs.get("private", {})
        day = int(obs.get("day", 0))
        hour = int(obs.get("hour", 0))
        positions = [tuple(farm["farmer"])] + [tuple(h) for h in farm.get("hands", [])]

        market = self._plan_market(obs, farm, private, day, hour)
        cmds = self._plan_units(obs, farm, private, day, positions)

        farmer_cmd = cmds[0] if cmds else [PASS]
        hands_cmds = cmds[1:] if len(cmds) > 1 else []
        return build_action(farmer_cmd, hands_cmds, market)

    # ---- 1. market --------------------------------------------------------- #
    def _plan_market(self, obs: dict, farm: dict, private: dict, day: int, hour: int) -> list:
        ops: list = []
        seeds = private.get("seeds", {})
        shed = private.get("shed", {})
        money = float(farm.get("money", 0.0))

        # Sell everything in the shed — cash now beats sitting inventory.
        # Premium goods (melon/strawberry) crash the shared market if we dump
        # too many at once, so cap how many of each we sell per turn. The shed
        # caps at 100 units, so this is a timing lever, not a stockpile one.
        for item, amount in shed.items():
            qty = int(amount)
            if qty <= 0:
                continue
            if item in self.PREMIUM:
                qty = min(qty, self.premium_sell_per_turn)
            if qty > 0:
                ops.append([SELL, item, qty])

        # HIRE hands at the start of each day. Cheap: first two cost $1 each.
        if hour == 0:
            n_hired = int(farm.get("hires_today", 0))
            want = max(0, self.max_hands - len(farm.get("hands", [])))
            for _ in range(want):
                cost = _fib(n_hired)
                if money < cost:
                    break
                ops.append([HIRE])
                money -= cost
                n_hired += 1

        # Buy land (NE quadrant) on the chosen day if affordable.
        if self.buy_land_day is not None and day >= self.buy_land_day:
            if "NE" not in farm.get("unlocked_quadrants", []) and money >= 1000:
                ops.append([BUY_LAND])
                money -= 1000

        # Buy seeds for the most profitable affordable crop(s). Skip premium
        # crops when we already have enough active plants (production cap).
        preferred = self._preferred_crops(obs, farm, day)
        active_premium = self._count_premium_plants(farm)
        for crop in preferred:
            if (
                crop in self.PREMIUM
                and self.max_premium_plants is not None
                and active_premium >= self.max_premium_plants
            ):
                continue
            have = seeds.get(crop, 0)
            if have < self.seed_buffer and money >= CROPS[crop]["seed"]:
                ops.append([BUY_SEED, crop, 1])
                money -= CROPS[crop]["seed"]
                if len(ops) >= MAX_MARKET_ORDERS:
                    break

        return ops[:MAX_MARKET_ORDERS]

    # ---- 2. unit coordination ---------------------------------------------- #
    def _plan_units(self, obs, farm, private, day, positions):
        tiles = farm.get("tiles", [])
        seeds = private.get("seeds", {})
        size = len(tiles)
        # priority buckets: water first (death), then harvest, dig, plant.
        water, harvest, weed, plant = [], [], [], []
        preferred = self._preferred_crops(obs, farm, day)

        for y in range(size):
            for x in range(size):
                tile = tiles[y][x]
                if tile is None:
                    if any(seeds.get(c, 0) > 0 for c in preferred):
                        plant.append((x, y))
                elif isinstance(tile, dict):
                    kind = tile.get("kind")
                    if kind == KIND_PLANT:
                        crop = tile.get("crop")
                        cd = CROPS.get(crop)
                        needs_water = not tile.get("watered_today", False)
                        if cd and cd["ongoing"]:
                            if tile.get("yield_units", 0) > 0:
                                harvest.append((x, y))
                            elif needs_water:
                                water.append((x, y))
                        elif cd:
                            age = day - int(tile.get("planted_day", day))
                            if age >= cd["max_yield_day"] and tile.get("yield_units", 0) > 0:
                                harvest.append((x, y))
                            elif needs_water:
                                water.append((x, y))
                    elif kind == KIND_WEED:
                        weed.append((x, y))

        active_premium = self._count_premium_plants(farm)

        # Crop order for planting: preferred list, but skip premium crops once
        # we've hit the production cap.
        def _plantable_crop():
            for c in preferred:
                if seeds.get(c, 0) > 0:
                    if (
                        c in self.PREMIUM
                        and self.max_premium_plants is not None
                        and active_premium >= self.max_premium_plants
                    ):
                        continue
                    return c
            return None

        # Ordered task list: water(rank 0) > harvest(1) > dig(2) > plant(3).
        tasks = []
        for xy in water:
            tasks.append((0, xy, [WATER]))
        for xy in harvest:
            tasks.append((1, xy, [HARVEST]))
        for xy in weed:
            tasks.append((2, xy, [DIG]))
        for xy in plant:
            crop = _plantable_crop()
            if crop:
                tasks.append((3, xy, [PLANT, crop]))

        # Assign each unit the nearest unassigned task (lower rank wins).
        assigned = set()
        cmds = []
        for pos in positions:
            best = None
            for rank, xy, action in tasks:
                if xy in assigned:
                    continue
                d = _manhattan(pos, xy)
                key = (rank, d)
                if best is None or key < best[0]:
                    best = (key, xy, action)
            if best is None:
                cmds.append([PASS])
                continue
            (_, _), xy, action = best
            assigned.add(xy)
            if pos == xy:
                cmds.append(action)
            else:
                cmds.append([step_toward(pos[0], pos[1], xy[0], xy[1])])
        return cmds

    # ---- 3. premium production cap ------------------------------------------- #
    def _count_premium_plants(self, farm) -> int:
        tiles = farm.get("tiles", [])
        return sum(
            1
            for y in range(len(tiles))
            for x in range(len(tiles[y]))
            if isinstance(tiles[y][x], dict)
            and tiles[y][x].get("kind") == KIND_PLANT
            and tiles[y][x].get("crop") in self.PREMIUM
        )

    # ---- 4. price-aware crop selection -------------------------------------- #
    def _preferred_crops(self, obs, farm, day) -> list[str]:
        prices = obs.get("market", {}).get("prices", {})
        scored = []
        for crop in self.crops:
            cd = CROPS[crop]
            # Must mature before season end (planting day counts toward growth).
            if day + cd["max_yield_day"] > SEASON_DAYS - 1:
                continue
            yield_est = _unfertilized_yield(crop)
            price = prices.get(crop, cd.get("base", 0))
            profit = yield_est * price - cd["seed"]
            scored.append((profit, crop))
        scored.sort(reverse=True)
        return [c for _, c in scored]


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
            "seeds": {"WHEAT": 1, "CARROT": 0, "TOMATO": 0, "STRAWBERRY": 0, "MELON": 0},
            "inventories": [{}],
        },
    }
    return agent(obs, None)
