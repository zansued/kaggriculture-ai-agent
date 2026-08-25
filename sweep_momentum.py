"""Sweep do glut-guard com MOMENTUM: detecta preço subindo/descendo e adapta.

Hipótese: o glut-guard do v5 usa dump_floor FIXO por item (preço absoluto).
Mas a TENDÊNCIA do preço importa: se o preço está CAINDO rápido (saturação
iminente), vender AGORA mesmo acima do floor; se está SUBINDO, segurar.

Configs testadas (vs hybrid_v5):
  - v5 baseline (floor fixo)
  - momentum 5% (caiu >5% no step → vende tudo; subiu >5% → segura)
  - momentum 3%
  - momentum 10%
  - momentum + floor (combina ambos: floor fixo OU queda >thresh)

Uso: python sweep_momentum.py --seeds 1-16
"""
from __future__ import annotations

import argparse
import importlib.util
import os
import statistics
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

import sweep_glut as sg  # reutiliza _make_agent, run_h2h, parse_seeds


def make_momentum_agent(thresh: float, use_floor: bool = True):
    """Cria agente com glut-guard momentum sobre a base hybrid_single."""
    base = dict(sg._BASE_PRICE)
    floors = {"MILK": 0.45, "WOOL": 0.45, "MELON": 0.40, "STRAWBERRY": 0.40}
    gstart, gstop = 250, 650
    state = {"prev": {}}

    def guard(action, obs, step):
        if not (gstart <= step < gstop):
            return action
        market = list(action.get("market") or [])
        if not market:
            return action
        prices = ((obs.get("market") or {}).get("prices") or {})
        shed = ((obs.get("private") or {}).get("shed") or {})
        prev = state["prev"]
        new_market = []
        for o in market:
            if isinstance(o, list) and len(o) >= 3 and o[0] == "SELL" and o[1] in base:
                item, qty = o[1], int(o[2] or 0)
                if qty <= 0:
                    continue
                price = float(prices.get(item, 0) or 0)
                prev_price = prev.get(item)
                avail = int(shed.get(item, 0) or 0)
                # momentum: queda > thresh → vender tudo
                falling = prev_price is not None and prev_price > 0 and price < prev_price * (1 - thresh)
                rising = prev_price is not None and prev_price > 0 and price > prev_price * (1 + thresh)
                if falling:
                    if avail > 0:
                        new_market.append(["SELL", item, max(qty, avail)])
                    else:
                        new_market.append(o)
                elif rising and not use_floor:
                    # subindo e sem floor → segura (não vende)
                    continue
                elif item in floors and price >= base[item] * floors[item]:
                    if avail > 0:
                        new_market.append(["SELL", item, max(qty, avail)])
                    else:
                        new_market.append(o)
                else:
                    new_market.append(o)
            else:
                new_market.append(o)
        state["prev"] = dict(prices)
        action["market"] = new_market[:10]
        return action

    def agent(obs, config=None):
        step = int(obs.get("step", 0) or 0)
        action = sg._h1.agent(obs, config)
        return guard(action, obs, step)

    return agent


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", default="1-16")
    ap.add_argument("--opp", default="submissions/hybrid_v5/main.py")
    args = ap.parse_args()
    seeds = sg.parse_seeds(args.seeds)

    ospec = importlib.util.spec_from_file_location("h5", args.opp)
    opp = importlib.util.module_from_spec(ospec)
    ospec.loader.exec_module(opp)

    configs = [
        ("momentum 5% (com floor v5)", make_momentum_agent(0.05, use_floor=True)),
        ("momentum 3% (com floor v5)", make_momentum_agent(0.03, use_floor=True)),
        ("momentum 10% (com floor v5)", make_momentum_agent(0.10, use_floor=True)),
        ("momentum 5% (sem floor)", make_momentum_agent(0.05, use_floor=False)),
    ]
    print(f"=== SWEEP MOMENTUM vs {args.opp}, seeds={seeds} ===", flush=True)
    for label, cand in configs:
        w, l, t, margins = sg.run_h2h(cand, opp.agent, seeds)
        md = statistics.mean(margins) if margins else 0
        print(f"{w:>2}-{l:<2} (t={t}) mean d={md:+.0f} | {label}", flush=True)


if __name__ == "__main__":
    main()
