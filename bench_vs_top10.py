"""Benchmark nosso agente contra os TRACES dos top 10, nos seeds originais.

Para cada episódio top10, extrai o trace de cada player-alvo do replay e roda
nosso agente (P0) vs trace (P1) no MESMO seed do episódio.

Uso:
    python bench_vs_top10.py --agent submissions/hybrid_v2/main.py [--out data/top10/bench.json]
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
sys.path.insert(0, os.path.join(_HERE, "data", "kawasagi"))
sys.path.insert(0, os.path.join(_HERE, "reference", "opponents"))
sys.stdout.reconfigure(encoding="utf-8")

from build_trace import build as build_trace  # noqa: E402
import trace_agent  # noqa: E402
from kaggle_environments import make  # noqa: E402

# episódio -> [(player, rank, team, reward_original)]
EPISODES = {
    "98419962": [("851118847", 0, 2, "Crop Dusta"), ("851118847", 1, 1, "Ryo Hasegawa")],
    "98419964": [("1243789113", 0, 2, "Crop Dusta"), ("1243789113", 1, 3, "Subramanya N")],
    "98426786": [("1638905968", 0, 5, "Say My Name ?"), ("1638905968", 1, 4, "junseok lee")],
    "98403998": [("647390248", 0, 6, "Arman Tuganbaev"), ("647390248", 1, 10, "ActiveMusyoku")],
    "98415386": [("1647964172", 1, 7, "Yizuki")],
    "98433623": [("338247171", 0, 8, "Kaileh57")],
    "98424471": [("688102744", 0, 8, "Kaileh57"), ("688102744", 1, 9, "Ueddy")],
    "98442664": [("22062911", 0, 10, "ActiveMusyoku")],
}


def load_agent(path: str):
    spec = importlib.util.spec_from_file_location("our_agent", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.agent


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--agent", default="submissions/hybrid_v2/main.py")
    ap.add_argument("--dir", default="data/top10")
    ap.add_argument("--out", default="data/top10/bench.json")
    args = ap.parse_args()

    our = load_agent(args.agent)
    results = []
    for ep_id, entries in EPISODES.items():
        replay_path = os.path.join(args.dir, f"episode-{ep_id}-replay.json")
        if not os.path.exists(replay_path):
            print(f"AVISO: replay {ep_id} não encontrado", file=sys.stderr)
            continue
        with open(replay_path, encoding="utf-8") as f:
            data = json.load(f)
        rewards_orig = data.get("rewards", [])
        for seed, player, rank, team in entries:
            trace = build_trace(data, player)
            # salva trace temporário e carrega agente
            tmp = os.path.join(args.dir, f"_tmp_trace_{ep_id}_p{player}.json")
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(trace, f)
            opp = trace_agent.load_trace_agent(tmp)

            env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": int(seed)})
            env.run([our, opp])
            last = env.steps[-1]
            r0 = last[0]["reward"] if last[0] else None
            r1 = last[1]["reward"] if last[1] else None
            st0 = last[0]["status"] if last[0] else None
            st1 = last[1]["status"] if last[1] else None
            orig = rewards_orig[player] if player < len(rewards_orig) else None
            outcome = "WIN" if (r0 is not None and r1 is not None and r0 > r1) else \
                      "LOSS" if (r0 is not None and r1 is not None and r1 > r0) else "BAD"
            print(f"ep={ep_id} seed={seed} vs #{rank} {team:<16} "
                  f"orig={orig:>8.0f} | nos={r0:>8.0f} op={r1:>8.0f} d={r0-r1 if r0 is not None and r1 is not None else 0:>+9.0f} "
                  f"[{st0}/{st1}] {outcome}", flush=True)
            results.append({
                "episode": ep_id, "seed": seed, "rank": rank, "team": team,
                "orig_reward": orig, "our_reward": r0, "opp_reward": r1,
                "st0": st0, "st1": st1, "outcome": outcome,
            })
            os.remove(tmp)

    wins = sum(1 for r in results if r["outcome"] == "WIN")
    losses = sum(1 for r in results if r["outcome"] == "LOSS")
    bad = sum(1 for r in results if r["outcome"] == "BAD")
    print(f"\n=== RESULT: nosso {wins}-{losses} vs top10 (bad={bad}, n={len(results)}) ===")
    if args.out:
        os.makedirs(os.path.dirname(args.out), exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump({"agent": args.agent, "results": results, "wins": wins, "losses": losses}, f, indent=1, ensure_ascii=False)
        print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
