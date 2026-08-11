"""Real-environment benchmark harness for the Kaggriculture agent.

Runs FarmBrain variants against built-in opponents across multiple seeds
using the actual engine (kaggle_environments.make('kaggriculture')).

Usage:
    python benchmark.py                          # default vs starter, 3 seeds
    python benchmark.py --opponent random --seeds 5
    python benchmark.py --compare land15,land20,hands3 --seeds 8
    python benchmark.py --steps 100               # smoke test, short episode
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time

from kaggle_environments import make

REPO = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(REPO, "src"))
import kaggriculture_real as kr  # noqa: E402

# Custom (function) opponents, e.g. the reconstructed 2600-Elo public agent.
sys.path.insert(0, os.path.join(REPO, "reference", "opponents"))
import purearch_opponent  # noqa: E402

OPPONENT_FUNCTIONS = {
    "purearch": purearch_opponent.agent,
}

# Named FarmBrain variants. "default" is the committed default config.
VARIANT_CONFIGS: dict[str, dict] = {
    "default": {},  # includes melon_plant_gate=240, harvest_at_cap=True by default
    "nogate": {"melon_plant_gate": None},
    "noharvcap": {"harvest_at_cap": False},
    "gate240_hands3": {"melon_plant_gate": 240, "max_hands": 3},
    # Land expansion — buy NE quadrant on a chosen day.
    "land10": {"buy_land_day": 10},
    "land15": {"buy_land_day": 15},
    "land20": {"buy_land_day": 20},
    # More/fewer farm hands.
    "hands1": {"max_hands": 1},
    "hands3": {"max_hands": 3},
    "hands4": {"max_hands": 4},
    # Seed buffer.
    "seed4": {"seed_buffer": 4},
    "seed8": {"seed_buffer": 8},
    "seed12": {"seed_buffer": 12},
    # Premium tuning.
    "no_floor": {"premium_sell_floor": None},
    "floor50": {"premium_sell_floor": 50},
    "floor150": {"premium_sell_floor": 150},
    "prem1": {"premium_sell_per_turn": 1},
    "prem3": {"premium_sell_per_turn": 3},
    "prem4": {"premium_sell_per_turn": 4},
    "prem1_f150": {"premium_sell_per_turn": 1, "premium_sell_floor": 150},
    "floor150": {"premium_sell_floor": 150},
    "floor200": {"premium_sell_floor": 200},
    "floor80": {"premium_sell_floor": 80},
    "premcap2": {"max_premium_plants": 2},
    "premcap4": {"max_premium_plants": 4},
    # Crop restriction — the profit calc over-values slow ongoing crops.
    "m": {"crops": ["MELON"]},
    "wm": {"crops": ["WHEAT", "MELON"]},
    "wcm": {"crops": ["WHEAT", "CARROT", "MELON"]},
    "premium": {"crops": ["MELON", "STRAWBERRY"]},
    "all_fast": {"crops": ["WHEAT", "CARROT"]},
    # Melon focus: while gate open, concentrate all seeds/planting on melon.
    "focus": {"melon_focus": True},
    "focus_hands3": {"melon_focus": True, "max_hands": 3},
    # Harvest one-time crops as soon as yield caps (melon at age 10, not 12).
    "harvcap": {"harvest_at_cap": True},
    "harvcap_g220": {"harvest_at_cap": True, "melon_plant_gate": 220},
    "harvcap_g230": {"harvest_at_cap": True, "melon_plant_gate": 230},
    "harvcap_g250": {"harvest_at_cap": True, "melon_plant_gate": 250},
    # Full livestock economy (cows+sheep+strawberry).
    "livestock": {"livestock": True},
    "livestock_46": {"livestock": True, "animal_plan": [["COW", 4], ["SHEEP", 3]]},
    "livestock_86": {"livestock": True, "animal_plan": [["COW", 8], ["SHEEP", 6]]},
    "livestock_handsmix": {"livestock": True, "animal_plan": [["COW", 5], ["SHEEP", 4]], "livestock_hands": 10},
    # Melon plant gate: stop planting melon when its price < gate.
    "gate180": {"melon_plant_gate": 180},
    "gate200": {"melon_plant_gate": 200},
    "gate210": {"melon_plant_gate": 210},
    "gate220": {"melon_plant_gate": 220},
    "gate230": {"melon_plant_gate": 230},
    "gate235": {"melon_plant_gate": 235},
    "gate240": {"melon_plant_gate": 240},
    "gate245": {"melon_plant_gate": 245},
    "gate250": {"melon_plant_gate": 250},
    "gate255": {"melon_plant_gate": 255},
    # Fertilizer / animals.
    "fert": {"fert_strawberry": True},
    "goose": {"animal": "GOOSE", "animal_day": 2},
    "cow": {"animal": "COW", "animal_day": 3},
    "sheep": {"animal": "SHEEP", "animal_day": 3},
}


def make_agent(config: dict | None):
    brain = kr.FarmBrain(**(config or {}))

    def _agent(obs, _cfg=None):
        return brain.decide(obs)

    return _agent


def run_game(agent, opponent, seed, steps: int):
    """Run one full game; return (my_reward, opp_reward, my_status, opp_status)."""
    env = make("kaggriculture", configuration={"episodeSteps": steps, "seed": seed})
    env.run([agent, opponent])
    last = env.steps[-1]
    s0, s1 = last[0], last[1]
    r0 = s0["reward"] if s0 else None
    r1 = s1["reward"] if s1 else None
    st0 = s0["status"] if s0 else None
    st1 = s1["status"] if s1 else None
    return r0, r1, st0, st1


def resolve_opponent(opponent: str):
    """Return the env.run opponent argument (built-in string or callable)."""
    if opponent in OPPONENT_FUNCTIONS:
        return OPPONENT_FUNCTIONS[opponent]
    return opponent


def benchmark_variant(name: str, config: dict, opponent: str, seeds: list[int], steps: int):
    agent = make_agent(config)
    opp = resolve_opponent(opponent)
    results = []
    for seed in seeds:
        t0 = time.time()
        try:
            r0, r1, st0, st1 = run_game(agent, opp, seed, steps)
            elapsed = time.time() - t0
            ok = st0 == "DONE" and r0 is not None
            results.append({"seed": seed, "mine": r0, "opp": r1,
                            "my_status": st0, "opp_status": st1, "seconds": round(elapsed, 1)})
            tag = "OK" if ok else f"BAD({st0})"
            print(f"  [seed {seed:>2}] {tag}  mine={r0}  opp={r1}  ({elapsed:.1f}s)", flush=True)
        except Exception as e:  # noqa: BLE001
            print(f"  [seed {seed:>2}] EXC {type(e).__name__}: {e}", flush=True)
            results.append({"seed": seed, "mine": None, "opp": None,
                            "my_status": "EXC", "opp_status": None, "seconds": 0.0})

    valid = [r for r in results if r["mine"] is not None and r["my_status"] == "DONE"]
    if valid:
        mine = [r["mine"] for r in valid]
        opp = [r["opp"] for r in valid if r["opp"] is not None]
        wins = sum(1 for r in valid if r["mine"] > (r["opp"] or 0))
        summary = {
            "variant": name,
            "opponent": opponent,
            "games_ok": len(valid),
            "games_attempted": len(seeds),
            "mean_mine": round(statistics.mean(mine), 1),
            "median_mine": round(statistics.median(mine), 1),
            "min_mine": round(min(mine), 1),
            "max_mine": round(max(mine), 1),
            "mean_opp": round(statistics.mean(opp), 1) if opp else None,
            "win_rate": round(wins / len(valid), 3),
            "per_game_seconds": round(statistics.mean([r["seconds"] for r in valid]), 1),
        }
    else:
        summary = {"variant": name, "opponent": opponent, "games_ok": 0,
                   "games_attempted": len(seeds), "error": "no DONE games"}
    print(f"  SUMMARY {json.dumps(summary)}", flush=True)
    return {"summary": summary, "games": results}


def parse_seeds(seed_spec: str) -> list[int]:
    if seed_spec == "auto":
        return list(range(1, 11))
    try:
        return [int(x) for x in seed_spec.split(",") if x.strip()]
    except ValueError:
        print(f"Invalid --seeds spec: {seed_spec!r} (use 'auto' or '1,2,3')")
        sys.exit(1)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--opponent", default="starter",
                    choices=["starter", "random", "pass"] + list(OPPONENT_FUNCTIONS))
    ap.add_argument("--seeds", default="1,2,3", help="comma list of seeds, or 'auto' (1..10)")
    ap.add_argument("--steps", type=int, default=720, help="episodeSteps per game")
    ap.add_argument("--variant", default="default", help="single variant name (see VARIANT_CONFIGS)")
    ap.add_argument("--compare", default=None,
                    help="comma-separated variant names to compare (e.g. 'default,land15,land20')")
    ap.add_argument("--json", default=None, help="write full results JSON to this path")
    args = ap.parse_args()

    if args.compare:
        names = [n.strip() for n in args.compare.split(",") if n.strip()]
    else:
        names = [args.variant]

    seeds = parse_seeds(args.seeds)
    print(f"=== Kaggriculture benchmark: {len(names)} variant(s) x {len(seeds)} seeds "
          f"vs '{args.opponent}' ({args.steps} steps) ===", flush=True)

    all_out = {"config": {"opponent": args.opponent, "steps": args.steps, "seeds": seeds}, "variants": []}
    for name in names:
        if name not in VARIANT_CONFIGS:
            print(f"Unknown variant {name!r}; available: {sorted(VARIANT_CONFIGS)}")
            sys.exit(1)
        print(f"\n--- variant: {name} ({VARIANT_CONFIGS[name]}) ---", flush=True)
        out = benchmark_variant(name, VARIANT_CONFIGS[name], args.opponent, seeds, args.steps)
        all_out["variants"].append(out)

    # Ranking table
    print("\n=== RANKING (mean reward) ===")
    ranked = sorted(
        (v["summary"] for v in all_out["variants"] if v["summary"].get("mean_mine") is not None),
        key=lambda s: s["mean_mine"], reverse=True,
    )
    for i, s in enumerate(ranked, 1):
        print(f"  {i}. {s['variant']:<12} mean={s['mean_mine']:>9}  median={s['median_mine']:>9}  "
              f"win_rate={s['win_rate']:.3f}  (n={s['games_ok']})")

    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(all_out, f, indent=2)
        print(f"\nWrote results to {args.json}")


if __name__ == "__main__":
    main()
