"""Build do bundle single-file do HÍBRIDO V18 (adaptativo): Moon V56 (GOOSE
expandido do v17) + overlays + GLUT-GUARD ADAPTATIVO.

Fase B do PLANO_TOP10.md: substituir o glut-guard FIXO (base estática) por
decisão baseada na série de preços REAL da partida:
  - dyn_base[item] = média dos últimos N preços (janela ~1 dia).
  - momentum = (preço atual - média anterior) / média anterior.
  - momentum NEGATIVO => vender mais cedo (floor menor, captura antes do crash).
  - momentum POSITIVO => segurar mais (floor maior, espera o pico).
  - Vendas FRACIONADAS (lote máx ~16) como os tops — suaviza impacto no preço.

Referência: docs/PLANO_TOP10.md (Fase B), docs/TOPS_ADAPTIVE_27AGO.md.

VALIDAÇÃO (31/08, seeds 1-72, 2 lados = 144 jogos):
  v18 124-20 vs v17 (86.1% dos não-empates, mean_d +514).
  Maior avanço desde v6->v17. Submetido como NOVO CAMPEÃO (31/08).

Output: submissions/hybrid_v20/main.py
Usage:   python build_hybrid_v20.py
"""
from __future__ import annotations

import base64
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "submissions" / "hybrid_v20" / "main.py"

_MIX_OVERPRELUDE = '''\
# ---------------------------------------------------------------------------
# Overlays do mix_agent (validados) — injetados sobre a base Moon.
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
# V18: _glut_guard ADAPTATIVO — decisão de venda pela série de preços real.
# Substitui o glut-guard fixo do v17 (base estática + floor fixo).
# ---------------------------------------------------------------------------
_GBASE = {"WHEAT": 25, "CARROT": 35, "TOMATO": 60, "STRAWBERRY": 120,
          "MELON": 250, "EGG": 50, "MILK": 160, "WOOL": 200, "FERTILIZER": 100}
_GRISERS = ("WHEAT", "CARROT", "TOMATO")
_GHOLD = 0.5
_GRISE_MULT = 1.3
_GDUMP = ("MILK", "WOOL", "MELON", "STRAWBERRY")
_GSTART = 200
_GSTOP = 680

# Parâmetros POR ITEM (v19): cada produto tem dinâmica de preço própria.
# MELON crasha d10; MILK pico curto d12-14; WOOL recupera no fim; STRAWB declina.
_ITEM_CFG = {
    "MILK":       {"floor": 0.42, "shift": 0.10, "window": 10, "lote": 16, "mom": 0.06},
    "WOOL":       {"floor": 0.50, "shift": 0.15, "window": 24, "lote": 12, "mom": 0.04},
    "MELON":      {"floor": 0.35, "shift": 0.16, "window": 8, "lote": 12, "mom": 0.08},
    "STRAWBERRY": {"floor": 0.38, "shift": 0.10, "window": 12, "lote": 16, "mom": 0.05},
}

_PHIST = {}           # seat -> {item -> [preços]}


def _glut_guard(action, obs, step):
    if not (_GSTART <= step < _GSTOP):
        return action
    market = list(action.get("market", []) or [])
    if not market:
        return action
    prices = ((obs.get("market") or {}).get("prices") or {})
    shed = ((obs.get("private") or {}).get("shed") or {})
    seat = int((obs or {}).get("index", 0) or 0)

    # atualiza histórico de preços (por item premium)
    hist = _PHIST.setdefault(seat, {})
    for item, c in _ITEM_CFG.items():
        p = float(prices.get(item, 0) or 0)
        if p > 0:
            hist.setdefault(item, []).append(p)
            if len(hist[item]) > c["window"]:
                hist[item] = hist[item][-c["window"]:]

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

            if item in _ITEM_CFG:
                c = _ITEM_CFG[item]
                h = hist.get(item, [])
                if len(h) < 5:
                    floor = c["floor"]
                else:
                    dyn_base = sum(h) / len(h)
                    prev = h[:max(1, len(h) - 4)]
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
    step = int(obs.get("step", 0) or 0)
    action = moon.agent(obs)
    _mature_opp_front_run(action, obs, step)
    action = _sell_first(action, obs, step)
    action = _glut_guard(action, obs, step)
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

    header = f'''"""hybrid_v20 - single-file Kaggle submission bundle.

Moon V56 (GOOSE v17) + overlays do mix + glut-guard ADAPTATIVO:
  - base dinamica (media recente) + momentum para decidir dump/hold.
  - vendas FRACIONADAS (lotes ate 16) como os tops.
  - janela 200-680.

Built by build_hybrid_v20.py. Self-contained.
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
