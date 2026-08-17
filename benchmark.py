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
    # Strawberry tuning (on top of the 8+6 livestock default).
    "st6": {"strawberry_target": 6},
    "st8": {"strawberry_target": 8},
    "st10": {"strawberry_target": 10},
    "st12": {"strawberry_target": 12},
    "s16": {"seed_buffers": {"MELON": 3, "WHEAT": 8, "STRAWBERRY": 16}},
    "st8_s16": {"strawberry_target": 8, "seed_buffers": {"MELON": 3, "WHEAT": 8, "STRAWBERRY": 16}},
    "st10_s16": {"strawberry_target": 10, "seed_buffers": {"MELON": 3, "WHEAT": 8, "STRAWBERRY": 16}},
    "st8_wcap4": {"strawberry_target": 8, "max_wheat_plants": 4},
    # --- session-10 reactive production-gap variants (9+4 livestock default) ---
    "st8_w20": {"strawberry_target": 8, "max_wheat_plants": 20},
    "st12_w20": {"strawberry_target": 12, "max_wheat_plants": 20},
    "st12_w30": {"strawberry_target": 12, "max_wheat_plants": 30},
    "st16_w30": {"strawberry_target": 16, "max_wheat_plants": 30},
    "st20_w30": {"strawberry_target": 20, "max_wheat_plants": 30},
    "h10": {"livestock_hands": 10},
    "h12": {"livestock_hands": 12},
    "h14": {"livestock_hands": 14},
    "h12_st12_w30": {"livestock_hands": 12, "strawberry_target": 12, "max_wheat_plants": 30},
    # Aggressive sell: compounding theory — sell fast, reinvest in production.
    "aggsell": {"premium_sell_per_turn": 999, "premium_sell_floor": None},
    "aggsell_h12": {"premium_sell_per_turn": 999, "premium_sell_floor": None, "livestock_hands": 12},
    "aggsell_h12_st12_w30": {"premium_sell_per_turn": 999, "premium_sell_floor": None,
                             "livestock_hands": 12, "strawberry_target": 12, "max_wheat_plants": 30},
    "st12_w30_h12": {"strawberry_target": 12, "max_wheat_plants": 30, "livestock_hands": 12},
    # Hand-ramp: hands reset daily at fibonacci cost, so hiring beyond today's
    # work burns early gold that could buy animals. Ramp by day.
    "ramp_pure": {"hand_ramp": [4, 6, 5, 5, 6, 6, 6, 8, 10, 11, 12, 12]},
    "ramp_slow8": {"hand_ramp": [3, 4, 4, 5, 5, 6, 6, 8, 8, 8, 8, 8]},
    "ramp_early4": {"hand_ramp": [4, 4, 4, 4, 6, 6, 6, 8, 8, 8, 8, 8]},
    "ramp_pure_aggsell": {"hand_ramp": [4, 6, 5, 5, 6, 6, 6, 8, 10, 11, 12, 12],
                          "premium_sell_per_turn": 999, "premium_sell_floor": None},
    "ramp_pure_st12_w30": {"hand_ramp": [4, 6, 5, 5, 6, 6, 6, 8, 10, 11, 12, 12],
                           "strawberry_target": 12, "max_wheat_plants": 30},
    # --- land done right: 3x tiles is the real production multiplier ---
    "land7_h12_st12_w30": {"buy_land_day": 7, "livestock_hands": 12,
                           "strawberry_target": 12, "max_wheat_plants": 30},
    "land7_h12_st16_w40": {"buy_land_day": 7, "livestock_hands": 12,
                           "strawberry_target": 16, "max_wheat_plants": 40},
    "land7_h12": {"buy_land_day": 7, "livestock_hands": 12},
    "land10_h12_st12_w30": {"buy_land_day": 10, "livestock_hands": 12,
                            "strawberry_target": 12, "max_wheat_plants": 30},
    "land7_h14_st16_w40": {"buy_land_day": 7, "livestock_hands": 14,
                           "strawberry_target": 16, "max_wheat_plants": 40},
    # Animal-mix tweaks from microbenchmark (COW $140/action > SHEEP $136/action;
    # keep 13 structures so tile count unchanged).
    "l_103": {"animal_plan": [["COW", 10], ["SHEEP", 3]]},
    "l_102": {"animal_plan": [["COW", 10], ["SHEEP", 2]]},
    "l_112": {"animal_plan": [["COW", 11], ["SHEEP", 2]]},
    "l_113": {"animal_plan": [["COW", 11], ["SHEEP", 3]]},
    # 12-animal mixes (12 structures -> 13 crop tiles)
    "l_84": {"animal_plan": [["COW", 8], ["SHEEP", 4]]},
    "l_93": {"animal_plan": [["COW", 9], ["SHEEP", 3]]},
    "l_111": {"animal_plan": [["COW", 11], ["SHEEP", 1]]},
    # 11-animal mixes (11 structures -> 14 crop tiles)
    "l_92": {"animal_plan": [["COW", 9], ["SHEEP", 2]]},
    "l_101": {"animal_plan": [["COW", 10], ["SHEEP", 1]]},
    # --- zone ownership: strict home-zone per hand to kill 75-tile thrashing ---
    "zone75": {"buy_land_day": 6, "zone_ownership": True},
    "zone75_h10": {"buy_land_day": 6, "zone_ownership": True, "livestock_hands": 10},
    "zone75_h12": {"buy_land_day": 6, "zone_ownership": True, "livestock_hands": 12},
    "zone75_st12": {"buy_land_day": 6, "zone_ownership": True, "strawberry_target": 12},
    "zone75_h12_st12": {"buy_land_day": 6, "zone_ownership": True, "livestock_hands": 12,
                        "strawberry_target": 12, "max_wheat_plants": 30},
    "reactive75_plain": {"buy_land_day": 6},  # land without zone ownership (control)
    # --- price-window planting: score crops by harvest-window price ---
    "pwp": {"price_window_plant": True},
    "pwp_st12_w30": {"price_window_plant": True, "strawberry_target": 12, "max_wheat_plants": 30},
    "pwp_st16_w40": {"price_window_plant": True, "strawberry_target": 16, "max_wheat_plants": 40},
    "pwp_h10": {"price_window_plant": True, "livestock_hands": 10},
    "livestock_86": {"livestock": True, "animal_plan": [["COW", 8], ["SHEEP", 6]]},
    "livestock_86_h8": {"livestock": True, "animal_plan": [["COW", 8], ["SHEEP", 6]], "livestock_hands": 8},
    "livestock_86_h10": {"livestock": True, "animal_plan": [["COW", 8], ["SHEEP", 6]], "livestock_hands": 10},
    "livestock_86_h12": {"livestock": True, "animal_plan": [["COW", 8], ["SHEEP", 6]], "livestock_hands": 12},
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
    # --- 16/08: escala de terra (replicar c27: terra dia 11 + zone + hands) ---
    "land11": {"buy_land_day": 11},
    "land11_zone_h12": {"buy_land_day": 11, "zone_ownership": True, "livestock_hands": 12},
    "land11_zone_h12_st25": {"buy_land_day": 11, "zone_ownership": True, "livestock_hands": 12,
                             "strawberry_target": 25},
    "land11_zone_h12_st25_w40": {"buy_land_day": 11, "zone_ownership": True, "livestock_hands": 12,
                                 "strawberry_target": 25, "max_wheat_plants": 40},
    "land14_zone_h14_st30_w50": {"buy_land_day": 14, "zone_ownership": True, "livestock_hands": 14,
                                 "strawberry_target": 30, "max_wheat_plants": 50},
    # Muitas hands para cobrir 75 tiles
    "land11_h18": {"buy_land_day": 11, "livestock_hands": 18},
    "land11_h22": {"buy_land_day": 11, "livestock_hands": 22},
    "land11_h18_w60": {"buy_land_day": 11, "livestock_hands": 18, "max_wheat_plants": 60},
    "land11_h18_w60_nostraw": {"buy_land_day": 11, "livestock_hands": 18, "max_wheat_plants": 60,
                               "strawberry_target": 0},
    # wheat rush na terra nova, hands moderadas
    "land11_h12_nostraw": {"buy_land_day": 11, "livestock_hands": 12, "strawberry_target": 0},
    "land11_h12_w60_nostraw": {"buy_land_day": 11, "livestock_hands": 12, "max_wheat_plants": 60,
                               "strawberry_target": 0},
    "land11_h12_w60_st12": {"buy_land_day": 11, "livestock_hands": 12, "max_wheat_plants": 60,
                            "strawberry_target": 12},
    "land14_h12_w60_nostraw": {"buy_land_day": 14, "livestock_hands": 12, "max_wheat_plants": 60,
                               "strawberry_target": 0},
    # isolar: menos animais = mais rega
    "land11_h12_anim42": {"buy_land_day": 11, "livestock_hands": 12, "animal_plan": [["COW", 4], ["SHEEP", 2]]},
    "land11_h12_anim0": {"buy_land_day": 11, "livestock_hands": 12, "animal_plan": []},
    "land11_h12_anim62": {"buy_land_day": 11, "livestock_hands": 12, "animal_plan": [["COW", 6], ["SHEEP", 2]]},
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
