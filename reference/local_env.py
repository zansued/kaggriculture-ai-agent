"""A LOCAL simulator that reproduces the real Kaggriculture contract.

Purpose: develop and test a real-protocol agent WITHOUT the Kaggle package. The
observation/action shapes here match `protocol.py` exactly, so an agent written
against this env plugs into the real env unchanged.

======================================================================= #
IMPORTANT — ASSUMPTIONS (reconcile with the real env when its spec arrives)
======================================================================= #
The pasted reference `agent(obs)` revealed the CONTRACT (shapes) but NOT the
numeric mechanics. Everything the real spec has not yet confirmed lives in the
`Mechanics` dataclass below and is marked [ASSUMPTION]. Swapping in real numbers
is a one-place edit; the contract-facing code does not change.

Confirmed from the reference agent:
  * grid is addressed tiles[y][x]; the reference farms the 5x5 NW quadrant
  * crop_age = obs["day"] - tile["planted_day"]; harvest at age >= 2
  * seeds must be bought before planting; harvested crop sits in the shed
  * one farmer command per turn (move OR act on current tile)
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from . import protocol as P


@dataclass
class CropSpec:
    seed_cost: float
    sell_price: float   # [ASSUMPTION] price per unit sold from the shed
    base_yield: float   # [ASSUMPTION] units produced by a healthy harvest


@dataclass
class Mechanics:
    """All tunable numbers. [ASSUMPTION] values pending the real spec."""

    farm_size: int = 5                 # confirmed: reference uses a 5x5 quadrant
    turns_per_day: int = 24            # from "30 days = 720 turns"
    max_days: int = 30                 # confirmed: 30 in-game days
    mature_days: int = 2               # confirmed: harvest at age >= 2
    weed_prob_per_day: float = 0.30    # [ASSUMPTION] chance a weed spawns per farm/day
    # [ASSUMPTION] watering matters: a crop watered every day yields full; an
    # un-watered crop yields half. Real weighting unknown.
    dry_yield_factor: float = 0.5
    crops: dict[str, CropSpec] = field(
        default_factory=lambda: {
            "WHEAT": CropSpec(seed_cost=10.0, sell_price=15.0, base_yield=3.0),
            "CORN": CropSpec(seed_cost=15.0, sell_price=26.0, base_yield=3.0),
        }
    )
    start_money: float = 100.0         # [ASSUMPTION]
    start_seeds: dict[str, int] = field(default_factory=lambda: {"WHEAT": 4})


class LocalKaggricultureEnv:
    """Deterministic-by-seed local Kaggriculture. Supports N players (default 2).

    Typical use:
        env = LocalKaggricultureEnv(seed=0)
        env.reset()
        while not env.done:
            actions = [agent(env.observe(p)) for p in range(env.n_players)]
            env.step(actions)
        score = env.score(0)
    """

    def __init__(
        self,
        seed: int = 0,
        n_players: int = 2,
        mech: Mechanics | None = None,
    ) -> None:
        self.mech = mech or Mechanics()
        self.n_players = n_players
        self._rng = random.Random(seed)
        self.max_turns = self.mech.turns_per_day * self.mech.max_days
        self.reset()

    # ---- lifecycle --------------------------------------------------------- #
    def reset(self) -> None:
        n = self.mech.farm_size
        self.turn = 0
        self.day = 1
        self.farms: list[dict] = []
        for _ in range(self.n_players):
            self.farms.append(
                {
                    "farmer": [0, 0],
                    "money": self.mech.start_money,
                    # tiles[y][x]; None = empty. Internal tiles carry a private
                    # "_waterings" counter that observe() never exposes.
                    "tiles": [[None for _ in range(n)] for _ in range(n)],
                    "seeds": dict(self.mech.start_seeds),
                    "shed": {},
                }
            )

    @property
    def done(self) -> bool:
        return self.turn >= self.max_turns or self.day > self.mech.max_days

    # ---- observation (mirrors the real obs shape exactly) ------------------ #
    def observe(self, player: int) -> dict:
        return {
            "player": player,
            "day": self.day,
            "farms": [self._public_farm(f) for f in self.farms],
            # private info is only ever the observing player's own
            "private": {
                "seeds": dict(self.farms[player]["seeds"]),
                "shed": dict(self.farms[player]["shed"]),
            },
        }

    def _public_farm(self, farm: dict) -> dict:
        return {
            "farmer": list(farm["farmer"]),
            "money": farm["money"],
            "tiles": [[self._public_tile(t) for t in row] for row in farm["tiles"]],
        }

    @staticmethod
    def _public_tile(tile: dict | None) -> dict | None:
        if tile is None:
            return None
        if tile["kind"] == P.KIND_PLANT:
            return {
                "kind": P.KIND_PLANT,
                "planted_day": tile["planted_day"],
                "watered_today": tile["watered_today"],
            }
        return {"kind": tile["kind"]}  # WEED

    # ---- stepping ---------------------------------------------------------- #
    def step(self, actions: list[dict]) -> None:
        if self.done:
            return
        for player, action in enumerate(actions):
            if action is None:
                continue
            self._apply_market(player, action.get("market") or [])
            self._apply_farmer(player, action.get("farmer") or [P.PASS])

        self.turn += 1
        if self.turn % self.mech.turns_per_day == 0:
            self._end_of_day()

    def _apply_market(self, player: int, ops: list) -> None:
        farm = self.farms[player]
        for op in ops:
            if not op:
                continue
            kind = op[0]
            if kind == P.BUY_SEED and len(op) >= 3:
                crop, qty = op[1], int(op[2])
                spec = self.mech.crops.get(crop)
                if spec is None or qty <= 0:
                    continue
                cost = qty * spec.seed_cost
                if farm["money"] >= cost:
                    farm["money"] -= cost
                    farm["seeds"][crop] = farm["seeds"].get(crop, 0) + qty
            elif kind == P.SELL and len(op) >= 3:
                crop, qty = op[1], int(op[2])
                spec = self.mech.crops.get(crop)
                have = farm["shed"].get(crop, 0)
                q = min(int(qty), have)
                if spec is None or q <= 0:
                    continue
                farm["shed"][crop] = have - q
                farm["money"] += q * spec.sell_price

    def _apply_farmer(self, player: int, cmd: list) -> None:
        if not cmd:
            return
        farm = self.farms[player]
        fx, fy = farm["farmer"]
        verb = cmd[0]
        n = self.mech.farm_size

        if verb in P.MOVES:
            if verb == P.EAST:
                fx = min(n - 1, fx + 1)
            elif verb == P.WEST:
                fx = max(0, fx - 1)
            elif verb == P.SOUTH:
                fy = min(n - 1, fy + 1)
            elif verb == P.NORTH:
                fy = max(0, fy - 1)
            farm["farmer"] = [fx, fy]
            return

        tile = farm["tiles"][fy][fx]

        if verb == P.WATER:
            if tile and tile["kind"] == P.KIND_PLANT and not tile["watered_today"]:
                tile["watered_today"] = True
                tile["_waterings"] += 1
        elif verb == P.HARVEST:
            if (
                tile
                and tile["kind"] == P.KIND_PLANT
                and self.day - tile["planted_day"] >= self.mech.mature_days
            ):
                crop = tile["crop"]
                spec = self.mech.crops[crop]
                # [ASSUMPTION] yield scales with how well it was watered.
                need = max(1, self.mech.mature_days)
                water_ratio = min(1.0, tile["_waterings"] / need)
                factor = self.mech.dry_yield_factor + (
                    1.0 - self.mech.dry_yield_factor
                ) * water_ratio
                amount = spec.base_yield * factor
                farm["shed"][crop] = farm["shed"].get(crop, 0) + amount
                farm["tiles"][fy][fx] = None
        elif verb == P.DIG:
            if tile and tile["kind"] == P.KIND_WEED:
                farm["tiles"][fy][fx] = None
        elif verb == P.PLANT and len(cmd) >= 2:
            crop = cmd[1]
            if tile is None and farm["seeds"].get(crop, 0) > 0:
                farm["seeds"][crop] -= 1
                farm["tiles"][fy][fx] = {
                    "kind": P.KIND_PLANT,
                    "crop": crop,
                    "planted_day": self.day,
                    "watered_today": False,
                    "_waterings": 0,
                }
        # PASS / unknown verbs: no-op

    def _end_of_day(self) -> None:
        self.day += 1
        n = self.mech.farm_size
        for farm in self.farms:
            for row in farm["tiles"]:
                for tile in row:
                    if tile and tile["kind"] == P.KIND_PLANT:
                        tile["watered_today"] = False
            # [ASSUMPTION] weeds sprout on a random empty tile each day.
            if self._rng.random() < self.mech.weed_prob_per_day:
                empties = [
                    (x, y)
                    for y in range(n)
                    for x in range(n)
                    if farm["tiles"][y][x] is None
                ]
                if empties:
                    x, y = self._rng.choice(empties)
                    farm["tiles"][y][x] = {"kind": P.KIND_WEED}

    # ---- scoring ----------------------------------------------------------- #
    def score(self, player: int) -> float:
        """[ASSUMPTION] final score = money + unsold shed value at market price."""
        farm = self.farms[player]
        shed_value = sum(
            amt * self.mech.crops[c].sell_price
            for c, amt in farm["shed"].items()
            if c in self.mech.crops
        )
        return round(farm["money"] + shed_value, 2)
