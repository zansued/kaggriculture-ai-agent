"""Compara nosso agente (P0) com os top 10 nos MESMOS seeds, via starter.

Roda nosso agente vs starter nos seeds dos episódios top10 e gera a curva
dia a dia de money/animais/plantas, lado a lado com o top10 original (do replay).

Uso:
    python compare_top10.py --agent submissions/hybrid_v2/main.py [--out data/top10/compare.md]
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

from kaggle_environments import make  # noqa: E402

EPISODES = {
    "98419962": ("851118847", [(0, 2, "Crop Dusta"), (1, 1, "Ryo Hasegawa")]),
    "98419964": ("1243789113", [(0, 2, "Crop Dusta"), (1, 3, "Subramanya N")]),
    "98426786": ("1638905968", [(0, 5, "Say My Name ?"), (1, 4, "junseok lee")]),
    "98403998": ("647390248", [(0, 6, "Arman Tuganbaev"), (1, 10, "ActiveMusyoku")]),
    "98415386": ("1647964172", [(1, 7, "Yizuki")]),
    "98433623": ("338247171", [(0, 8, "Kaileh57")]),
    "98424471": ("688102744", [(0, 8, "Kaileh57"), (1, 9, "Ueddy")]),
    "98442664": ("22062911", [(0, 10, "ActiveMusyoku")]),
}

ANIMAL_ORDER = ["GOOSE", "COW", "SHEEP"]
CROP_ORDER = ["WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON"]


def load_agent(path: str):
    spec = importlib.util.spec_from_file_location("our_agent", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.agent


def snapshot_day(step, player):
    obs = step.get("observation")
    if not obs:
        return None
    farm = obs["farms"][player]
    animals = {}
    plants = {}
    for row in farm.get("tiles", []):
        for t in row:
            if isinstance(t, dict):
                if t.get("animal"):
                    animals[t["animal"]] = animals.get(t["animal"], 0) + 1
                elif t.get("kind") == "PLANT":
                    c = t.get("crop")
                    plants[c] = plants.get(c, 0) + 1
    return {"money": farm.get("money"), "animals": animals, "plants": plants}


def run_agent(agent, seed):
    env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": seed})
    env.run([agent, "starter"])
    steps = env.steps
    last = steps[-1]
    days = {}
    for st in steps:
        s = snapshot_day(st[0], 0)
        if s is None:
            continue
        day = st[0]["observation"].get("day", 0)
        if day not in days:
            days[day] = s
    return days, last[0]["reward"], last[0]["status"]


def top10_days(path, player):
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    days = {}
    for st in data["steps"]:
        s = snapshot_day(st[player], player)
        if s is None:
            continue
        day = st[player]["observation"].get("day", 0)
        if day not in days:
            days[day] = s
    return days


def fmt_counts(counter, order):
    if not counter:
        return "-"
    return " ".join(f"{k[0]}{counter.get(k, 0)}" for k in order if counter.get(k, 0))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--agent", default="submissions/hybrid_v2/main.py")
    ap.add_argument("--dir", default="data/top10")
    ap.add_argument("--out", default="data/top10/compare.md")
    args = ap.parse_args()

    our = load_agent(args.agent)
    lines = ["# Comparação: nosso agente vs Top 10 (mesmos seeds)", ""]

    for ep_id, (seed, entries) in EPISODES.items():
        replay_path = os.path.join(args.dir, f"episode-{ep_id}-replay.json")
        if not os.path.exists(replay_path):
            continue
        days, reward, status = run_agent(our, int(seed))
        lines.append(f"## Episódio {ep_id} (seed {seed}) — nosso reward={reward} ({status})")
        lines.append("")
        # money por dia: nosso vs cada top10
        for player, rank, team in entries:
            tdays = top10_days(replay_path, player)
            lines.append(f"### Money diário: NÓS vs #{rank} {team} (reward original {tdays.get(29,{}).get('money') if 29 in tdays else '?'})")
            lines.append("| day | nós | {} | Δ |".format(team))
            lines.append("|----:|----:|----:|----:|")
            for d in range(30):
                m0 = days.get(d, {}).get("money")
                m1 = tdays.get(d, {}).get("money")
                if m0 is None and m1 is None:
                    continue
                dlt = ""
                if m0 is not None and m1 is not None:
                    dlt = f"{m0-m1:+,.0f}"
                lines.append(f"| {d} | {m0:,.0f} | {m1:,.0f} | {dlt} |")
            lines.append("")
        # composição final d29
        lines.append("**Composição d29 — NÓS:**")
        s = days.get(29, {})
        lines.append(f"  money={s.get('money'):,.0f}  animais=[{fmt_counts(s.get('animals'), ANIMAL_ORDER)}]  plantas=[{fmt_counts(s.get('plants'), CROP_ORDER)}]")
        lines.append("")

    report = "\n".join(lines)
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"Relatório em {args.out} ({len(report)} bytes)")


if __name__ == "__main__":
    main()
