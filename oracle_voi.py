"""Oracle VOI: measure the value of perfect knowledge of the opponent's future sells.

The report's #1 experiment. If knowing exactly when the opponent will dump
premium products barely improves the h2h win-rate, opponent forecasting is not
worth building. If it's large, inference is a first-class front.

The oracle is OFFLINE-ONLY: it reads the opponent's ACTUAL future market sells
from its trace (impossible online) and sells my shed stock of those products
BEFORE the opponent — perfect front-running with H-turn lookahead. It is the
theoretical ceiling of front-run/denial; it must never ship in a submission.

Comparison: baseline = mix_agent (which has an approximate maturity front-run).
Oracle H in {1,3,6,12} = mix + perfect future-sell knowledge.

Metric: h2h win-rate + margin vs purearch (paired seeds, both seats). The
report says the ladder rates W/L/D, not margin — so report BOTH.

Usage: python oracle_voi.py [--h 1,3,6,12] [--seeds 1-12]
"""
from __future__ import annotations

import argparse
import os
import sys
import statistics

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
sys.path.insert(0, os.path.join(_HERE, "reference", "opponents"))
sys.path.insert(0, os.path.join(_HERE, "src"))

import mix_agent  # noqa: E402
import purearch_opponent as pa  # noqa: E402
from kaggle_environments import make  # noqa: E402


def make_oracle(horizon: int):
    """mix_agent + perfect front-run reading purearch's future sells (H turns)."""
    def agent(obs, config=None):
        action = mix_agent.agent(obs, config)
        step = min(int(obs.get("step", 0) or 0), len(pa._MARKET_TRACE) - 1)
        # Perfect knowledge: purearch's SELL orders in the next `horizon` turns.
        planned = {}
        for fs in range(step + 1, min(len(pa._MARKET_TRACE), step + horizon + 1)):
            for o in pa._MARKET_TRACE[fs]:
                if (isinstance(o, list) and len(o) >= 3 and o[0] == "SELL"
                        and o[1] in ("MELON", "STRAWBERRY", "MILK", "WOOL")):
                    item = o[1]
                    planned[item] = planned.get(item, 0) + max(0, int(o[2] or 0))
        if not planned:
            return action
        orders = list(action.get("market", []) or [])
        already = set()
        for o in orders:
            if isinstance(o, list) and len(o) >= 2 and o[0] == "SELL":
                already.add(o[1])
        shed = (obs.get("private") or {}).get("shed") or {}
        front = []
        for item, _q in sorted(planned.items(), key=lambda kv: -kv[1]):
            qty = int(shed.get(item, 0) or 0)
            if qty > 0 and item not in already and len(front) + len(orders) < 10:
                front.append(["SELL", item, qty])
                already.add(item)
        action["market"] = (front + orders)[:10]
        return action
    return agent


def parse_seeds(spec):
    if "-" in spec:
        a, b = spec.split("-")
        return list(range(int(a), int(b) + 1))
    return [int(x) for x in spec.split(",") if x]


def run_h2h(agent_a, agent_b, seeds):
    wins = losses = ties = 0
    margins = []
    for s in seeds:
        env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": s})
        env.run([agent_a, agent_b])
        last = env.steps[-1]
        r0 = last[0]["reward"] if last[0] and last[0].get("status") == "DONE" else None
        r1 = last[1]["reward"] if last[1] and last[1].get("status") == "DONE" else None
        if r0 is None or r1 is None:
            continue
        margins.append(r0 - r1)
        if r0 > r1:
            wins += 1
        elif r1 > r0:
            losses += 1
        else:
            ties += 1
    return wins, losses, ties, margins


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--h", default="1,3,6,12")
    ap.add_argument("--seeds", default="1-12")
    args = ap.parse_args()
    horizons = [int(x) for x in args.h.split(",")]
    seeds = parse_seeds(args.seeds)

    base = mix_agent.agent
    w, l, t, ms = run_h2h(base, pa.agent, seeds)
    print(f"baseline mix   vs purearch: {w}W-{l}L (t={t})  margin={statistics.mean(ms):+.0f}")
    wr_base = w / (w + l + t) if (w + l + t) else 0.0

    for h in horizons:
        oracle = make_oracle(h)
        w, l, t, ms = run_h2h(oracle, pa.agent, seeds)
        wr = w / (w + l + t) if (w + l + t) else 0.0
        print(f"oracle H={h:>2}    vs purearch: {w}W-{l}L (t={t})  "
              f"margin={statistics.mean(ms):+.0f}  dwinrate={wr - wr_base:+.3f}")


if __name__ == "__main__":
    main()
