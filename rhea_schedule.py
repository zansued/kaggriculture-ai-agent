"""RHEA/CEM: search the trace's SELL TIMING to make a variant beat purearch.

Stage-3 search. purearch's sell schedule is a tight local optimum (lns_sell
confirmed), but the trace_10c4s variant (10 COW + 4 SHEEP, +value vs starter)
lost h2h 8-12. The bet: a DIFFERENT sell timing may flip the h2h.

FINDING (Aug 18): sell-timing is NOT a lever to beat purearch h2h. A CEM
init'd at caps=999 has a flat landscape (never explores restrictive caps —
lns_sell had the same flaw). Targeted hypothesis tests on 10c4s h2h vs
purearch over seeds 1-8:
  baseline    margin -2818 (3-5)   raw 71832
  milk_peak   margin -6306 (1-7)   raw 75614   <-- raises RAW reward +3.8k
  hold_wool   raw 60283 (much worse)
  hold_wheat  raw 16787 (much worse)
  straw_dump  raw 80556 (neutral)
The milk_peak result is the key insight: holding milk raises the shared-market
price for BOTH agents, and purearch (selling freely) captures MORE of it -> raw
reward up, but the h2h MARGIN worsens. So raw reward is a misleading objective
in h2h, and no sell-cap config improves the purearch margin.

CEM loop kept (with a better init for future use) but the conclusion is
documented: aggressive selling IS the h2h-optimal policy.

Usage:
    python rhea_schedule.py --evals 60 --seeds 1,2,3,4 --base data/kawasagi/trace_10c4s.json
    python rhea_schedule.py --targeted          # run the hypothesis table
"""
from __future__ import annotations

import argparse
import copy
import json
import math
import os
import random
import statistics
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
sys.path.insert(0, os.path.join(_HERE, "reference", "opponents"))
sys.path.insert(0, os.path.join(_HERE, "src"))

import purearch_opponent as pa  # noqa: E402
import trace_agent  # noqa: E402
from kaggle_environments import make  # noqa: E402

PRODUCTS = ["MELON", "STRAWBERRY", "WHEAT", "MILK", "WOOL", "FERTILIZER", "CARROT"]
WINDOWS = [(0, 8), (9, 18), (19, 27)]  # day 28-29 always dump
DEFAULT_CAP = 999

N_PARAMS = len(PRODUCTS) * len(WINDOWS)


def params_to_caps(params):
    """params (list of 21) -> {product: [cap_early, cap_mid, cap_late]}."""
    caps = {}
    for i, prod in enumerate(PRODUCTS):
        caps[prod] = [params[i * len(WINDOWS) + w] for w in range(len(WINDOWS))]
    return caps


def make_agent(base_agent, caps: dict):
    """Wrap a trace agent, capping SELL order quantities per window."""
    def _agent(obs, config=None):
        trace = base_agent(obs, config)
        day = int(obs.get("day", 0) or 0)
        if day >= 28:
            return trace  # terminal dump, uncapped
        market = []
        for o in trace.get("market", []):
            if o and o[0] == "SELL" and len(o) >= 3:
                prod = o[1]
                if prod in caps:
                    cap = caps[prod][0] if day <= 8 else caps[prod][1] if day <= 18 else caps[prod][2]
                    qty = min(o[2], cap)
                    if qty > 0:
                        market.append(["SELL", prod, qty])
                    continue
            market.append(o)
        return {"farmer": trace.get("farmer", ["PASS"]), "hands": trace.get("hands", []), "market": market[:10]}

    return _agent


def eval_h2h(agent, seeds):
    """Mean reward of `agent` vs purearch on paired seeds (agent is P0)."""
    rs = []
    for s in seeds:
        env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": s})
        env.run([agent, pa.agent])
        r = env.steps[-1][0]["reward"]
        if r is not None:
            rs.append(r)
    return statistics.mean(rs) if rs else 0.0


def sample_params(mean, std, rng):
    return [max(0, rng.gauss(m, s)) for m, s in zip(mean, std)]


def _full_caps(**kw):
    c = {p: [999, 999, 999] for p in PRODUCTS}
    for k, v in kw.items():
        c[k] = list(v)
    return c


