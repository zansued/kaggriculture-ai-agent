"""hybrid_v4: candidato de melhoria do glut_guard.

Mudanças vs hybrid_v2 (validadas em h2h 36 seeds vs v2: 17W-9L):
  - _DUMP_FLOOR_MULT: 0.55 -> 0.40   (despejar colapsantes MILK/WOOL/MELON/
    STRAWBERRY MAIS TARDE — segura enquanto preço >= base*0.40)
  - _GUARD_START/_GUARD_STOP: 200-700 -> 250-650  (janela mais estreita)

Base: submissions/hybrid_single/main.py (Moon V56 + mature_opp_front_run +
sell_first). Mesmo overlay do v2, com os dois parâmetros recalibrados.

Uso: python h2h_bench.py hybrid_v4.py hybrid_v2.py --seeds 1-36
     python h2h_bench.py hybrid_v2.py hybrid_v4.py --seeds 1-36   # espelho
"""
from __future__ import annotations

import importlib.util
import os

_HERE = os.path.dirname(os.path.abspath(__file__))

_spec = importlib.util.spec_from_file_location("h1", os.path.join(_HERE, "submissions", "hybrid_single", "main.py"))
_h1 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_h1)

_BASE_PRICE = {
    "WHEAT": 25, "CARROT": 35, "TOMATO": 60, "STRAWBERRY": 120,
    "MELON": 250, "EGG": 50, "MILK": 160, "WOOL": 200, "FERTILIZER": 100,
}

_LATE_RISERS = ("WHEAT", "CARROT", "TOMATO")
_LATE_HOLD_RATIO = 0.5
_LATE_RISE_MULT = 1.3
_EARLY_DUMP = ("MILK", "WOOL", "MELON", "STRAWBERRY")
_DUMP_FLOOR_MULT = 0.40            # v2 era 0.55
_GUARD_START = 250                 # v2 era 200
_GUARD_STOP = 650                  # v2 era 700

_ENABLED = os.environ.get("HYBRID_V3_GUARD", "1") == "1"


def _glut_guard(action, obs, step):
    if not _ENABLED or not (_GUARD_START <= step < _GUARD_STOP):
        return action
    market = list(action.get("market") or [])
    if not market:
        return action
    prices = ((obs.get("market") or {}).get("prices") or {})
    shed = ((obs.get("private") or {}).get("shed") or {})
    new_market = []
    for o in market:
        if isinstance(o, list) and len(o) >= 3 and o[0] == "SELL" and o[1] in _BASE_PRICE:
            item = o[1]
            qty = int(o[2] or 0)
            if qty <= 0:
                continue
            price = float(prices.get(item, 0) or 0)
            base = _BASE_PRICE[item]
            if item in _LATE_RISERS and price > 0 and price < base * _LATE_RISE_MULT:
                keep = max(1, int(qty * _LATE_HOLD_RATIO))
                new_market.append(["SELL", item, keep])
            elif item in _EARLY_DUMP and price >= base * _DUMP_FLOOR_MULT:
                avail = int(shed.get(item, 0) or 0)
                if avail > 0:
                    new_market.append(["SELL", item, max(qty, avail)])
                else:
                    new_market.append(o)
            else:
                new_market.append(o)
        else:
            new_market.append(o)
    action["market"] = new_market[:10]
    return action


def agent(obs, config=None):
    step = int(obs.get("step", 0) or 0)
    action = _h1.agent(obs, config)
    action = _glut_guard(action, obs, step)
    return action


if __name__ == "__main__":
    from kaggle_environments import make
    for s in (1, 2):
        env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": s})
        env.run([agent, "starter"])
        print(f"seed {s} vs starter:", env.steps[-1][0]["reward"])
