"""Build do bundle HÍBRIDO V21 = v17 + experimento B (overlays de market).

Base: mesmo blob Moon V56 + overlays do mix + glut-guard do hybrid_v17.
Experimento B (camada adaptativa reativa — overlays de TIMING de mercado, sem
mexer em produção/mão-de-obra):

  1. _wheat_mid_sell — vender WHEAT excedente em lote quando o preço está alto
     (>= base*1.35) e o shed tem mais que a reserva de FEED (>=40). O Moon vende
     wheat em lotes de 1-11; os tops (CropDusta) vendem 222-244/dia em lotes
     grandes nos dias 11-14 (preço ~1.44-1.6x base). Consolida a venda para
     capturar melhor preço e reduzir número de ordens de wheat.

  2. _fert_gate — suprimir vendas de FERTILIZER quando o preço está baixo
     (< base*0.5), liberando slots de market para itens premium. (Observação:
     o v6 spama 5.870 ordens de FERT barato; o Moon vende 225x — o gate limita
     o desperdício de slots em preço baixo.)

Motivação (evidência da fita 8c6s): o Moon já vende wheat ao longo do jogo
(159x) e FERT 225x; o gap vs tops está no VOLUME de wheat produzido e na
eficiência de ordens. Estes overlays são de classe de timing (como glut_guard/
feed_guard), que historicamente funcionou, e NÃO adicionam produção.

Usage: python build_hybrid_v21.py  ->  submissions/hybrid_v21/main.py
"""
from __future__ import annotations

import base64
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "submissions" / "hybrid_v21" / "main.py"

# Copia o prelúdio do v17 (overlays validados do mix + glut-guard)
_MIX_OVERPRELUDE = '''\
# ---------------------------------------------------------------------------
# Overlays do mix_agent (validados) — injetados sobre a base Moon.
# _mature_opp_front_run (vende quando produção do oponente está madura) e
# _sell_first (order-slot: premium sells antes, piorando o preço do oponente).
# ---------------------------------------------------------------------------
_OPP_THRESH = {"STRAWBERRY": 4, "MELON": 2, "MILK": 4, "WOOL": 3}
_OPP_MAX_DAY = {"STRAWBERRY": 10, "MELON": 12}
_FRONT_FIRST_ITEMS = ("MELON", "STRAWBERRY", "MILK", "WOOL")


def _mature_opp_front_run(action, obs, step):
    farms = obs.get("farms", [])
    if len(farms) < 2:
        return
    tiles = farms[1].get("tiles", []) or []
    day = int(obs.get("day", 0) or 0)
    prod = {"STRAWBERRY": 0, "MELON": 0, "MILK": 0, "WOOL": 0}
    for row in tiles:
        for t in row:
            if not isinstance(t, dict):
                continue
            if t.get("kind") == "PLANT":
                c = t.get("crop")
                if c in ("STRAWBERRY", "MELON"):
                    age = day - int(t.get("planted_day", day))
                    if age >= _OPP_MAX_DAY[c] - 2 and int(t.get("yield_units", 0) or 0) > 0:
                        prod[c] += 1
            elif t.get("animal"):
                p = {"COW": "MILK", "SHEEP": "WOOL"}.get(t["animal"])
                if p and int(t.get("yield_units", 0) or 0) > 0:
                    prod[p] += 1
    orders = list(action.get("market", []) or [])
    if len(orders) >= 10:
        return
    already = set()
    for o in orders:
        if isinstance(o, list) and len(o) >= 2 and o[0] == "SELL":
            already.add(o[1])
    shed = (obs.get("private") or {}).get("shed") or {}
    for item, thresh in _OPP_THRESH.items():
        if prod.get(item, 0) >= thresh and item not in already and int(shed.get(item, 0) or 0) > 0 and len(orders) < 10:
            orders.append(["SELL", item, int(shed.get(item, 0) or 0)])
            already.add(item)
    action["market"] = orders[:10]


def _sell_first(action, obs, step):
    market = list(action.get("market", []) or [])
    sells = []
    others = []
    for o in market:
        if isinstance(o, list) and len(o) >= 3 and o[0] == "SELL":
            sells.append(o)
        else:
            others.append(o)
    sells.sort(key=lambda o: (o[1] not in _FRONT_FIRST_ITEMS, -(o[2] or 0)))
    action["market"] = (sells + others)[:10]
    return action


# ---------------------------------------------------------------------------
# V5: _glut_guard — timing de venda adaptativo à saturação do mercado.
# dump_floor POR ITEM: MILK/WOOL 0.45, MELON/STRAWBERRY 0.40. Janela 250-650.
# ---------------------------------------------------------------------------
_GBASE = {"WHEAT": 25, "CARROT": 35, "TOMATO": 60, "STRAWBERRY": 120,
          "MELON": 250, "EGG": 50, "MILK": 160, "WOOL": 200, "FERTILIZER": 100}
_GRISERS = ("WHEAT", "CARROT", "TOMATO")
_GHOLD = 0.5
_GRISE_MULT = 1.3
_GDUMP = ("MILK", "WOOL", "MELON", "STRAWBERRY")
_GD_FLOOR = {"MILK": 0.45, "WOOL": 0.45, "MELON": 0.40, "STRAWBERRY": 0.40}
_GSTART = 250
_GSTOP = 650


def _floor_of(item):
    return _GD_FLOOR.get(item, 0.45) if isinstance(_GD_FLOOR, dict) else _GD_FLOOR


def _glut_guard(action, obs, step):
    if not (_GSTART <= step < _GSTOP):
        return action
    market = list(action.get("market", []) or [])
    if not market:
        return action
    prices = ((obs.get("market") or {}).get("prices") or {})
    shed = ((obs.get("private") or {}).get("shed") or {})
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
                keep = max(1, int(qty * _GHOLD))
                new_market.append(["SELL", item, keep])
            elif item in _GDUMP and price >= base * _floor_of(item):
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


# ---------------------------------------------------------------------------
# EXPERIMENTO B — overlays de market (timing, sem produção).
# ---------------------------------------------------------------------------
# _wheat_mid_sell: vende WHEAT excedente (acima da reserva de FEED) em lote
# quando o preço está >= base*1.35, na janela d5-d25 (steps 120-600).
_WHEAT_RESERVE = 40
_WHEAT_MIN_MULT = 1.35
_WHEAT_WINDOW = (120, 600)


def _wheat_mid_sell(action, obs, step):
    lo, hi = _WHEAT_WINDOW
    if not (lo <= step < hi):
        return action
    prices = ((obs.get("market") or {}).get("prices") or {})
    price = float(prices.get("WHEAT", 0) or 0)
    if price <= 0 or price < _GBASE["WHEAT"] * _WHEAT_MIN_MULT:
        return action
    shed = ((obs.get("private") or {}).get("shed") or {})
    avail = int(shed.get("WHEAT", 0) or 0)
    if avail <= _WHEAT_RESERVE:
        return action
    market = list(action.get("market") or [])
    for o in market:
        if isinstance(o, list) and len(o) >= 2 and o[0] == "SELL" and o[1] == "WHEAT":
            return action
    qty = avail - _WHEAT_RESERVE
    if len(market) >= 10:
        # Substitui uma venda de FERTILIZER (ordem de menor valor) por WHEAT.
        for i, o in enumerate(market):
            if isinstance(o, list) and len(o) >= 3 and o[0] == "SELL" and o[1] == "FERTILIZER":
                market[i] = ["SELL", "WHEAT", qty]
                action["market"] = market[:10]
                return action
        return action
    market.append(["SELL", "WHEAT", qty])
    action["market"] = market[:10]
    return action


# _fert_gate: suprime SELL FERTILIZER quando preço < base*0.5 (libera slots).
_FERT_MIN_MULT = 0.5


def _fert_gate(action, obs, step):
    prices = ((obs.get("market") or {}).get("prices") or {})
    price = float(prices.get("FERTILIZER", 0) or 0)
    if price <= 0 or price >= _GBASE["FERTILIZER"] * _FERT_MIN_MULT:
        return action
    market = list(action.get("market") or [])
    new_market = []
    for o in market:
        if isinstance(o, list) and len(o) >= 3 and o[0] == "SELL" and o[1] == "FERTILIZER":
            continue
        new_market.append(o)
    action["market"] = new_market[:10]
    return action


def agent(obs, config=None):
    step = int(obs.get("step", 0) or 0)
    action = moon.agent(obs)
    _mature_opp_front_run(action, obs, step)
    action = _sell_first(action, obs, step)
    action = _glut_guard(action, obs, step)
    action = _fert_gate(action, obs, step)
    action = _wheat_mid_sell(action, obs, step)
    return action
'''


