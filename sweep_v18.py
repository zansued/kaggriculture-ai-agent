"""sweep_v18 — calibração dos parâmetros do glut-guard ADAPTATIVO (v18).

Testa variações de parâmetros do v18 (base dinâmica + momentum + fracionado)
vs v17, para extrair mais performance. Cada config = h2h 24 jogos (2 lados).

Uso: python sweep_v18.py [--configs a,b,c]
"""
from __future__ import annotations

import argparse
import importlib.util
import os
import statistics
import sys

REPO = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, REPO)

spec17 = importlib.util.spec_from_file_location("v17", os.path.join(REPO, "submissions", "hybrid_v17", "main.py"))
mod17 = importlib.util.module_from_spec(spec17)
spec17.loader.exec_module(mod17)

_PREMIUM = ("MILK", "WOOL", "MELON", "STRAWBERRY")
_GBASE = {"WHEAT": 25, "CARROT": 35, "TOMATO": 60, "STRAWBERRY": 120,
          "MELON": 250, "EGG": 50, "MILK": 160, "WOOL": 200, "FERTILIZER": 100}
_GRISERS = ("WHEAT", "CARROT", "TOMATO")
_GDUMP = _PREMIUM
_GRISE_MULT = 1.3
_GHOLD = 0.5
_FLOOR_BASE = {"MILK": 0.45, "WOOL": 0.45, "MELON": 0.40, "STRAWBERRY": 0.40}

_history = {}


def make_agent(cfg):
    window = cfg.get("window", 24)
    mom_thresh = cfg.get("mom_thresh", 0.04)
    floor_shift = cfg.get("floor_shift", 0.12)
    max_lote = cfg.get("max_lote", 16)
    gstart = cfg.get("gstart", 200)
    gstop = cfg.get("gstop", 680)

    def adaptive_glut(action, obs, step):
        if not (gstart <= step < gstop):
            return action
        seat = int((obs or {}).get("index", 0) or 0)
        h = _history.setdefault(seat, {})
        prices = (obs.get("market") or {}).get("prices") or {}
        shed = (obs.get("private") or {}).get("shed") or {}
        for item in _GDUMP:
            p = float(prices.get(item, 0) or 0)
            if p > 0:
                h.setdefault(item, []).append(p)
                if len(h[item]) > window:
                    h[item] = h[item][-window:]
        market = list(action.get("market") or [])
        new_market = []
        for o in market:
            if isinstance(o, list) and len(o) >= 3 and o[0] == "SELL" and o[1] in _GBASE:
                item = o[1]
                qty = int(o[2] or 0)
                if qty <= 0:
                    continue
                price = float(prices.get(item, 0) or 0)
                base = _GBASE[item]
                if item in _GRISERS and price > 0 and price < base * _GRISE_MULT:
                    new_market.append(["SELL", item, max(1, int(qty * _GHOLD))])
                    continue
                if item in _GDUMP:
                    hist = h.get(item, [])
                    if len(hist) < 5:
                        floor = _FLOOR_BASE.get(item, 0.45)
                    else:
                        dyn_base = sum(hist) / len(hist)
                        prev = hist[:max(1, len(hist) - 4)]
                        prev_base = sum(prev) / len(prev)
                        momentum = (price - prev_base) / max(0.01, prev_base)
                        floor = _FLOOR_BASE.get(item, 0.45)
                        if momentum < -mom_thresh:
                            floor = max(0.12, floor - floor_shift)
                        elif momentum > mom_thresh:
                            floor = min(0.75, floor + floor_shift)
                        base = dyn_base
                    if price >= base * floor:
                        avail = int(shed.get(item, 0) or 0)
                        if avail > 0:
                            lote = min(max(qty, avail), max_lote)
                            new_market.append(["SELL", item, lote])
                        else:
                            new_market.append(o)
                    else:
                        new_market.append(["SELL", item, max(1, int(qty * 0.5))])
                    continue
                new_market.append(o)
            else:
                new_market.append(o)
        action["market"] = new_market[:10]
        return action

    def agent(obs, config=None):
        action = mod17.agent(obs, config)
        return adaptive_glut(action, obs, int((obs or {}).get("step", 0) or 0))
    return agent


def run_config(cfg, seeds=range(1, 13)):
    _history.clear()
    agent = make_agent(cfg)
    wins = loss = ties = 0
    margins = []
    for seed in seeds:
        from kaggle_environments import make
        env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": seed})
        env.run([agent, mod17.agent])
        r0 = env.steps[-1][0]["reward"]; r1 = env.steps[-1][1]["reward"]
        if r0 > r1: wins += 1
        elif r1 > r0: loss += 1
        else: ties += 1
        margins.append(r0 - r1)
        env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": seed})
        env.run([mod17.agent, agent])
        r0 = env.steps[-1][0]["reward"]; r1 = env.steps[-1][1]["reward"]
        if r1 > r0: wins += 1
        elif r0 > r1: loss += 1
        else: ties += 1
        margins.append(r1 - r0)
    return wins, loss, ties, statistics.mean(margins)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--configs", default="")
    args = ap.parse_args()

    cfgs = [
        {"name": "v18-atual", "window": 24, "mom_thresh": 0.04, "floor_shift": 0.12, "max_lote": 16},
        {"name": "lote8", "window": 24, "mom_thresh": 0.04, "floor_shift": 0.12, "max_lote": 8},
        {"name": "lote32", "window": 24, "mom_thresh": 0.04, "floor_shift": 0.12, "max_lote": 32},
        {"name": "janela48", "window": 48, "mom_thresh": 0.04, "floor_shift": 0.12, "max_lote": 16},
        {"name": "mom02", "window": 24, "mom_thresh": 0.02, "floor_shift": 0.12, "max_lote": 16},
    ]
    if args.configs:
        names = args.configs.split(",")
        cfgs = [c for c in cfgs if c["name"] in names]

    for cfg in cfgs:
        name = cfg.pop("name")
        w, l, t, md = run_config(cfg)
        print(f"{name}: {w}-{l} (ties={t}) mean_d={md:+.0f}  [{cfg}]")
        _history.clear()


if __name__ == "__main__":
    main()
