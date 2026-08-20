"""Stage-5 (PSRO) step 1: build the META-GAME payoff matrix and find the Nash.

Population = the diverse strategies we have:
  purearch        8 COW + 6 SHEEP trace, 75 tiles, ~181k (our best, tight opt.)
  trace_10c4s     10 COW + 4 SHEEP trace, ~183k vs starter but loses to purearch
  trace_10c4s_mixed  another 10+4 conversion variant
  reactive_94     9 COW + 4 SHEEP FarmBrain, 25 tiles, ~88k
  reactive_102    10 COW + 2 SHEEP FarmBrain, best vs-starter reactive (~89k)
  top_p1          top-agent P1 raw trace (state-coupled, weak but DIFFERENT)

For each ordered pair (A,B) we compute A's mean h2h margin vs B over `seeds`
(the metric that matters). Then solve the meta-game: the mixed strategy over
the population that maximizes worst-case payoff (maximin), via replicator
dynamics. Report the Nash support and each strategy's exploitability (how
much a Nash-optimal opponent beats it by).

Usage:
    python psro_meta.py --seeds 1,2,3,4
"""
from __future__ import annotations

import argparse
import os
import statistics
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
sys.path.insert(0, os.path.join(_HERE, "reference", "opponents"))
sys.path.insert(0, os.path.join(_HERE, "src"))

from kaggle_environments import make  # noqa: E402

import trace_agent  # noqa: E402
import kaggriculture_real as kr  # noqa: E402


def _load_population():
    pop = {}

    def _trace(name):
        return trace_agent.load_trace_agent(os.path.join(_HERE, "data", "kawasagi", name))

    pop["purearch"] = _trace("trace_purearch.json")
    pop["trace_10c4s"] = _trace("trace_10c4s.json")
    pop["trace_10c4s_mixed"] = _trace("trace_10c4s_mixed.json")
    pop["top_p1"] = _trace("trace_92730021_p1.json")

    # Gui's c27_agent (self-contained): c27 trace + clone-detection front-run.
    import c27_agent  # noqa: E402
    pop["c27"] = c27_agent.agent

    def _fb(**cfg):
        b = kr.FarmBrain(**cfg)
        return lambda obs, c=None: b.decide(obs)

    pop["reactive_94"] = _fb()
    pop["reactive_102"] = _fb(animal_plan=[["COW", 10], ["SHEEP", 2]])
    return pop


def mean_margin(agent_a, agent_b, seeds):
    ms = []
    for s in seeds:
        env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": s})
        env.run([agent_a, agent_b])
        last = env.steps[-1]
        ms.append(last[0]["reward"] - last[1]["reward"])
    return statistics.mean(ms)


def replicator_dynamics(M, iters=2000):
    """Maximin mixed strategy for the ROW player over payoff matrix M."""
    n = len(M)
    x = [1.0 / n] * n
    for _ in range(iters):
        # row player payoff vs each pure column
        val = [sum(x[i] * M[i][j] for i in range(n)) for j in range(n)]
        worst = min(val)  # opponent plays the best response column
        # gradient: improve probability on rows that do well vs the worst column
        # (simplified replicator): x_i *= (M[i][j*] - val[j*] + c)
        jstar = val.index(worst)
        c = max(0.0, -min(M[i][jstar] for i in range(n))) + 1.0
        fit = [M[i][jstar] + c for i in range(n)]
        avg = sum(x[i] * fit[i] for i in range(n))
        x = [x[i] * fit[i] / avg for i in range(n)]
    return x, min(val)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", default="1,2,3,4")
    args = ap.parse_args()
    seeds = [int(v) for v in args.seeds.split(",")]

    pop = _load_population()
    names = list(pop.keys())
    n = len(names)
    print(f"Population: {names}")
    print(f"Seeds: {seeds}  (paired h2h margins, row player = row strategy)\n", flush=True)

    # Payoff matrix M[i][j] = mean margin of names[i] (P0) vs names[j] (P1).
    M = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(n):
            if i == j:
                M[i][j] = 0.0  # mirror: ~0 by symmetry (skip games)
                continue
            M[i][j] = mean_margin(pop[names[i]], pop[names[j]], seeds)
            print(f"  {names[i]:<16} vs {names[j]:<16}: {M[i][j]:+8.0f}", flush=True)
    print("")

    # Nash (maximin) for the row player.
    x, worst_payoff = replicator_dynamics(M)
    print("=== META-NASH (maximin over population) ===")
    for name, xi in sorted(zip(names, x), key=lambda t: -t[1]):
        if xi > 0.01:
            print(f"  {name:<16} weight={xi:0.3f}")
    print(f"  worst-case payoff vs best response: {worst_payoff:+.0f}")

    # Exploitability of each PURE strategy: min_j M[i][j] (worst it can be beaten).
    print("\n=== Exploitability (worst margin each pure strategy suffers) ===")
    for i, name in enumerate(names):
        worst = min(M[i][j] for j in range(n) if j != i)
        print(f"  {name:<16} worst={worst:+8.0f}")

    # Print the full matrix for the record.
    print("\n=== PAYOFF MATRIX (row vs column) ===")
    print("        " + "".join(f"{nm:>14}" for nm in names))
    for i, name in enumerate(names):
        print(f"{name:<8}" + "".join(f"{M[i][j]:>14.0f}" for j in range(n)))


if __name__ == "__main__":
    main()
