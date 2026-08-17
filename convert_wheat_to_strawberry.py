"""Convert early WHEAT plant chains in purearch's trace to STRAWBERRY.

Hypothesis: the top agent's edge (8/10 h2h vs purearch) is 33 concurrent
strawberry (vs purearch's 18). Strawberry planted early yields ~$4000/plant
over the season vs wheat ~$240. Convert the first N PLANT WHEAT actions in
days 0-16 to PLANT STRAWBERRY (and adjust seed buying).

Risk: strawberry is ongoing (needs water for its whole life) vs wheat
(4 days). The trace's fixed water schedule may under-water the extra
strawberry. This tests whether the conversion helps despite the coupling.

Usage: python convert_wheat_to_strawberry.py --n 10 --out trace_straw10.json
"""
from __future__ import annotations

import argparse
import copy
import json
import sys

sys.path.insert(0, "reference/opponents")
import purearch_opponent as p


def convert(n_convert: int):
    units = copy.deepcopy(p._UNIT_TRACE)
    markets = copy.deepcopy(p._MARKET_TRACE)
    converted = 0
    # Convert the first `n_convert` PLANT WHEAT actions in days 0-16.
    for i, u in enumerate(units):
        day = i // 24
        if day > 16:
            continue
        if converted >= n_convert:
            break
        f = u.get("farmer", [])
        if f and f[0] == "PLANT" and len(f) > 1 and f[1] == "WHEAT":
            u["farmer"] = ["PLANT", "STRAWBERRY"]
            converted += 1
        for h in u.get("hands", []):
            if converted >= n_convert:
                break
            if h and h[0] == "PLANT" and len(h) > 1 and h[1] == "WHEAT":
                h[1] = "STRAWBERRY"
                converted += 1
        if converted >= n_convert:
            break

    # Adjust seed buying: convert n_convert WHEAT seeds to STRAWBERRY.
    adj_wheat = n_convert
    adj_straw = 0
    for m in markets:
        for op in m:
            if not op or len(op) < 3:
                continue
            if op[0] == "BUY_SEED" and op[1] == "WHEAT" and adj_wheat > 0:
                take = min(op[2], adj_wheat)
                op[2] -= take
                adj_wheat -= take
                if op[2] <= 0:
                    op[0] = "BUY_SEED"
                    op[1] = "STRAWBERRY"
                    op[2] = take
                    adj_straw += take
                else:
                    m.append(["BUY_SEED", "STRAWBERRY", take])
                    adj_straw += take
            if adj_wheat <= 0:
                break
        if adj_wheat <= 0:
            break

    return {"units": units, "markets": markets}, converted


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=10)
    ap.add_argument("--out", default="trace_straw10.json")
    args = ap.parse_args()
    trace, converted = convert(args.n)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(trace, f)
    print(f"wrote {args.out}: converted {converted} wheat->strawberry")


if __name__ == "__main__":
    main()
