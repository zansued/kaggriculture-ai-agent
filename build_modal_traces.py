"""Build the shared-opening modal trace set for our own adaptive agent.

The Moon's "sacada #1" is a shop-routed modal base: pick the cow/sheep mix
based on the town's shops (yarn -> more sheep, milk shops -> more cows). Our
traces (purearch 8c6s, trace_10c4s) already share days 0-7 (verified: they
differ in only 2 market steps + 3 unit steps around day 8). So we can build a
modal selector that switches routes at the day-8 divergence.

This script produces the three shared-opening variants:
  purearch (8c6s)   — default
  trace_10c4s (10c4s) — milk-heavy (day-8 sheep -> cow)  [already exists]
  trace_6c8s (6c8s)  — yarn-heavy (post-day-8 cow -> sheep)  [built here]

The 6c8s variant converts the two day-10 COW chains (buy at steps 257, 258 +
their PICKUP/PLACE) into SHEEP, sharing days 0-8 with purearch.

Output: data/kawasagi/trace_6c8s.json
Usage:   python build_modal_traces.py
"""
from __future__ import annotations

import copy
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, "reference", "opponents"))
import purearch_opponent as pa  # noqa: E402

OUT = os.path.join(_HERE, "data", "kawasagi", "trace_6c8s.json")


def _find_chain(units, buy_step, animal):
    """Find the PICKUP/PLACE steps for the animal bought at buy_step."""
    # scan forward from buy_step for PICKUP <animal> then PLACE <animal>
    pickup = place = None
    for i in range(buy_step, min(buy_step + 40, len(units))):
        u = units[i]
        acts = [u.get("farmer")] + u.get("hands", [])
        for a in acts:
            if not (isinstance(a, list) and len(a) >= 2):
                continue
            if a[0] == "PICKUP" and a[1] == animal and pickup is None:
                pickup = i
            elif a[0] == "PLACE" and a[1] == animal and place is None and pickup is not None:
                place = i
                return pickup, place
    return pickup, place


def build():
    units = copy.deepcopy(pa._UNIT_TRACE)
    markets = copy.deepcopy(pa._MARKET_TRACE)
    converted = 0
    for buy_step in (257, 258):
        # convert the buy order
        for o in markets[buy_step]:
            if len(o) >= 2 and o[0] == "BUY_ANIMAL" and o[1] == "COW":
                o[1] = "SHEEP"
                break
        pickup, place = _find_chain(units, buy_step, "COW")
        if pickup is not None:
            u = units[pickup]
            acts = [u.get("farmer")] + u.get("hands", [])
            for a in acts:
                if isinstance(a, list) and len(a) >= 2 and a[0] == "PICKUP" and a[1] == "COW":
                    a[1] = "SHEEP"
                    break
        if place is not None:
            u = units[place]
            acts = [u.get("farmer")] + u.get("hands", [])
            for a in acts:
                if isinstance(a, list) and len(a) >= 2 and a[0] == "PLACE" and a[1] == "COW":
                    a[1] = "SHEEP"
                    break
        converted += 1
    trace = {"units": units, "markets": markets}
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(trace, open(OUT, "w"))
    print(f"wrote {OUT}: converted {converted} cow chains -> sheep")
    # verify: count animals
    cow_buys = sum(1 for m in markets for o in m if len(o) >= 2 and o[0] == "BUY_ANIMAL" and o[1] == "COW")
    sheep_buys = sum(1 for m in markets for o in m if len(o) >= 2 and o[0] == "BUY_ANIMAL" and o[1] == "SHEEP")
    print(f"BUY_ANIMAL totals: COW={cow_buys} SHEEP={sheep_buys}")


if __name__ == "__main__":
    build()
