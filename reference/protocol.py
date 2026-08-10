"""The REAL Kaggriculture env contract — constants, accessors, action builders.

Decoded from the competition's community `agent(obs)`. Keeping this in one place
means the rest of the real-protocol code never hard-codes magic strings, and if
the real env renames anything we fix it here once.

Observation shape (dict):
    obs["player"]            -> my player index
    obs["day"]               -> current in-game day
    obs["farms"][player]     -> {"farmer": (x, y), "money": float,
                                 "tiles": tiles[y][x]}
        tile is None, or {"kind": "PLANT", "planted_day": int,
                          "watered_today": bool}, or {"kind": "WEED"}
    obs["private"]           -> {"seeds": {CROP: n}, "shed": {CROP: n}}

Action shape (returned dict):
    {"farmer": [CMD, ...], "hands": [], "market": [[OP, CROP, QTY], ...]}
      farmer CMD is exactly one of: a MOVE, a tile ACTION, or ["PLANT", CROP].
"""

from __future__ import annotations

# --- farmer movement -------------------------------------------------------- #
# Coordinate convention (from the reference agent): x = column, y = row.
#   fx < tx -> EAST   (east increases x)
#   fy < ty -> SOUTH  (south increases y)
NORTH = "NORTH"
SOUTH = "SOUTH"
EAST = "EAST"
WEST = "WEST"
MOVES = (NORTH, SOUTH, EAST, WEST)

# --- tile actions (act on the tile the farmer stands on) -------------------- #
WATER = "WATER"
HARVEST = "HARVEST"
DIG = "DIG"       # remove a weed
PLANT = "PLANT"   # ["PLANT", CROP]
PASS = "PASS"

# --- tile kinds ------------------------------------------------------------- #
KIND_PLANT = "PLANT"
KIND_WEED = "WEED"

# --- market operations ------------------------------------------------------ #
BUY_SEED = "BUY_SEED"
SELL = "SELL"


def build_action(farmer_cmd: list, market: list | None = None) -> dict:
    """Assemble a well-formed action dict for one turn."""
    return {"farmer": list(farmer_cmd), "hands": [], "market": market or []}


def pass_action(market: list | None = None) -> dict:
    """Do nothing with the farmer this turn (still allows market ops)."""
    return build_action([PASS], market)


def step_toward(fx: int, fy: int, tx: int, ty: int) -> str:
    """One move that brings the farmer closer to (tx, ty).

    Matches the reference agent: resolve the x-axis first, then the y-axis.
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
    return PASS  # already there


def my_farm(obs: dict) -> dict:
    """The observing player's own farm block."""
    return obs["farms"][obs["player"]]


def farmer_xy(obs: dict) -> tuple[int, int]:
    fx, fy = my_farm(obs)["farmer"]
    return int(fx), int(fy)
