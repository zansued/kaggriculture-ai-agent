"""LNS-N7: search over per-product sell caps (early/late windows).

The purearch trace's sell schedule is a tight local optimum, but the sell
TIMING is the dimension where we got closest to beating it (hold-wheat-late
reached 2-6). This parameterizes the sell schedule as per-product caps in two
time windows (early days 0-13, late days 14-27; days 28-29 always dump),
then runs CEM (cross-entropy) to find caps that beat purearch.

Caps = maximum units sold per SELL order. cap=999 means "as purearch does"
(unlimited). The search shrinks/stretches these.

Objective: mean reward vs starter over N seeds (fast proxy). Best config is
then validated h2h vs purearch.

Usage:
    python lns_sell.py --evals 60 --seeds 2   # run CEM
"""
from __future__ import annotations

import argparse
import json
import math
import os
import random
import statistics
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
sys.path.insert(0, os.path.join(_HERE, "reference", "opponents"))
import purearch_opponent as pa  # noqa: E402
from kaggle_environments import make  # noqa: E402

PRODUCTS = ["MELON", "STRAWBERRY", "WHEAT", "MILK", "WOOL", "EGG", "FERTILIZER", "CARROT"]
EARLY_END = 14   # days 0-13 = early window
LATE_END = 28    # days 14-27 = late window (28-29 always dump)
DEFAULT_CAP = 999  # purearch = unlimited

# cap index: 2 * product_i + window (0=early, 1=late)
N_PARAMS = len(PRODUCTS) * 2


def params_to_caps(params):
    """params (list of 16) -> {product: (cap_early, cap_late)}."""
    caps = {}
    for i, prod in enumerate(PRODUCTS):
        caps[prod] = (params[2 * i], params[2 * i + 1])
    return caps


def make_agent(caps: dict):
    def _agent(obs, config=None):
        trace = pa.agent(obs, config)
        day = int(obs.get("day", 0) or 0)
        market = []
        for o in trace.get("market", []):
            if o and o[0] == "SELL" and len(o) >= 3 and day < LATE_END:
                prod = o[1]
                if prod in caps:
                    cap = caps[prod][0] if day < EARLY_END else caps[prod][1]
                    qty = min(o[2], cap)
                    if qty > 0:
                        market.append(["SELL", prod, qty])
                    continue  # drop the original (capped) order
            market.append(o)
        return {"farmer": trace.get("farmer", ["PASS"]), "hands": trace.get("hands", []), "market": market[:10]}

    return _agent


def eval_caps(caps, seeds):
    agent = make_agent(caps)
    rs = []
    for s in seeds:
        env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": s})
        env.run([agent, "starter"])
        r = env.steps[-1][0]["reward"]
        if r is not None:
            rs.append(r)
    return statistics.mean(rs) if rs else 0.0


def sample_params(mean, std, rng):
    return [max(0, rng.gauss(m, s)) for m, s in zip(mean, std)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--evals", type=int, default=60, help="total configs to evaluate")
    ap.add_argument("--seeds", default="1,2", help="seeds for objective eval")
    ap.add_argument("--popsize", type=int, default=12)
    ap.add_argument("--elite", type=int, default=4)
    ap.add_argument("--out", default="lns_sell_result.json")
    args = ap.parse_args()
    seeds = [int(x) for x in args.seeds.split(",")]

    rng = random.Random(42)
    # Init: purearch (999 everywhere). Wide std so search explores smaller caps.
    mean = [float(DEFAULT_CAP)] * N_PARAMS
    std = [200.0] * N_PARAMS

    # Sanity: purearch baseline with 999 caps.
    purearch_caps = params_to_caps([DEFAULT_CAP] * N_PARAMS)
    baseline = eval_caps(purearch_caps, seeds)
    print(f"Baseline (purearch, caps=999): {baseline:.0f} over seeds {seeds}", flush=True)

    best_score = baseline
    best_params = [DEFAULT_CAP] * N_PARAMS
    evals_done = 0
    while evals_done < args.evals:
        # Sample population
        pop = []
        for _ in range(args.popsize):
            p = sample_params(mean, std, rng)
            pop.append(p)
        # Evaluate
        scored = []
        for p in pop:
            caps = params_to_caps(p)
            sc = eval_caps(caps, seeds)
            evals_done += 1
            scored.append((sc, p))
            tag = "  <= BEST" if sc > best_score else ""
            if sc > best_score:
                best_score = sc
                best_params = p
            print(f"  [{evals_done}] score={sc:.0f}{tag} caps_wheat=({p[4]:.0f},{p[5]:.0f}) "
                  f"caps_milk=({p[6]:.0f},{p[7]:.0f})", flush=True)
        # Update distribution from elite
        scored.sort(reverse=True, key=lambda x: x[0])
        elite = scored[: args.elite]
        new_mean = [statistics.mean(e[1][i] for e in elite) for i in range(N_PARAMS)]
        new_std = [max(30.0, statistics.pstdev([e[1][i] for e in elite])) for i in range(N_PARAMS)]
        mean, std = new_mean, new_std
        print(f"  elite mean={mean[:4]}... std={[round(s) for s in std[:4]]}...", flush=True)

    result = {
        "baseline": baseline,
        "best_score": best_score,
        "best_params": best_params,
        "best_caps": params_to_caps(best_params),
    }
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=1)
    print(f"\nDONE. baseline={baseline:.0f} best={best_score:.0f}")
    print(f"Best caps: {json.dumps(result['best_caps'])}")
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
