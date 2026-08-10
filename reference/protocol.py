"""The REAL Kaggriculture env contract — constants, accessors, action builders.

Sourced from the actual engine source shipped with `kaggle_environments`
(`envs/kaggriculture/kaggriculture.py`) — the authoritative reference, not an
assumption. Keeping this in one place means the agent code never hard-codes
magic strings, and if the env renames anything we fix it here once.

Observation shape (dict):
    obs["player"]            -> my player index (0 or 1)
    obs["day"]               -> current in-game day (0-indexed)
    obs["hour"]              -> turn within the day (0-indexed, 0..23)
    obs["farms"][player]     -> {"money": float, "tiles": tiles[y][x],
                                 "farmer": [x, y], "hands": [[x,y], ...],
                                 "unlocked_quadrants": [...], "hires_today": int}
        tile is None (empty unlocked), "LOCKED" (unbought quadrant), or a dict:
          plant  {"kind":"PLANT","crop","planted_day","watered_today",
                  "consecutive_unwatered","yield_units","max_lifespan_step",
                  "fertilized_until_day"}
          weed   {"kind":"WEED"}
          animal {"kind":"COOP"|"PASTURE","animal"|None,"placed_day",
                  "yield_units","fed_today","consecutive_unfed","cared_today",
                  "fertilizer_available","pending_care_bonus"}
    obs["market"]            -> shared: {"inventory": {item:int},
                                         "prices": {item:int}}
    obs["town"]              -> shared: {"unlocked_shops": [str, ...]}
    obs["private"]           -> my only: {"shed": {item:int}, "seeds": {crop:int},
                                         "inventories": [farmer_inv, hand_inv, ...]}

Action shape (returned dict):
    {"farmer": [op, ...args], "hands": [[op, ...], ...],
     "market": [[op, item, n], ...]}     # market capped at 10 orders/turn
"""

from __future__ import annotations

# --- crops (from engine CROPS) --------------------------------------------- #
# seed cost, first_yield_day, max_yield_day, interval (0 = one-time),
# max_yield, ongoing
CROPS = {
    "WHEAT":      {"seed": 10, "first_yield_day": 2, "max_yield_day": 4, "interval": 0, "max_yield": 6, "ongoing": False},
    "CARROT":     {"seed": 20, "first_yield_day": 2, "max_yield_day": 3, "interval": 0, "max_yield": 4, "ongoing": False},
    "TOMATO":     {"seed": 50, "first_yield_day": 8, "max_yield_day": 8, "interval": 1, "max_yield": 4, "ongoing": True},
    "STRAWBERRY": {"seed": 100, "first_yield_day": 10, "max_yield_day": 10, "interval": 2, "max_yield": 4, "ongoing": True},
    "MELON":      {"seed": 80, "first_yield_day": 10, "max_yield_day": 12, "interval": 0, "max_yield": 6, "ongoing": False},
}

# --- animals (from engine ANIMALS) ----------------------------------------- #
ANIMALS = {
    "GOOSE": {"cost": 300, "structure": "COOP",    "first_yield_day": 4, "interval": 1, "max_held": 4, "product": "EGG"},
    "COW":   {"cost": 400, "structure": "PASTURE", "first_yield_day": 8, "interval": 2, "max_held": 6, "product": "MILK"},
    "SHEEP": {"cost": 500, "structure": "PASTURE", "first_yield_day": 6, "interval": 3, "max_held": 6, "product": "WOOL"},
}

PRODUCTS = ["WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON", "EGG", "MILK", "WOOL", "FERTILIZER"]

# --- market params (from engine MARKET_PARAMS) ----------------------------- #
MARKET_I0 = 10000
PRICE_FLOOR = 1
MARKET_PARAMS = {
    "WHEAT":      {"base":  25, "I0": MARKET_I0, "T": 400, "below_func": "sqrt",   "below_target": 0.80, "above_func": "log",    "above_target": 0.20},
    "CARROT":     {"base":  35, "I0": MARKET_I0, "T": 450, "below_func": "log",    "below_target": 0.20, "above_func": "sqrt",   "above_target": 0.70},
    "TOMATO":     {"base":  60, "I0": MARKET_I0, "T": 200, "below_func": "linear", "below_target": 0.40, "above_func": "sqrt",   "above_target": 0.60},
    "STRAWBERRY": {"base": 120, "I0": MARKET_I0, "T": 100, "below_func": "sqrt",   "below_target": 0.70, "above_func": "linear", "above_target": 1.60},
    "MELON":      {"base": 250, "I0": MARKET_I0, "T": 300, "below_func": "log",    "below_target": 0.20, "above_func": "sq",     "above_target": 3.60},
    "EGG":        {"base":  50, "I0": MARKET_I0, "T": 332, "below_func": "linear", "below_target": 0.40, "above_func": "log",    "above_target": 0.20},
    "MILK":       {"base": 160, "I0": MARKET_I0, "T": 122, "below_func": "sqrt",   "below_target": 0.60, "above_func": "linear", "above_target": 1.60},
    "WOOL":       {"base": 200, "I0": MARKET_I0, "T": 105, "below_func": "log",    "below_target": 0.20, "above_func": "sq",     "above_target": 3.20},
    "FERTILIZER": {"base": 100, "I0": MARKET_I0, "T": 200, "below_func": "linear", "below_target": 0.40, "above_func": "linear", "above_target": 0.40},
}