def _blob(path: Path) -> str:
    src = path.read_text(encoding="utf-8")
    idx = src.find("if __name__")
    if idx > 0:
        src = src[:idx]
    return base64.b85encode(zlib.compress(src.encode("utf-8"))).decode("utf-8")


def build() -> None:
    moon_src = ROOT / "research" / "public" / "moon_v17_goose.py"
    moon_b = _blob(moon_src)

    header = f'''"""hybrid_v21 - single-file Kaggle submission bundle.

Moon V56 + overlays do mix + glut-guard (do v17) + experimento B:
_wheat_mid_sell (venda de WHEAT excedente em preço alto) e _fert_gate
(suprime venda de FERTILIZER barato). Overlays de timing de mercado apenas.

Built by build_hybrid_v21.py. Self-contained: embute moon_v17_goose.py
(zlib+base85) e injeta os overlays inline.
"""
from __future__ import annotations

import base64
import types
import zlib

_MOON_B85 = {moon_b!r}


def _load(blob, modname):
    code = zlib.decompress(base64.b85decode(blob)).decode("utf-8")
    ns = types.ModuleType(modname)
    ns.__file__ = modname + ".py"
    exec(compile(code, modname + ".py", "exec"), ns.__dict__)
    return ns


moon = _load(_MOON_B85, "moon_agent_main")
'''

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(header + _MIX_OVERPRELUDE, encoding="utf-8")
    print(f"OK -> {OUT} ({OUT.stat().st_size} bytes)")
    print(f"    moon blob: {len(moon_b)} chars")


if __name__ == "__main__":
    build()
