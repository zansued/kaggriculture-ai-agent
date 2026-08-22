"""hybrid_v2: híbrido Moon+mix + overlay de timing adaptativo à saturação.

Base: submissions/hybrid_single/main.py (Moon V56 + mature_opp_front_run +
sell_first). Overlay novo (_glut_guard): ajusta QUANTIDADES vendidas ao ciclo
de preço observado no mercado, capturando dois padrões documentados:
  - LATE_RISERS (WHEAT/CARROT/TOMATO): preço sobe no final (29->47, 35->279,
    60->409). Quando o preço corrente ainda está baixo, SEGURA parte da venda
    para liquidar no terminal (step>=708, que vende ao preço de pico).
  - EARLY_DUMP (MILK/WOOL/MELON/STRAWBERRY): preço colapsa (175->7, 212->5,
    melon pós-d10). Quando o preço ainda está acima de um piso, ANTECIPA o
    dump do shed, antes do crash.

Uso: python h2h_bench.py hybrid_v2.py research/public/moon_agent_main.py --seeds 1-8
"""
from __future__ import annotations

import importlib.util
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))

_spec = importlib.util.spec_from_file_location("h1", os.path.join(_HERE, "submissions", "hybrid_single", "main.py"))
_h1 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_h1)

# Preço base de cada item (do MARKET_PARAMS do Moon).
_BASE_PRICE = {
    "WHEAT": 25, "CARROT": 35, "TOMATO": 60, "STRAWBERRY": 120,
    "MELON": 250, "EGG": 50, "MILK": 160, "WOOL": 200, "FERTILIZER": 100,
}

# Itens cujo preço SOBE no final do jogo: segurar compensa.
_LATE_RISERS = ("WHEAT", "CARROT", "TOMATO")
_LATE_HOLD_RATIO = 0.5          # segura 50% da venda planejada
_LATE_RISE_MULT = 1.3           # segura enquanto preço < base*1.3
# Itens cujo preço COLAPSA: antecipar a venda enquanto ainda vale.
_EARLY_DUMP = ("MILK", "WOOL", "MELON", "STRAWBERRY")
_DUMP_FLOOR_MULT = 0.55         # dump enquanto preço >= base*0.55
# Não mexer antes do jogo esquentar (d<~8) nem no terminal do Moon.
_GUARD_START = 200
_GUARD_STOP = 700

_ENABLED = os.environ.get("HYBRID_V2_GUARD", "1") == "1"


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
                # Segura metade para o terminal (vende ao preço de pico).
                keep = max(1, int(qty * _LATE_HOLD_RATIO))
                new_market.append(["SELL", item, keep])
            elif item in _EARLY_DUMP and price >= base * _DUMP_FLOOR_MULT:
                # Antecipa: despeja tudo do shed agora, antes do crash.
                avail = int(shed.get(item, 0) or 0)
                if avail > 0:
                    new_market.append(["SELL", item, max(qty, avail)])
                # se não há shed, mantém a ordem original
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
