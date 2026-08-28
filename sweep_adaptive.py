"""sweep_adaptive — overlay ADAPTATIVO de preço no glut-guard (vs v17).

Baseado em docs/TOPS_ADAPTIVE_27AGO.md: os tops REAGEM ao preço real da partida
(base dinâmica + momentum), não a thresholds fixos.

Overlay: pós-processa a action do v17, ajustando ordens SELL de itens premium
(MILK/WOOL/MELON/STRAWB) com base em:
  - dyn_base[item] = média dos últimos N preços (janela ~0.5-1 dia).
  - momentum = (preço atual - média anterior) / média anterior.
  - Se momentum NEGATIVO (preço caindo): vender mais (capturar antes do crash).
  - Se momentum POSITIVO (preço subindo): segurar mais (esperar o pico).

Uso: python sweep_adaptive.py [seeds] [--p1 base|adaptive]
"""
from __future__ import annotations

import argparse
import importlib.util
import os
import statistics

REPO = os.path.dirname(os.path.abspath(__file__))

# carrega v17
spec = importlib.util.spec_from_file_location("v17", os.path.join(REPO, "submissions", "hybrid_v17", "main.py"))
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

# itens premium (glut-guard dumpa estes)
_PREMIUM = ("MILK", "WOOL", "MELON", "STRAWBERRY")
_BASE = {"WHEAT": 25, "CARROT": 35, "TOMATO": 60, "STRAWBERRY": 120,
         "MELON": 250, "EGG": 50, "MILK": 160, "WOOL": 200, "FERTILIZER": 100}

# estado do histórico (por seat)
_history = {}
_def_floor = {"MILK": 0.45, "WOOL": 0.45, "MELON": 0.40, "STRAWBERRY": 0.40}


def _hist(seat):
    return _history.setdefault(seat, {})


def adaptive_glut(action, obs, step, cfg):
    """Pós-processa ordens SELL premium com base dinâmica + momentum."""
    seat = int((obs or {}).get("index", 0) or 0)
    h = _hist(seat)
    prices = (obs.get("market") or {}).get("prices") or {}
    window = cfg.get("window", 24)          # 24 steps = 1 dia
    mom_thresh = cfg.get("mom_thresh", 0.02)  # momentum mínimo p/ reagir
    floor_shift = cfg.get("floor_shift", 0.08)  # quanto o floor muda com momentum

    # atualiza histórico
    for item, p in prices.items():
        if item not in _PREMIUM:
            continue
        h.setdefault(item, []).append(float(p or 0))
        if len(h[item]) > window:
            h[item] = h[item][-window:]

    market = list(action.get("market") or [])
    shed = ((obs.get("private") or {}).get("shed") or {})
    new_market = []
    for o in market:
        if isinstance(o, list) and len(o) >= 3 and o[0] == "SELL" and o[1] in _PREMIUM:
            item = o[1]
            qty = int(o[2] or 0)
            if qty <= 0:
                continue
            price = float(prices.get(item, 0) or 0)
            hist = h.get(item, [])
            if len(hist) < 4:
                new_market.append(o)
                continue
            dyn_base = statistics.mean(hist)
            prev_base = statistics.mean(hist[:-max(1, len(hist) // 4)])
            momentum = (price - prev_base) / max(0.01, prev_base)
            # floor adaptativo: momentum negativo => floor mais baixo (vender cedo)
            floor = _def_floor.get(item, 0.45)
            if momentum < -mom_thresh:
                floor = max(0.15, floor - floor_shift)   # vender antes do crash
            elif momentum > mom_thresh:
                floor = min(0.70, floor + floor_shift)   # segurar, esperar pico
            if price >= dyn_base * floor:
                avail = int(shed.get(item, 0) or 0)
                if avail > 0:
                    new_market.append(["SELL", item, max(qty, avail)])
                else:
                    new_market.append(o)
            else:
                keep = max(1, int(qty * 0.5))
                new_market.append(["SELL", item, keep])
        else:
            new_market.append(o)
    action["market"] = new_market[:10]
    return action


def make_agent(cfg):
    def agent(obs, config=None):
        action = mod.agent(obs, config)
        return adaptive_glut(action, obs, int((obs or {}).get("step", 0) or 0), cfg)
    return agent


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("seeds", default="1-12")
    ap.add_argument("--p1", default="base", help="base|adaptive")
    ap.add_argument("--window", type=int, default=24)
    ap.add_argument("--mom_thresh", type=float, default=0.02)
    ap.add_argument("--floor_shift", type=float, default=0.08)
    args = ap.parse_args()

    if "-" in args.seeds:
        a, b = args.seeds.split("-")
        seeds = list(range(int(a), int(b) + 1))
    else:
        seeds = [int(x) for x in args.seeds.split(",")]

    cfg = {"window": args.window, "mom_thresh": args.mom_thresh, "floor_shift": args.floor_shift}
    agent_a = make_agent(cfg)
    agent_b = mod.agent if args.p1 == "base" else make_agent(cfg)

    from kaggle_environments import make
    wins = loss = ties = 0
    margins = []
    for seed in seeds:
        env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": seed})
        env.run([agent_a, agent_b])
        last = env.steps[-1]
        r0 = last[0]["reward"] if last[0] else None
        r1 = last[1]["reward"] if last[1] else None
        if r0 is None or r1 is None:
            continue
        if r0 > r1: wins += 1
        elif r1 > r0: loss += 1
        else: ties += 1
        margins.append(r0 - r1)
        print(f"[seed {seed:>2}] A={r0:>7.0f} B={r1:>7.0f} d={r0-r1:>+8.0f} {'A' if r0>r1 else 'B' if r1>r0 else 'T'}")
    print(f"\n=== adaptive vs {args.p1}: {wins}-{loss} ties={ties} n={len(margins)} mean_d={statistics.mean(margins):+.0f}")


if __name__ == "__main__":
    main()