def run_targeted(base_path, seeds):
    """Hypothesis table (price-dynamics sell-timing) with h2h MARGIN vs purearch."""
    base_agent = trace_agent.load_trace_agent(base_path)
    configs = {
        "baseline":   _full_caps(),
        "milk_peak":  _full_caps(MILK=[5, 999, 5]),
        "hold_wool":  _full_caps(WOOL=[0, 5, 999]),
        "hold_wheat": _full_caps(WHEAT=[0, 0, 999]),
        "straw_dump": _full_caps(STRAWBERRY=[999, 999, 5]),
        "combo":      _full_caps(WOOL=[0, 5, 999], WHEAT=[0, 0, 999], MILK=[5, 999, 5],
                                 STRAWBERRY=[999, 999, 5]),
    }
    for name, c in configs.items():
        agent = make_agent(base_agent, c)
        margins = []
        for s in seeds:
            env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": s})
            env.run([agent, pa.agent])
            r0 = env.steps[-1][0]["reward"]; r1 = env.steps[-1][1]["reward"]
            margins.append(r0 - r1)
        mean_d = statistics.mean(margins)
        wins = sum(1 for d in margins if d > 0)
        print(f"{name:12s} margin={mean_d:>+8.0f}  W-L={wins}-{len(seeds)-wins}  per_seed={[int(d) for d in margins]}", flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--targeted", action="store_true", help="run the hypothesis table (margins)")
    ap.add_argument("--evals", type=int, default=60)
    ap.add_argument("--seeds", default="1,2,3,4")
    ap.add_argument("--popsize", type=int, default=10)
    ap.add_argument("--elite", type=int, default=4)
    ap.add_argument("--base", default="data/kawasagi/trace_10c4s.json")
    ap.add_argument("--out", default="rhea_schedule_result.json")
    args = ap.parse_args()
    seeds = [int(x) for x in args.seeds.split(",")]

    if args.targeted:
        run_targeted(args.base, seeds)
        return

    base_agent = trace_agent.load_trace_agent(args.base)
    rng = random.Random(42)
    # Fix for the flat-landscape flaw: init at a MODERATE cap (250) with wide
    # std so the search actually explores restrictive (hold) caps. cap=999 init
    # only samples [799,1199] = effectively uncapped -> flat fitness (lns_sell
    # had the same flaw). Kept for future use; conclusion is documented.
    mean = [250.0] * N_PARAMS
    std = [220.0] * N_PARAMS

    # Baselines (uncapped = purearch sells).
    pure = make_agent(base_agent, params_to_caps([DEFAULT_CAP] * N_PARAMS))
    baseline = eval_h2h(pure, seeds)
    print(f"Baseline ({os.path.basename(args.base)} uncapped) h2h vs purearch over {seeds}: {baseline:.0f}", flush=True)

    best_score = baseline
    best_params = [DEFAULT_CAP] * N_PARAMS
    evals_done = 0
    while evals_done < args.evals:
        pop = [sample_params(mean, std, rng) for _ in range(args.popsize)]
        scored = []
        for p in pop:
            caps = params_to_caps(p)
            agent = make_agent(base_agent, caps)
            sc = eval_h2h(agent, seeds)
            evals_done += 1
            scored.append((sc, p))
            tag = "  <= BEST" if sc > best_score else ""
            if sc > best_score:
                best_score = sc
                best_params = p
            print(f"  [{evals_done}] h2h={sc:.0f}{tag} "
                  f"milk=({p[9]:.0f},{p[10]:.0f},{p[11]:.0f}) "
                  f"wool=({p[12]:.0f},{p[13]:.0f},{p[14]:.0f}) "
                  f"wheat=({p[6]:.0f},{p[7]:.0f},{p[8]:.0f})", flush=True)
        scored.sort(reverse=True, key=lambda x: x[0])
        elite = scored[: args.elite]
        mean = [statistics.mean(e[1][i] for e in elite) for i in range(N_PARAMS)]
        std = [max(30.0, statistics.pstdev([e[1][i] for e in elite])) for i in range(N_PARAMS)]
        print(f"  elite mean milk={[round(mean[9]), round(mean[10]), round(mean[11])]} "
              f"wool={[round(mean[12]), round(mean[13]), round(mean[14])]}", flush=True)

    result = {
        "base": args.base,
        "seeds": seeds,
        "baseline_h2h": baseline,
        "best_h2h": best_score,
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
