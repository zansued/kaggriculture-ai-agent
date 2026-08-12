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

# Base market prices (from the competition rules / MARKET_PARAMS). Used to
# judge whether the CURRENT market price signals strong or weak demand.
BASE_PRICES = {
    "WHEAT": 25, "CARROT": 35, "TOMATO": 60, "STRAWBERRY": 120, "MELON": 250,
    "EGG": 50, "MILK": 160, "WOOL": 200, "FERTILIZER": 100,
}

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
BUILD_COOP = "BUILD_COOP"; BUILD_PASTURE = "BUILD_PASTURE"
FEED = "FEED"; CARE = "CARE"; COLLECT_FERTILIZER = "COLLECT_FERTILIZER"
PICKUP = "PICKUP"; PLACE = "PLACE"; FERTILIZE = "FERTILIZE"
KIND_PLANT = "PLANT"; KIND_WEED = "WEED"
KIND_COOP = "COOP"; KIND_PASTURE = "PASTURE"
BUY_SEED = "BUY_SEED"; BUY_ANIMAL = "BUY_ANIMAL"; BUY_PRODUCT = "BUY_PRODUCT"
SELL = "SELL"; HIRE = "HIRE"; BUY_LAND = "BUY_LAND"


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


SHED_TILES = [(4, 4), (5, 4), (4, 5), (5, 5)]


