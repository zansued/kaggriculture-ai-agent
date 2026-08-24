"""Analisa os replays dos top 10 do Kaggriculture e gera relatório dia a dia.

Uso:
    python analyze_top10.py [--out data/top10/report.md]

Para cada episódio/player-alvo extrai:
  * trajetória dia a dia (money, quads, hands, animais, plantas, shed, seeds)
  * ações de mercado agregadas por dia (compras/vendas)
  * eventos de construção
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import defaultdict, Counter

sys.stdout.reconfigure(encoding="utf-8")

# Mapeamento: episódio -> {player_index: (rank, team_name)}
# Definido a partir das URLs manuais do Gui + metadados dos replays.
TARGETS = {
    "98419962": {0: (2, "Crop Dusta"), 1: (1, "Ryo Hasegawa")},
    "98419964": {0: (2, "Crop Dusta"), 1: (3, "Subramanya N")},
    "98426786": {0: (5, "Say My Name ?"), 1: (4, "junseok lee")},
    "98403998": {0: (6, "Arman Tuganbaev"), 1: (10, "ActiveMusyoku")},
    "98415386": {0: (11, "Izzoudine Mohamed KANTA"), 1: (7, "Yizuki")},
    "98433623": {0: (8, "Kaileh57"), 1: (11, "Izzoudine Mohamed KANTA")},
    "98424471": {0: (8, "Kaileh57"), 1: (9, "Ueddy")},
    "98442664": {0: (10, "ActiveMusyoku"), 1: (17, "Chiranjieev")},
}

ANIMALS = {"GOOSE", "COW", "SHEEP"}
CROPS = {"WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON"}

# Ordem compacta para exibição
ANIMAL_ORDER = ["GOOSE", "COW", "SHEEP"]
CROP_ORDER = ["WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON"]
PROD_ORDER = ["WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON", "EGG", "MILK", "WOOL", "FERTILIZER"]


def parse_tile(t):
    """Retorna (tipo, nome) para um tile."""
    if t is None:
        return None
    if isinstance(t, str):
        return ("state", t)
    if isinstance(t, dict):
        if t.get("animal"):
            return ("animal", t["animal"])
        if t.get("kind") == "PLANT":
            return ("plant", t.get("crop"))
        if t.get("kind"):
            return ("kind", t.get("kind"))
        return ("?", str(t)[:20])
    return ("?", str(t)[:20])


def first_of_day_snapshot(step, player):
    """Snapshot no primeiro step do dia (usando obs do step)."""
    obs = step.get("observation")
    if not obs:
        return None
    farm = obs["farms"][player]
    priv = obs.get("private", {})
    shed = {k: v for k, v in priv.get("shed", {}).items() if v}
    seeds = {k: v for k, v in priv.get("seeds", {}).items() if v}
    animals = Counter()
    plants = Counter()
    for row in farm.get("tiles", []):
        for t in row:
            p = parse_tile(t)
            if p is None:
                continue
            kind, name = p
            if kind == "animal":
                animals[name] += 1
            elif kind == "plant":
                plants[name] += 1
    return {
        "money": farm.get("money"),
        "quads": sorted(farm.get("unlocked_quadrants") or []),
        "hands": len(farm.get("hands") or []),
        "hires_today": farm.get("hires_today", 0),
        "animals": dict(animals),
        "plants": dict(plants),
        "shed": shed,
        "seeds": seeds,
    }


def fmt_counts(counter, order):
    if not counter:
        return "-"
    return " ".join(f"{k[0]}{counter.get(k, 0)}" for k in order if counter.get(k, 0))


def analyze_episode(ep_id, path):
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    info = data.get("info", {})
    seed = info.get("seed")
    rewards = data.get("rewards", [])
    results = {}
    for player, (rank, team) in TARGETS.get(ep_id, {}).items():
        days = {}
        market_actions = defaultdict(Counter)  # day -> Counter of action labels
        builds = Counter()
        for i, step in enumerate(data["steps"]):
            st = step[player]
            obs = st.get("observation")
            if not obs:
                continue
            day = obs.get("day", 0)
            # primeiro step do dia
            if day not in days:
                days[day] = first_of_day_snapshot(st, player)
            # ações de mercado
            act = st.get("action") or {}
            for order in act.get("market", []):
                if not isinstance(order, list) or not order:
                    continue
                op = order[0]
                if op in ("BUY_SEED", "BUY_ANIMAL"):
                    label = f"{op}:{order[1]}"
                    market_actions[day][label] += int(order[2]) if len(order) > 2 else 1
                elif op in ("SELL", "BUY"):
                    label = f"{op}:{order[1]}"
                    market_actions[day][label] += int(order[2]) if len(order) > 2 else 1
                elif op == "HIRE":
                    market_actions[day]["HIRE"] += 1
                elif op == "FERTILIZE":
                    market_actions[day]["FERTILIZE"] += 1
                elif op == "CLEAR":
                    market_actions[day]["CLEAR"] += 1
                else:
                    market_actions[day][op] += 1
            for b in act.get("farmer", []):
                builds[b] += 1
        results[player] = {
            "rank": rank,
            "team": team,
            "seed": seed,
            "reward": rewards[player] if player < len(rewards) else None,
            "days": days,
            "market": market_actions,
            "builds": builds,
            "last_day": max(days.keys()) if days else None,
            "final": days.get(max(days.keys())),
        }
    return results


def render(results, ep_id):
    lines = []
    for player in sorted(results.keys()):
        r = results[player]
        lines.append("")
        lines.append(f"### #{r['rank']} {r['team']}  (ep={ep_id} player={player} seed={r['seed']} reward={r['reward']})")
        lines.append("")
        lines.append("| day | money | quads | hands | hires | animals | plants | shed | seeds |")
        lines.append("|----:|------:|-------|------:|------:|---------|--------|------|-------|")
        for d in sorted(r["days"].keys()):
            s = r["days"][d]
            lines.append(
                "| {} | {:.0f} | {} | {} | {} | {} | {} | {} | {} |".format(
                    d,
                    s["money"] or 0,
                    "".join(str(q) for q in s["quads"]) or "-",
                    s["hands"],
                    s["hires_today"],
                    fmt_counts(s["animals"], ANIMAL_ORDER),
                    fmt_counts(s["plants"], CROP_ORDER),
                    fmt_counts(s["shed"], PROD_ORDER),
                    fmt_counts(s["seeds"], CROP_ORDER),
                )
            )
        lines.append("")
        lines.append("**Ações de mercado por dia:**")
        for d in sorted(r["market"].keys()):
            c = r["market"][d]
            if c:
                parts = ", ".join(f"{k}x{v}" for k, v in sorted(c.items()))
                lines.append(f"  d{d}: {parts}")
        lines.append("")
        lines.append(f"**Builds:** {dict(r['builds']) if r['builds'] else '-'}")
        lines.append("")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default="data/top10")
    ap.add_argument("--out", default="data/top10/report.md")
    args = ap.parse_args()

    all_lines = ["# Kaggriculture — Análise Top 10 (replays)", ""]
    for ep_id in sorted(TARGETS.keys()):
        path = os.path.join(args.dir, f"episode-{ep_id}-replay.json")
        if not os.path.exists(path):
            print(f"AVISO: replay {ep_id} não encontrado, pulando", file=sys.stderr)
            continue
        results = analyze_episode(ep_id, path)
        all_lines.append(f"## Episódio {ep_id}")
        all_lines.append(render(results, ep_id))
        all_lines.append("")

    report = "\n".join(all_lines)
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"Relatório escrito em {args.out} ({len(report)} bytes)")


if __name__ == "__main__":
    main()
