"""sweep_v18_refinado — refina o glut-guard adaptativo com parâmetros POR ITEM.

O v18 usa parâmetros uniformes (janela 24, floor_shift 0.12, lote 16) para todos
os itens premium. Mas cada produto tem dinâmica de preço diferente:
  - MELON: crasha d10 (T=300, acima sq) -> reagir rápido, janela curta.
  - MILK: pico curto d12-14 (T=122) -> janela curta, floor mais alto.
  - WOOL: recupera no fim (T=105) -> janela longa, segurar p/ recuperar.
  - STRAWBERRY: declínio d13-24 -> janela média.

Testa configurações por item vs v18.

Uso: python sweep_v18_refinado.py [--cfg nome]
"""
from __future__ import annotations

import importlib.util
import os
import statistics
import sys

REPO = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, REPO)

spec18 = importlib.util.spec_from_file_location("v18", os.path.join(REPO, "submissions", "hybrid_v18", "main.py"))
mod18 = importlib.util.module_from_spec(spec18)
spec18.loader.exec_module(mod18)

_PREMIUM = ("MILK", "WOOL", "MELON", "STRAWBERRY")
_GBASE = {"WHEAT": 25, "CARROT": 35, "TOMATO": 60, "STRAWBERRY": 120,
          "MELON": 250, "EGG": 50, "MILK": 160, "WOOL": 200, "FERTILIZER": 100}
_GRISERS = ("WHEAT", "CARROT", "TOMATO")
_GRISE_MULT = 1.3
_GHOLD = 0.5

# Defaults por item (v18 atual: uniforme)
DEFAULT_CFG = {
    "MILK": {"floor": 0.45, "shift": 0.12, "window": 24, "lote": 16, "mom": 0.04},
    "WOOL": {"floor": 0.45, "shift": 0.12, "window": 24, "lote": 16, "mom": 0.04},
    "MELON": {"floor": 0.40, "shift": 0.12, "window": 24, "lote": 16, "mom": 0.04},
    "STRAWBERRY": {"floor": 0.40, "shift": 0.12, "window": 24, "lote": 16, "mom": 0.04},
}

# Configuração refinada: parâmetros por item (janela curta p/ crash, longa p/ recuperação)
REFINADO = {
    "MILK": {"floor": 0.42, "shift": 0.10, "window": 16, "lote": 16, "mom": 0.05},   # pico curto d12-14
    "WOOL": {"floor": 0.50, "shift": 0.15, "window": 36, "lote": 12, "mom": 0.03},   # recupera no fim
    "MELON": {"floor": 0.35, "shift": 0.16, "window": 12, "lote": 12, "mom": 0.06},  # crasha d10
    "STRAWBERRY": {"floor": 0.38, "shift": 0.10, "window": 20, "lote": 16, "mom": 0.04},
}

# Alternativa: reagir mais ao momentum (agressivo)
AGGRESSIVO = {
    "MILK": {"floor": 0.40, "shift": 0.14, "window": 12, "lote": 16, "mom": 0.04},
    "WOOL": {"floor": 0.45, "shift": 0.18, "window": 30, "lote": 12, "mom": 0.02},
    "MELON": {"floor": 0.30, "shift": 0.20, "window": 10, "lote": 12, "mom": 0.05},
    "STRAWBERRY": {"floor": 0.35, "shift": 0.14, "window": 16, "lote": 16, "mom": 0.03},
}

_history = {}


def make_agent(item_cfg, gstart=200, gstop=680):
    def adaptive_glut(action, obs, step):
        if not (gstart <= step < gstop):
            return action
        seat = int((obs or {}).get("index", 0) or 0)
        h = _history.setdefault(seat, {})
        prices = (obs.get("market") or {}).get("prices") or {}
        shed = (obs.get("private") or {}).get("shed") or {}
        for item, c in item_cfg.items():
            p = float(prices.get(item, 0) or 0)
            if p > 0:
                h.setdefault(item, []).append(p)
                if len(h[item]) > c["window"]:
                    h[item] = h[item][-c["window"]:]
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
                if item in item_cfg:
                    c = item_cfg[item]
                    hist = h.get(item, [])
                    if len(hist) < 5:
                        floor = c["floor"]
                    else:
                        dyn_base = sum(hist) / len(hist)
                        prev = hist[:max(1, len(hist) - 4)]
                        prev_base = sum(prev) / len(prev)
                        momentum = (price - prev_base) / max(0.01, prev_base)
                        floor = c["floor"]
                        if momentum < -c["mom"]:
                            floor = max(0.12, floor - c["shift"])
                        elif momentum > c["mom"]:
                            floor = min(0.75, floor + c["shift"])
                        base = dyn_base
                    if price >= base * floor:
                        avail = int(shed.get(item, 0) or 0)
                        if avail > 0:
                            lote = min(max(qty, avail), c["lote"])
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
        action = mod18.agent(obs, config)
        return adaptive_glut(action, obs, int((obs or {}).get("step", 0) or 0))
    return agent


def run_cfg(name, item_cfg, seeds=range(1, 13)):
    _history.clear()
    agent = make_agent(item_cfg)
    from kaggle_environments import make
    wins = loss = ties = 0
    margins = []
    for seed in seeds:
        env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": seed})
        env.run([agent, mod18.agent])
        r0 = env.steps[-1][0]["reward"]; r1 = env.steps[-1][1]["reward"]
        if r0 > r1: wins += 1
        elif r1 > r0: loss += 1
        else: ties += 1
        margins.append(r0 - r1)
        env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": seed})
        env.run([mod18.agent, agent])
        r0 = env.steps[-1][0]["reward"]; r1 = env.steps[-1][1]["reward"]
        if r1 > r0: wins += 1
        elif r0 > r1: loss += 1
        else: ties += 1
        margins.append(r1 - r0)
    print(f"{name}: {wins}-{loss} (ties={ties}) mean_d={statistics.mean(margins):+.0f}")
    return wins, loss


if __name__ == "__main__":
    print("=== Refinamento do glut-guard adaptativo (por item) vs v18 ===")
    run_cfg("REFINADO", REFINADO)
    _history.clear()
    run_cfg("AGGRESSIVO", AGGRESSIVO)
