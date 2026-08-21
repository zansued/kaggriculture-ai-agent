"""Sweep the maturity-aware front-run overlay of mix_agent.

For each parameter config we re-import mix_agent (clean module state), override
the maturity-overlay globals, then run a head-to-head vs purearch over N seeds.
The metric that matters is the MARGIN (d = mix - purearch), not raw reward.

Usage:
    python sweep_maturity.py --seeds 1-6 [--noshuffle]
"""
from __future__ import annotations

import argparse
import importlib
import os
import sys
import statistics

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
sys.path.insert(0, os.path.join(_HERE, "reference", "opponents"))

from kaggle_environments import make  # noqa: E402
import purearch_opponent  # noqa: E402


def load_mix(overrides: dict, disable_clone: bool = False, disable_maturity: bool = False):
    """Fresh import of mix_agent with globals overridden."""
    # Eject any previously-imported copy so module-level state is clean.
    for name in list(sys.modules):
        if name in ("mix_agent", "c27_agent", "purearch_opponent"):
            del sys.modules[name]
    sys.path.insert(0, _HERE)
    sys.path.insert(0, os.path.join(_HERE, "reference", "opponents"))
    import mix_agent  # noqa: F401
    if disable_clone:
        mix_agent._front_run_purearch = lambda a, o, s: None
    if disable_maturity:
        mix_agent._mature_opp_front_run = lambda a, o, s: None
    for k, v in overrides.items():
        setattr(mix_agent, k, v)
    return mix_agent


def parse_seeds(spec: str):
    if "-" in spec:
        a, b = spec.split("-")
        return list(range(int(a), int(b) + 1))
    return [int(x) for x in spec.split(",") if x]


def run_h2h(agent_a, agent_b, seeds):
    wins = losses = ties = 0
    margins = []
    for seed in seeds:
        env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": seed})
        env.run([agent_a, agent_b])
        last = env.steps[-1]
        r0 = last[0]["reward"] if last[0] and last[0].get("status") == "DONE" else None
        r1 = last[1]["reward"] if last[1] and last[1].get("status") == "DONE" else None
        if r0 is None or r1 is None:
            print(f"    [seed {seed}] BAD r0={r0} r1={r1}", flush=True)
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
    ap.add_argument("--seeds", default="1-6")
    ap.add_argument("--configs", default=None,
                    help="config indices to run, e.g. '4-7' or '0,2' (default: all)")
    args = ap.parse_args()
    seeds = parse_seeds(args.seeds)
    configs_all = [
        ("baseline  (clone+maturity, thresh=4/3/3/2, maxday=10/12)",
         {"_OPP_THRESH": {"STRAWBERRY": 4, "MELON": 3, "MILK": 3, "WOOL": 2},
          "_OPP_MAX_DAY": {"STRAWBERRY": 10, "MELON": 12}}, False, False),
        ("clone-only (maturity OFF)",
         {}, False, True),
        ("maturity-only (clone OFF)",
         {"_OPP_THRESH": {"STRAWBERRY": 4, "MELON": 3, "MILK": 3, "WOOL": 2},
          "_OPP_MAX_DAY": {"STRAWBERRY": 10, "MELON": 12}}, True, False),
        ("maturity earlier (-3)",
         {"_OPP_THRESH": {"STRAWBERRY": 4, "MELON": 3, "MILK": 3, "WOOL": 2},
          "_OPP_MAX_DAY": {"STRAWBERRY": 9, "MELON": 11}}, False, False),
        ("maturity later (-1)",
         {"_OPP_THRESH": {"STRAWBERRY": 4, "MELON": 3, "MILK": 3, "WOOL": 2},
          "_OPP_MAX_DAY": {"STRAWBERRY": 11, "MELON": 13}}, False, False),
        ("maturity higher thresh (6/4/4/3)",
         {"_OPP_THRESH": {"STRAWBERRY": 6, "MELON": 4, "MILK": 4, "WOOL": 3},
          "_OPP_MAX_DAY": {"STRAWBERRY": 10, "MELON": 12}}, False, False),
        ("maturity lower thresh (3/2/2/2)",
         {"_OPP_THRESH": {"STRAWBERRY": 3, "MELON": 2, "MILK": 2, "WOOL": 2},
          "_OPP_MAX_DAY": {"STRAWBERRY": 10, "MELON": 12}}, False, False),
    ]
    if args.configs is not None:
        cfg_spec = args.configs
        if "-" in cfg_spec:
            a, b = cfg_spec.split("-")
            idxs = list(range(int(a), int(b) + 1))
        else:
            idxs = [int(x) for x in cfg_spec.split(",") if x]
        configs = [configs_all[i] for i in idxs]
    else:
        configs = configs_all

    results = []
    for label, ov, dc, dm in configs:
        print(f"\n### {label}", flush=True)
        mix = load_mix(ov, disable_clone=dc, disable_maturity=dm)
        wins, losses, ties, margins = run_h2h(mix.agent, purearch_opponent.agent, seeds)
        mean_d = statistics.mean(margins) if margins else float("nan")
        total_d = sum(margins)
        results.append((label, wins, losses, ties, mean_d, total_d, len(margins)))
        print(f"    -> {wins}W-{losses}L (ties={ties}, n={len(margins)})  "
              f"mean_d={mean_d:+.0f}  total_d={total_d:+.0f}", flush=True)

    print("\n=== SUMMARY (sorted by total margin vs purearch) ===")
    results.sort(key=lambda r: -r[5])
    for label, w, l, t, mean_d, total_d, n in results:
        print(f"  {total_d:>+8}  ({w}W-{l}L, n={n})  {label}")


if __name__ == "__main__":
    main()