# --- land / hands ----------------------------------------------------------- #
LAND_ORDER = ["NE", "SW", "SE"]
LAND_PRICES = [1000, 2000, 4000]

# --- movement --------------------------------------------------------------- #
NORTH = "NORTH"
SOUTH = "SOUTH"
EAST = "EAST"
WEST = "WEST"
MOVES = (NORTH, SOUTH, EAST, WEST)

# --- tile actions ------------------------------------------------------------ #
PASS = "PASS"
WATER = "WATER"
HARVEST = "HARVEST"
DIG = "DIG"
PLANT = "PLANT"
FERTILIZE = "FERTILIZE"
BUILD_COOP = "BUILD_COOP"
BUILD_PASTURE = "BUILD_PASTURE"
FEED = "FEED"
CARE = "CARE"
COLLECT_FERTILIZER = "COLLECT_FERTILIZER"
PICKUP = "PICKUP"
DROP = "DROP"
PLACE = "PLACE"

# --- tile kinds -------------------------------------------------------------- #
KIND_PLANT = "PLANT"
KIND_WEED = "WEED"
KIND_COOP = "COOP"
KIND_PASTURE = "PASTURE"

# --- market operations -------------------------------------------------------- #
BUY_SEED = "BUY_SEED"
BUY_ANIMAL = "BUY_ANIMAL"
BUY_PRODUCT = "BUY_PRODUCT"
SELL = "SELL"
HIRE = "HIRE"
BUY_LAND = "BUY_LAND"

# --- defaults ---------------------------------------------------------------- #
STARTING_MONEY = 3000
SHED_CAPACITY = 100
MAX_MARKET_ORDERS = 10
TURNS_PER_DAY = 24
SEASON_DAYS = 30
BOARD_SIZE = 10
WEED_SPAWN_CHANCE = 0.005


def build_action(farmer_cmd: list, hands_cmds: list | None = None, market: list | None = None) -> dict:
    """Assemble a well-formed action dict for one turn."""
    return {
        "farmer": list(farmer_cmd),
        "hands": [list(c) for c in (hands_cmds or [])],
        "market": [list(o) for o in (market or [])],
    }


def pass_action(market: list | None = None) -> dict:
    """Do nothing with every unit (still allows market ops)."""
    return build_action([PASS], [], market)


def step_toward(fx: int, fy: int, tx: int, ty: int) -> str:
    """One move that brings the farmer closer to (tx, ty).

    Matches the engine: resolve the x-axis first, then the y-axis.
    Returns a MOVE constant; caller should only use it when (fx, fy) != (tx, ty).
    """
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
    """The observing player's own farm block."""
    return obs["farms"][obs["player"]]


def farmer_xy(obs: dict) -> tuple[int, int]:
    fx, fy = my_farm(obs)["farmer"]
    return int(fx), int(fy)


def market_prices(obs: dict) -> dict:
    """Current market sell prices (shared)."""
    return obs.get("market", {}).get("prices", {})


def market_inventory(obs: dict) -> dict:
    """Current market supply (shared)."""
    return obs.get("market", {}).get("inventory", {})


def shed(obs: dict) -> dict:
    """My shed inventory (produce/animals/fertilizer)."""
    return obs.get("private", {}).get("shed", {})


def seeds(obs: dict) -> dict:
    """My seed inventory (separate slot, never through the shed)."""
    return obs.get("private", {}).get("seeds", {})


def is_shed_adjacent(x: int, y: int, board_size: int = BOARD_SIZE) -> bool:
    """The four center tiles around the shed are shed-adjacent."""
    half = board_size // 2
    return (x, y) in {(half - 1, half - 1), (half, half - 1), (half - 1, half), (half, half)}