def _shed_tile(farm) -> tuple[int, int]:
    """Nearest shed-access tile to the farmer (shed-adjacent positions)."""
    fx, fy = farm.get("farmer", [4, 4])
    return min(SHED_TILES, key=lambda t: _manhattan((fx, fy), t))


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
    # the shared market and drives the price to the $1 floor. The sell logic is
    # dynamic: strong prices (market hungry, e.g. milk/strawberry with shop
    # demand) → sell fast; weak prices (glut) → dribble/hold.
    PREMIUM = {"MELON", "STRAWBERRY", "MILK", "WOOL"}

    def __init__(
        self,
        crops: list[str] | None = None,
        max_hands: int = 2,
        seed_buffer: int = 6,
        buy_land_day: int | None = None,
        premium_sell_per_turn: int = 2,
        max_premium_plants: int | None = None,
        premium_sell_floor: float | None = 100,
        fert_strawberry: bool = True,
        animal: str | None = None,  # experimental; off by default (logistics > value)
        animal_day: int = 1,
        melon_plant_gate: float | None = 240,  # stop planting melon when price < gate
        melon_focus: bool = False,  # while gate open, buy/plant ONLY melon
        harvest_at_cap: bool = True,  # harvest one-time crops as soon as yield caps
        livestock: bool = True,  # full animal economy (cows+sheep+strawberry)
        animal_plan: list | None = None,  # e.g. [("COW",4),("SHEEP",3)]
        livestock_hands: int = 8,  # hands to hire daily in livestock mode
        max_melon_plants: int | None = None,  # cap total melon plants (livestock)
        max_wheat_plants: int | None = None,  # cap total wheat plants (livestock)
        strawberry_target: int = 0,  # maintain this many strawberry plants (0=off)
        seed_buffers: dict | None = None,  # per-crop seed buffer override
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
        # Don't sell premium goods below this price (hold in shed until the
        # market recovers); always dump in the final days of the season so no
        # value is left in the shed.
        self.premium_sell_floor = premium_sell_floor
        # Fertilize strawberry: buy one fertilizer and apply it on the day the
        # plant reaches first_yield_day so its first two productions (day X and
        # X+interval) are doubled. Net value: +2 units * base ~ $120 each = +$240
        # gross - $100 cost = +$140. Only applied when a strawberry exists and
        # the market price makes the expected gain positive.
        self.fert_strawberry = fert_strawberry
        # Optional livestock: one animal type ("GOOSE"/"COW"/"SHEEP") bought on
        # `animal_day`, fed wheat daily, harvested for product + free fertilizer.
        self.animal = animal
        self.animal_day = animal_day
        # Melon has NO shop demand (only the town center drains ~1/day). Once the
        # market is saturated (melon price below this gate) further melon planting
        # just floods the market and crashes the price to $1 — switch to crops the
        # town actually consumes (wheat/carrot/strawberry/tomato) instead.
        self.melon_plant_gate = melon_plant_gate
        # Concentrate ALL seed money and planting on melons while the gate is
        # open (melon is by far the best per-tile crop), then diversify once the
        # market saturates. Avoids spreading early cash across all crops.
        self.melon_focus = melon_focus
        # One-time crops cap their yield before max_yield_day (melon caps at age
        # 10 vs max_yield_day 12). Harvesting as soon as the yield is maxed frees
        # the tile ~2 days earlier per cycle for replanting.
        self.harvest_at_cap = harvest_at_cap
        # Full livestock economy (cows+sheep). Animals produce milk/wool plus 1
        # fertilizer/day each, and their products have shop demand (unlike melon)
        # so prices hold. Needs many hands for daily feed/collect chores.
        self.livestock = livestock
        if livestock and animal_plan is None:
            # 8 cows + 6 sheep (purearch scale) with 8 hands benchmarked best.
            animal_plan = [("COW", 8), ("SHEEP", 6)]
        self.animal_plan = animal_plan or []
        if livestock:
            self.max_hands = max(self.max_hands, livestock_hands)
            # The livestock economy farms melon (early cash wave) + wheat
            # (feed/sell) + strawberry (main late income). Tiles are the scarce
            # resource: 14 animal structures leave only ~11 crop tiles, so melon
            # is kept small (early cash only) and strawberry gets the tiles in
            # the second half once melon is harvested.
            if crops is None:
                self.crops = ["MELON", "WHEAT", "STRAWBERRY"]
            if max_melon_plants is None:
                max_melon_plants = 6
            if max_wheat_plants is None:
                max_wheat_plants = None
            if seed_buffers is None:
                seed_buffers = {"MELON": 3, "WHEAT": 8, "STRAWBERRY": 6}
        self.max_melon_plants = max_melon_plants
        self.max_wheat_plants = max_wheat_plants
        self.strawberry_target = strawberry_target
        self.seed_buffers = seed_buffers or {}

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
        # too many at once, so cap how many of each we sell per turn. Also hold
        # them when the price is below a floor (the town drains the market and
        # the price recovers). Always dump in the final days of the season so
        # no value is left sitting in the shed.
        prices = obs.get("market", {}).get("prices", {})
        # Livestock feed reserve: never sell wheat that animals need. Match the
        # buy-side 2-day buffer so wheat doesn't oscillate buy-then-sell.
        feed_reserve = 0
        if self.livestock:
            invs = private.get("inventories", [])
            pending = sum(shed.get(a, 0) + sum(inv.get(a, 0) for inv in invs)
                          for a, _ in self.animal_plan)
            feed_reserve = (self._total_animals(farm) + pending) * 2
        for item, amount in shed.items():
            qty = int(amount)
            if qty <= 0:
                continue
            if item in ANIMALS:
                # Never sell animals — they're bought for placement, not resale.
                continue
            if self.livestock and item == "WHEAT":
                qty = max(0, qty - feed_reserve)
                if qty <= 0:
                    continue
            if self.livestock and self.fert_strawberry and item == "FERTILIZER":
                # Reserve free animal fertilizer for strawberry only while a
                # fertilized strawberry unit is worth more than selling the
                # fertilizer. FERTILIZE doubles one production (+1 strawberry)
                # but costs 1 fertilizer; if the fertilizer price is higher,
                # selling it is the better use.
                st_price = prices.get("STRAWBERRY", 0)
                fert_price = prices.get("FERTILIZER", 100)
                reserve = self._strawberry_fert_reserve(farm) if st_price >= fert_price else 0
                qty = max(0, qty - reserve)
                if qty <= 0:
                    continue
            if item in self.PREMIUM:
                price = prices.get(item, 0)
                base = BASE_PRICES.get(item, 100)
                if day >= SEASON_DAYS - 2:
                    pass  # final days: dump everything, don't cap
                elif price >= base * 1.5:
                    # Market is hungry (e.g. milk/strawberry with shop demand):
                    # sell as fast as the market queue allows.
                    qty = min(qty, 10)
                elif price >= base * 1.1:
                    qty = min(qty, 6)
                elif self.premium_sell_floor is not None and price < self.premium_sell_floor:
                    continue  # hold; price too low, town will drain and recover
                else:
                    qty = min(qty, self.premium_sell_per_turn)  # dribble, don't flood
            if qty > 0:
                ops.append([SELL, item, qty])
                # Track expected cash from this sale so buy decisions below use
                # a realistic budget (the engine credits sell proceeds before the
                # market phase's buys are processed).
                money += qty * prices.get(item, 0)

        # Buy land quadrants after `buy_land_day`, staggered, keeping a cash
        # buffer so the animal/feed budget is never starved. The engine buys
        # quadrants in order (NE $1000, SW $2000, SE $4000). Cap at NE+SW (the
        # top agent's footprint); SE is too expensive and spreads us too thin.
        if self.buy_land_day is not None and day >= self.buy_land_day:
            n_unlocked = len(farm.get("unlocked_quadrants", []))  # NW always counts
            if n_unlocked < 3:  # at most NE + SW
                next_cost = (1000, 2000, 4000)[n_unlocked - 1]
                if day >= self.buy_land_day + (n_unlocked - 1) * 3:
                    if money >= next_cost + 400:  # keep ~$400 float for feed
                        ops.append([BUY_LAND])
                        money -= next_cost

        # Full livestock economy: buy cows+sheep per the plan, keep wheat feed.
        # The market queue is capped at MAX_MARKET_ORDERS and processed in order,
        # so ordering here is critical: feed FIRST (animals die without it), then
        # ANIMALS at hour 0 (the core engine — buy aggressively early so they
        # start producing fertilizer ASAP), then hands, then seeds fill what's
        # left. On day 0 this matches the reference agent's 4-animal opening.
        if self.livestock:
            invs = private.get("inventories", [])
            n_animals = self._total_animals(farm)
            n_pending = sum(
                shed.get(a, 0) + sum(inv.get(a, 0) for inv in invs)
                for a, _ in self.animal_plan
            )
            # 1) FEED: top up to a 2-day buffer every turn so the herd never
            #    starves while other orders churn. Sells reserve the same buffer
            #    (see feed_reserve above) so there is no buy/sell oscillation.
            feed_need = (n_animals + n_pending) * 2
            have_wheat = shed.get("WHEAT", 0) + sum(inv.get("WHEAT", 0) for inv in invs)
            wheat_price = prices.get("WHEAT", 25)
            if feed_need > 0 and have_wheat < feed_need and money >= wheat_price:
                # Buy at the real price; when wheat is scarce/expensive buy less
                # (rely on grown wheat / town drain) — never let the 2-day buffer
                # goal blow the feed budget.
                want = min(feed_need - have_wheat, 6 if wheat_price <= 30 else 4)
                ops.append([BUY_PRODUCT, "WHEAT", want])
                money -= wheat_price * want
            # 2) ANIMALS: at hour 0 only, one per type (COW then SHEEP) while
            #    the plan/placeability/feed-budget allow. Placed BEFORE hiring
            #    so the market-order cap never starves the animal buys.
            if hour == 0:
                for animal, target in self.animal_plan:
                    a = ANIMALS[animal]
                    placed = self._placed_count(farm, animal)
                    in_shed = shed.get(animal, 0)
                    in_inv = sum(inv.get(animal, 0) for inv in invs)
                    owned = placed + in_shed + in_inv
                    if owned >= target:
                        continue
                    placeable = (
                        self._find_empty_structure(farm, a["structure"]) is not None
                        or self._first_empty_tile(farm) is not None
                    )
                    # 2 days of feed for the herd including this new animal.
                    feed_cash = (n_animals + n_pending + 1) * 2 * 25
                    if placeable and money >= a["cost"] + feed_cash:
                        ops.append([BUY_ANIMAL, animal, 1])
                        money -= a["cost"]
                        n_animals += 1
                        n_pending += 1
                        if len(ops) >= MAX_MARKET_ORDERS:
                            return ops[:MAX_MARKET_ORDERS]
            # 3) HIRE: spread across the day (max 2/turn) so hands ramp up
            #    without consuming the whole hour-0 market budget.
            n_hands = len(farm.get("hands", []))
            if n_hands < self.max_hands:
                n_hired = int(farm.get("hires_today", 0))
                for _ in range(min(2, self.max_hands - n_hands)):
                    cost = _fib(n_hired)
                    if money < cost:
                        break
                    ops.append([HIRE])
                    money -= cost
                    n_hired += 1

        # Buy seeds for the most profitable affordable crop(s). Skip premium
        # crops when we already have enough active plants (production cap).
        preferred = self._preferred_crops(obs, farm, day)
        active_premium = self._count_premium_plants(farm)
        active_melon = self._count_melon_plants(farm)
        active_wheat = self._count_wheat_plants(farm)
        for crop in preferred:
            if (
                crop in self.PREMIUM
                and self.max_premium_plants is not None
                and active_premium >= self.max_premium_plants
            ):
                continue
            if (
                crop == "MELON"
                and self.max_melon_plants is not None
                and active_melon >= self.max_melon_plants
            ):
                continue
            if (
                crop == "WHEAT"
                and self.max_wheat_plants is not None
                and active_wheat >= self.max_wheat_plants
            ):
                continue
            buffer = self.seed_buffers.get(crop, self.seed_buffer)
            have = seeds.get(crop, 0)
            if have < buffer and money >= CROPS[crop]["seed"]:
                ops.append([BUY_SEED, crop, 1])
                money -= CROPS[crop]["seed"]
                if len(ops) >= MAX_MARKET_ORDERS:
                    break

        # Optional livestock: buy the animal on `animal_day`; keep a wheat stock
        # for daily feed (animals escape after 2 unfed days). Buy wheat only
        # after the animal is placed (we know we have it once shed has it).
        if self.animal is not None:
            a = ANIMALS[self.animal]
            if day >= self.animal_day and shed.get(self.animal, 0) == 0 and not self._animal_placed(farm):
                if money >= a["cost"]:
                    ops.append([BUY_ANIMAL, self.animal, 1])
                    money -= a["cost"]
            # Feed wheat reserve: keep ~2 wheat in the shed for daily feed.
            have_wheat = shed.get("WHEAT", 0)
            if day >= self.animal_day and self._animal_placed(farm) and have_wheat < 3:
                if money >= 25:  # wheat market price ~25
                    ops.append([BUY_PRODUCT, "WHEAT", 3 - have_wheat])
                    money -= 25 * (3 - have_wheat)

        return ops[:MAX_MARKET_ORDERS]

    # ---- 2. unit coordination ---------------------------------------------- #
    def _plan_units(self, obs, farm, private, day, positions):
        tiles = farm.get("tiles", [])
        seeds = private.get("seeds", {})
        size = len(tiles)
        inventories = private.get("inventories", [])
        # priority buckets: water first (death), then harvest, dig, plant.
        # water_at_risk = plants one day from weeding (2 unwatered days -> weed).
        # harvest_full = ongoing crop about to cap its yield (must reap or the
        # next production is wasted).
        water, water_at_risk, harvest, harvest_full, weed, plant = [], [], [], [], [], []
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
                            # Ongoing crops MUST be watered every day to survive
                            # (2 unwatered days -> weed) AND harvested when they
                            # hold yield. The old if/elif meant a plant with
                            # yield>0 only got harvested and never watered, so
                            # it withered and strawberry production collapsed.
                            if needs_water:
                                if int(tile.get("consecutive_unwatered", 0)) >= 1:
                                    water_at_risk.append((x, y))
                                else:
                                    water.append((x, y))
                            y_units = int(tile.get("yield_units", 0))
                            if y_units >= cd["max_yield"] - 1:
                                harvest_full.append((x, y))  # about to cap: reap now
                            elif y_units > 0:
                                harvest.append((x, y))
                        elif cd:
                            age = day - int(tile.get("planted_day", day))
                            yield_units = tile.get("yield_units", 0)
                            # One-time crops cap their yield before max_yield_day
                            # (melon caps at age 10 vs max_yield_day 12). If
                            # harvest_at_cap, reap as soon as yield is maxed to
                            # free the tile ~2 days earlier per cycle.
                            at_cap = yield_units >= cd["max_yield"]
                            if (age >= cd["max_yield_day"] or (self.harvest_at_cap and at_cap)) and yield_units > 0:
                                harvest.append((x, y))
                            elif needs_water:
                                if int(tile.get("consecutive_unwatered", 0)) >= 1:
                                    water_at_risk.append((x, y))
                                else:
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
                    if (
                        c == "MELON"
                        and self.max_melon_plants is not None
                        and self._count_melon_plants(farm) >= self.max_melon_plants
                    ):
                        continue
                    if (
                        c == "WHEAT"
                        and self.max_wheat_plants is not None
                        and self._count_wheat_plants(farm) >= self.max_wheat_plants
                    ):
                        continue
                    return c
            return None

        # ---- livestock tasks ------------------------------------------------ #
        # Priority is higher than planting so we don't let animals escape.
        animal_tasks = self._plan_animal_tasks(obs, farm, private, day, size)

        # ---- strawberry fertilizer ------------------------------------------- #
        # Applying free animal fertilizer to production-day strawberries doubles
        # that production. The FIRST hand is dedicated to the fertilizer chain
        # (PICKUP -> FERTILIZE) whenever there is work, so the hand carrying
        # fertilizer is never pulled away to feed/farm chores mid-chain. When
        # the specialist is off, fert tasks fall into the shared pool instead.
        fert_targets = self._find_fert_targets(obs, farm, day, size)
        fert_specialist_cmd = None
        if self.livestock and fert_targets and len(positions) > 1:
            hx, hy = positions[1]
            hand_inv = inventories[1] if len(inventories) > 1 else {}
            if hand_inv.get("FERTILIZER", 0) > 0:
                t = _nearest(hx, hy, fert_targets)
                fert_specialist_cmd = [FERTILIZE] if (hx, hy) == t else [step_toward(hx, hy, t[0], t[1])]
            elif private.get("shed", {}).get("FERTILIZER", 0) > 0:
                st = _shed_tile(farm)
                batch = min(private["shed"].get("FERTILIZER", 0), len(fert_targets), 3)
                fert_specialist_cmd = [PICKUP, "FERTILIZER", batch] if (hx, hy) == st else [step_toward(hx, hy, st[0], st[1])]
        fert_tasks = self._plan_fert_tasks(obs, farm, private, day, size)

        # Ordered task list: water(0) > harvest(1) > dig(2) > plant(3), with
        # livestock tasks (feed/harvest/build/place) at rank -1 (urgent) and
        # strawberry fertilizer just above watering.
        tasks = list(animal_tasks)
        if fert_specialist_cmd is None:
            tasks.extend(fert_tasks)
        # At-risk plants (1 day from weeding) out-rank normal watering.
        for xy in water_at_risk:
            tasks.append((-0.5, xy, [WATER], None, False))
        # Ongoing crops about to cap yield: reap now so the next production
        # isn't wasted. Beats normal watering, loses to at-risk watering.
        for xy in harvest_full:
            tasks.append((-0.25, xy, [HARVEST], None, False))
        for xy in water:
            tasks.append((0, xy, [WATER], None, False))
        for xy in harvest:
            tasks.append((1, xy, [HARVEST], None, False))
        for xy in weed:
            tasks.append((2, xy, [DIG], None, False))
        # Maintain the strawberry field: ongoing plants decay after max_yield
        # productions, so replant empty tiles to keep the count near target.
        # Rank 1.1 (after water/harvest, before dig/fert) so it beats generic
        # planting and actually happens while hands are nearby.
        st_priority = set()
        if self.livestock and day >= 4:
            st_count = self._count_strawberry_plants(farm)
            st_seeds = seeds.get("STRAWBERRY", 0)
            need = max(0, self.strawberry_target - st_count)
            for xy in plant:
                if need <= 0:
                    break
                if st_seeds <= 0:
                    break
                # Strawberry must still mature before season end.
                if day + CROPS["STRAWBERRY"]["max_yield_day"] > SEASON_DAYS - 1:
                    break
                tasks.append((1.1, xy, [PLANT, "STRAWBERRY"], None, False))
                st_priority.add(xy)
                st_seeds -= 1
                need -= 1
        for xy in plant:
            if xy in st_priority:
                continue
            crop = _plantable_crop()
            if crop:
                # Plant at rank 2.5 (after weeding) so freed tiles actually get
                # re-cropped instead of sitting idle while hands chase watering/
                # harvesting/animal chores all day.
                tasks.append((2.5, xy, [PLANT, crop], None, False))

        # Assign each unit the nearest unassigned task it is CAPABLE of (lower
        # key wins). The farmer (unit 0) is processed first and animal chores
        # have the highest priority, so it naturally leads the logistics chain.
        # `shareable` tasks (shed restocking) may be taken by several units at
        # once — they are never added to the assigned set. The first hand (i=1)
        # is the fertilizer specialist when a chain is active.
        #
        # ZONE-BASED PRIORITY (4 levels, lower key wins):
        #   0 = URGENT  (at-risk feed -2 / at-risk water -0.5)  -> ANY unit
        #   1 = CRITICAL (feed/collect/care/harvest/place/build, rank<0) -> any unit
        #   2 = own-zone normal crops (water/harvest/plant/dig, rank>=0)
        #   3 = out-of-zone normal crops
        # So survival tasks are always covered first by any unit, and the LAST
        # few hands ("field hands") stick to their quadrant's crops the rest of
        # the time. This keeps expanded-land strawberry watered without letting
        # animals starve (the failure mode of a pure static split).
        zoning = len(farm.get("unlocked_quadrants", [])) > 1
        n_field = max(0, min(4, len(positions) - 4)) if zoning else 0
        field_start = len(positions) - n_field
        inventories = private.get("inventories", [])
        assigned = set()
        cmds = []
        for i, pos in enumerate(positions):
            if i == 1 and fert_specialist_cmd is not None:
                cmds.append(fert_specialist_cmd)
                continue
            inv = inventories[i] if i < len(inventories) else {}
            is_field = i >= field_start
            # Field hands alternate quadrants (even->NE, odd->SW) so the outer
            # crops in both bought quadrants get covered.
            field_zone = "NE" if (i - field_start) % 2 == 0 else "SW"
            best = None
            for rank, xy, action, cap, shareable in tasks:
                if (not shareable) and xy in assigned:
                    continue
                if not self._unit_capable(cap, inv):
                    continue
                if rank <= -2 or rank == -0.5:
                    prio = 0  # urgent: at-risk animal/plant survival
                elif rank < 0:
                    prio = 1  # critical animal chore
                elif is_field and self._zone_of(*xy) == field_zone:
                    prio = 2  # own quadrant crop
                elif is_field:
                    prio = 3  # other quadrant crop (or core)
                else:
                    prio = 2  # core hand: in-zone = any normal crop
                d = _manhattan(pos, xy)
                key = (prio, rank, d)
                if best is None or key < best[0]:
                    best = (key, xy, action, shareable)
            if best is None:
                cmds.append([PASS])
                continue
            (_, _, _), xy, action, shareable = best
            if not shareable:
                assigned.add(xy)
            if pos == xy:
                cmds.append(action)
            else:
                cmds.append([step_toward(pos[0], pos[1], xy[0], xy[1])])
        return cmds

    # ---- 3. strawberry fertilizer -------------------------------------------- #
    def _find_fert_targets(self, obs, farm, day, size) -> list[tuple[int, int]]:
        """All unfertilized strawberries at a production day."""
        cd = CROPS["STRAWBERRY"]
        tiles = farm.get("tiles", [])
        out = []
        for y in range(size):
            for x in range(size):
                t = tiles[y][x]
                if not (isinstance(t, dict) and t.get("kind") == KIND_PLANT and t.get("crop") == "STRAWBERRY"):
                    continue
                age = day - int(t.get("planted_day", day))
                days_since_first = age - cd["first_yield_day"]
                if days_since_first < 0 or days_since_first % cd["interval"] != 0:
                    continue
                if t.get("fertilized_until_day", -1) >= day:
                    continue
                out.append((x, y))
        return out

    def _plan_fert_tasks(self, obs, farm, private, day, size) -> list:
        """High-priority tasks for applying free animal fertilizer to strawberry.

        Fertilizer on a production-day strawberry doubles that production (~$110
        value) which beats selling it (~$95). These tasks must out-rank watering
        and harvest — otherwise the hand carrying fertilizer gets pulled away to
        farm chores and never fertilizes. Emits a shareable PICKUP FERTILIZER
        (at the shed) so several hands can restock, and a FERTILIZE per target
        that only a fertilizer-carrying unit may take.
        """
        if not self.fert_strawberry:
            return []
        shed_fert = private.get("shed", {}).get("FERTILIZER", 0)
        targets = self._find_fert_targets(obs, farm, day, size)
        if not targets:
            return []
        n_carry = sum(1 for inv in private.get("inventories", []) if inv.get("FERTILIZER", 0) > 0)
        tasks = []
        if n_carry > 0:
            for xy in targets:
                tasks.append((-0.4, xy, [FERTILIZE], "FERT", False))
        elif shed_fert > 0:
            # Restock: shareable shed tile, one task per free unit up to need.
            n_free = sum(
                1 for inv in private.get("inventories", [])
                if inv.get("FERTILIZER", 0) <= 0 and not any(a in inv for a in ANIMALS)
            )
            for _ in range(min(n_free, len(targets), 3)):
                tasks.append((-0.5, _shed_tile(farm), [PICKUP, "FERTILIZER", 1], "!FERT", True))
        return tasks

    # ---- 4. livestock -------------------------------------------------------- #
    def _animal_placed(self, farm) -> bool:
        if self.animal is None:
            return False
        tiles = farm.get("tiles", [])
        for y in range(len(tiles)):
            for x in range(len(tiles[y])):
                t = tiles[y][x]
                if isinstance(t, dict) and t.get("animal") == self.animal:
                    return True
        return False

    def _find_empty_structure(self, farm, structure_kind) -> tuple[int, int] | None:
        """Empty structure of `structure_kind`, nearest the shed center."""
        tiles = farm.get("tiles", [])
        best = None
        best_d = 10 ** 9
        for y in range(len(tiles)):
            for x in range(len(tiles[y])):
                t = tiles[y][x]
                if isinstance(t, dict) and t.get("kind") == structure_kind and "animal" not in t:
                    d = abs(x - 4) + abs(y - 4)
                    if d < best_d:
                        best_d = d
                        best = (x, y)
        return best

    def _find_animal_tile(self, farm) -> tuple[int, int] | None:
        if self.animal is None:
            return None
        tiles = farm.get("tiles", [])
        for y in range(len(tiles)):
            for x in range(len(tiles[y])):
                t = tiles[y][x]
                if isinstance(t, dict) and t.get("animal") == self.animal:
                    return (x, y)
        return None

    # ---- 4b. multi-animal livestock economy ---------------------------------- #
    def _all_animals(self, farm):
        """Yield (x, y, tile) for every tile holding a placed animal."""
        tiles = farm.get("tiles", [])
        for y in range(len(tiles)):
            for x in range(len(tiles[y])):
                t = tiles[y][x]
                if isinstance(t, dict) and t.get("animal"):
                    yield x, y, t

    def _placed_count(self, farm, animal: str) -> int:
        return sum(1 for _, _, t in self._all_animals(farm) if t.get("animal") == animal)

    def _total_animals(self, farm) -> int:
        return sum(1 for _ in self._all_animals(farm))

    def _any_carry(self, private, item: str) -> bool:
        return any(inv.get(item, 0) > 0 for inv in private.get("inventories", []))

    def _room_for_structure(self, farm, size, structure_kind) -> bool:
        """True if an empty tile exists to build a structure on."""
        if self._find_empty_structure(farm, structure_kind) is not None:
            return True
        tiles = farm.get("tiles", [])
        return any(t is None for row in tiles for t in row)

    def _first_empty_tile(self, farm) -> tuple[int, int] | None:
        """Empty unlocked tile nearest the shed center, NEVER on a shed access
        tile (those must stay free so units can reach the shed)."""
        tiles = farm.get("tiles", [])
        best = None
        best_d = 10 ** 9
        for y in range(len(tiles)):
            for x in range(len(tiles[y])):
                if (x, y) in SHED_TILES:
                    continue
                if tiles[y][x] is None:
                    d = abs(x - 4) + abs(y - 4)
                    if d < best_d:
                        best_d = d
                        best = (x, y)
        return best

    @staticmethod
    def _zone_of(x: int, y: int) -> str:
        """Spatial zone of a tile: core (near the shed), NE, SW, else far."""
        if abs(x - 4) + abs(y - 4) <= 3:
            return "core"
        if x >= 5 and y < 5:
            return "NE"
        if x < 5 and y >= 5:
            return "SW"
        return "far"

    # ---- capability tags for multi-step choreography ------------------------ #
    # Each animal chore task carries a `cap` tag. The assignment loop only lets
    # a unit take a task it is capable of, so the PICKUP->FEED and PICKUP->PLACE
    # chains stay on the SAME unit across turns (a unit that carries wheat is the
    # only one that may feed; a unit that carries a cow is the only one that may
    # place it). Without this, the nearest-task coordinator hands the second half
    # of a chain to a different unit and the animal gets stuck in a deadlock.
    @staticmethod
    def _unit_capable(cap, inv) -> bool:
        if cap is None:
            return True
        if cap == "WHEAT":          # must be carrying wheat (can feed)
            return inv.get("WHEAT", 0) > 0
        if cap == "!WHEAT":         # must NOT be carrying wheat or any animal
            return inv.get("WHEAT", 0) <= 0 and not any(a in inv for a in ANIMALS)
        if cap == "!ANIMAL":        # must not be carrying any animal
            return not any(a in inv for a in ANIMALS)
        if cap == "FERT":           # must be carrying fertilizer (can fertilize)
            return inv.get("FERTILIZER", 0) > 0
        if cap == "!FERT":          # must not be carrying fertilizer
            return inv.get("FERTILIZER", 0) <= 0
        return inv.get(cap, 0) > 0  # must be carrying this specific animal

    def _plan_animal_tasks(self, obs, farm, private, day, size):
        """Livestock chores, ranked just above watering so animals never escape.

        Every task is (rank, xy, action, cap): the assigned unit must satisfy
        `cap` (see `_unit_capable`). This keeps feed/placement chains on the
        same carrier across turns instead of deadlocking animals in the shed.
        """
        if not self.livestock:
            return []
        shed = private.get("shed", {})
        tasks: list = []
        tiles = farm.get("tiles", [])

        # ---- (A) chores for already-placed animals --------------------------
        unfed = []  # (x, y, at_risk) — at_risk = unfed for 1 day, escapes at 2
        for x, y, t in self._all_animals(farm):
            animal = t["animal"]
            if not t.get("fed_today", False):
                unfed.append((x, y, int(t.get("consecutive_unfed", 0)) >= 1))
            if t.get("fertilizer_available", False):
                tasks.append((-1, (x, y), [COLLECT_FERTILIZER], None, False))
            if t.get("yield_units", 0) > 0:
                tasks.append((-1, (x, y), [HARVEST], None, False))
            if not t.get("cared_today", False):
                tasks.append((-1, (x, y), [CARE], None, False))

        # Feed: units already carrying wheat may FEED; units NOT carrying
        # wheat/animals restock from the shed. Both are emitted simultaneously
        # so feeding never stalls while a single carrier walks a long way.
        # Restock tasks are marked `shareable=True` so several units may target
        # the same shed tile in the same turn (each picking up a small batch).
        # Animals one day from escaping (consecutive_unfed >= 1) get rank -2 so
        # they're fed before anything else.
        if unfed:
            inventories = private.get("inventories", [])
            n_unfed = len(unfed)
            n_urgent = sum(1 for _, _, at_risk in unfed if at_risk)
            n_carry_wheat = sum(1 for inv in inventories if inv.get("WHEAT", 0) > 0)
            n_free = sum(
                1 for inv in inventories
                if inv.get("WHEAT", 0) <= 0 and not any(a in inv for a in ANIMALS)
            )
            for ux, uy, at_risk in unfed:
                tasks.append((-2 if at_risk else -1, (ux, uy), [FEED], "WHEAT", False))
            if shed.get("WHEAT", 0) > 0:
                need = max(0, n_unfed - n_carry_wheat)
                for _ in range(min(n_free, need, 3)):
                    batch = min(shed.get("WHEAT", 0), max(1, n_unfed), 2)
                    rank = -2 if n_urgent > 0 else -1
                    tasks.append((rank, _shed_tile(farm), [PICKUP, "WHEAT", batch], "!WHEAT", True))

        # ---- (B) place/build unplaced animals --------------------------------
        for animal, target in self.animal_plan:
            a = ANIMALS[animal]
            placed = self._placed_count(farm, animal)
            if placed >= target:
                continue
            in_shed = shed.get(animal, 0)
            in_inv = sum(inv.get(animal, 0) for inv in private.get("inventories", []))
            structure_kind = a["structure"]
            empty_struct = self._find_empty_structure(farm, structure_kind)
            build = BUILD_COOP if structure_kind == KIND_COOP else BUILD_PASTURE
            if empty_struct is not None:
                if in_inv > 0:
                    tasks.append((-1, empty_struct, [PLACE, animal, 1], animal, False))
                elif in_shed > 0:
                    tasks.append((-1, _shed_tile(farm), [PICKUP, animal, 1], "!ANIMAL", False))
            elif in_shed + in_inv > 0:
                # A structure is needed and an animal is ready: build it now so
                # the pickup/place chain doesn't stall on missing structures.
                tile = self._first_empty_tile(farm)
                if tile is not None:
                    tasks.append((-1, tile, [build], None, False))

        return tasks

    # ---- 4. premium production cap ------------------------------------------- #
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

    def _count_melon_plants(self, farm) -> int:
        tiles = farm.get("tiles", [])
        return sum(
            1
            for y in range(len(tiles))
            for x in range(len(tiles[y]))
            if isinstance(tiles[y][x], dict)
            and tiles[y][x].get("kind") == KIND_PLANT
            and tiles[y][x].get("crop") == "MELON"
        )

    def _count_strawberry_plants(self, farm) -> int:
        tiles = farm.get("tiles", [])
        return sum(
            1
            for y in range(len(tiles))
            for x in range(len(tiles[y]))
            if isinstance(tiles[y][x], dict)
            and tiles[y][x].get("kind") == KIND_PLANT
            and tiles[y][x].get("crop") == "STRAWBERRY"
        )

    def _count_wheat_plants(self, farm) -> int:
        tiles = farm.get("tiles", [])
        return sum(
            1
            for y in range(len(tiles))
            for x in range(len(tiles[y]))
            if isinstance(tiles[y][x], dict)
            and tiles[y][x].get("kind") == KIND_PLANT
            and tiles[y][x].get("crop") == "WHEAT"
        )

    def _strawberry_fert_reserve(self, farm) -> int:
        """How many fertilizer units to keep in the shed for strawberry
        fertilization: one per active strawberry plant (applied on its next
        production day, fertilized_until covers 2-3 production cycles)."""
        if not self.fert_strawberry:
            return 0
        return self._count_strawberry_plants(farm)

    # ---- 5. price-aware crop selection -------------------------------------- #
    def _preferred_crops(self, obs, farm, day) -> list[str]:
        prices = obs.get("market", {}).get("prices", {})
        melon_price = prices.get("MELON", CROPS["MELON"].get("base", 250))
        # Melon focus: while the gate is open and melon can still mature, put ALL
        # seed money and planting into melon (best per-tile crop by far).
        if self.melon_focus and self.melon_plant_gate is not None and melon_price >= self.melon_plant_gate:
            if day + CROPS["MELON"]["max_yield_day"] <= SEASON_DAYS - 1:
                return ["MELON"]
        scored = []
        for crop in self.crops:
            cd = CROPS[crop]
            # Must mature before season end (planting day counts toward growth).
            if day + cd["max_yield_day"] > SEASON_DAYS - 1:
                continue
            # Livestock mode: strawberry seeds/plants start on day 4 to save early
            # cash for animals (matches the top agent's schedule).
            if self.livestock and crop == "STRAWBERRY" and day < 4:
                continue
            # Melon gate: once the melon market is saturated (price below gate),
            # stop planting melons — the glut crashes the price to $1 anyway.
            price = prices.get(crop, cd.get("base", 0))
            if crop == "MELON":
                if self.melon_plant_gate is not None and price < self.melon_plant_gate:
                    continue
                if self.max_melon_plants is not None and self._count_melon_plants(farm) >= self.max_melon_plants:
                    continue
            yield_est = _unfertilized_yield(crop)
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
