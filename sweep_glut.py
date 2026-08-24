"""Sweep dos parâmetros do overlay _glut_guard (timing adaptativo à saturação).

Base: submissions/hybrid_single/main.py (Moon V56 + mature_opp_front_run +
sell_first). Cada config aplica uma variação do glut_guard sobre a MESMA base,
e roda head-to-head contra o hybrid_v2 atual (submissions/hybrid_v2/main.py).

Hipótese central: o v2 segura os late risers (CARROT/TOMATO/WHEAT) só até
preço < base*1.3, mas os dados mostram CARROT 35->279 (8x) e TOMATO 60->409
(6.8x). Segurar por mais tempo (mult maior / hold maior) deve capturar melhor
a subida. Também testamos o dump floor dos colapsantes (MILK/WOOL).

Métrica que importa: W/L do confronto direto (o ladder avalia W/D/L, não
margem). Rodar triagem com --seeds 1-12 e validar top-2 com 1-36.

Usage:
    python sweep_glut.py --seeds 1-12            # triagem rápida
    python sweep_glut.py --seeds 1-36 --configs 0-8   # validação completa
"""
from __future__ import annotations

import argparse
import importlib.util
import os
import sys
import statistics

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

from kaggle_environments import make  # noqa: E402

# ---------------------------------------------------------------------------
# Base (submissions/hybrid_single/main.py) — carregada UMA vez, reusada.
# ---------------------------------------------------------------------------
_BASE_PATH = os.path.join(_HERE, "submissions", "hybrid_single", "main.py")
_spec = importlib.util.spec_from_file_location("h1_base", _BASE_PATH)
_h1 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_h1)

_BASE_PRICE = {
    "WHEAT": 25, "CARROT": 35, "TOMATO": 60, "STRAWBERRY": 120,
    "MELON": 250, "EGG": 50, "MILK": 160, "WOOL": 200, "FERTILIZER": 100,
}

# Defaults (== hybrid_v2 atual)
_DEF = {
    "rise_items": ("WHEAT", "CARROT", "TOMATO"),
    "hold_ratio": 0.5,
    "rise_mult": 1.3,           # float OR dict per-item
    "dump_items": ("MILK", "WOOL", "MELON", "STRAWBERRY"),
    "dump_floor": 0.55,
    "start": 200,
    "stop": 700,
}


def _make_guard(cfg: dict):
    cfg = {**_DEF, **cfg}
    rise_mult = cfg["rise_mult"]
    hold = cfg["hold_ratio"]
    dump_floor = cfg["dump_floor"]
    gstart, gstop = cfg["start"], cfg["stop"]
    rise_items = cfg["rise_items"]
    dump_items = cfg["dump_items"]

    def _floor_of(item):
        return dump_floor if isinstance(dump_floor, float) else dump_floor.get(item, 0.55)

    def _guard(action, obs, step):
        if not (gstart <= step < gstop):
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
                if item in rise_items and price > 0 and price < base * (rise_mult if isinstance(rise_mult, float) else rise_mult.get(item, 1.3)):
                    keep = max(1, int(qty * hold))
                    new_market.append(["SELL", item, keep])
                elif item in dump_items and price >= base * _floor_of(item):
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

    return _guard


def _make_agent(cfg: dict):
    guard = _make_guard(cfg)

    def agent(obs, config=None):
        step = int(obs.get("step", 0) or 0)
        action = _h1.agent(obs, config)
        return guard(action, obs, step)

    return agent


# ---------------------------------------------------------------------------
# Configs do sweep
# ---------------------------------------------------------------------------
CONFIGS = [
    ("baseline v2  (mult=1.3, hold=0.5, floor=0.55)",
     {}),
    ("risers mult 2.0 (todos)",
     {"rise_mult": 2.0}),
    ("risers mult 3.0 (todos)",
     {"rise_mult": 3.0}),
    ("exploders seguros (CARROT/TOMATO 3.0, WHEAT 1.3)",
     {"rise_mult": {"WHEAT": 1.3, "CARROT": 3.0, "TOMATO": 3.0}}),
    ("exploders seguros + hold 0.7",
     {"rise_mult": {"WHEAT": 1.3, "CARROT": 3.0, "TOMATO": 3.0}, "hold_ratio": 0.7}),
    ("hold 0.7 (mult 1.3)",
     {"hold_ratio": 0.7}),
    ("hold 0.3 (mult 1.3)",
     {"hold_ratio": 0.3}),
    ("dump floor 0.70 (dump mais cedo)",
     {"dump_floor": 0.70}),
    ("dump floor 0.40 (dump mais tarde)",
     {"dump_floor": 0.40}),
    ("janela 250-650",
     {"start": 250, "stop": 650}),
    ("hold 0.7 + dump 0.40",
     {"hold_ratio": 0.7, "dump_floor": 0.40}),
    ("hold 0.7 + janela 250-650",
     {"hold_ratio": 0.7, "start": 250, "stop": 650}),
    ("dump 0.40 + janela 250-650",
     {"dump_floor": 0.40, "start": 250, "stop": 650}),
    ("hold 0.7 + dump 0.40 + janela 250-650",
     {"hold_ratio": 0.7, "dump_floor": 0.40, "start": 250, "stop": 650}),
    # --- Calibração por item do dump_floor (após validar dump 0.40 global) ---
    ("dump per-item: MILK/WOOL 0.45, MELON/STRAWB 0.40",
     {"dump_floor": {"MILK": 0.45, "WOOL": 0.45, "MELON": 0.40, "STRAWBERRY": 0.40}}),
    ("dump per-item: MILK/WOOL 0.35, MELON/STRAWB 0.45",
     {"dump_floor": {"MILK": 0.35, "WOOL": 0.35, "MELON": 0.45, "STRAWBERRY": 0.45}}),
    ("dump per-item: MILK 0.30, WOOL 0.50, MELON 0.40, STRAWB 0.30",
     {"dump_floor": {"MILK": 0.30, "WOOL": 0.50, "MELON": 0.40, "STRAWBERRY": 0.30}}),
    ("dump per-item + janela 250-650",
     {"dump_floor": {"MILK": 0.45, "WOOL": 0.45, "MELON": 0.40, "STRAWBERRY": 0.40},
      "start": 250, "stop": 650}),
]


def parse_seeds(spec: str):
    if "-" in spec:
        a, b = spec.split("-")
        return list(range(int(a), int(b) + 1))
    return [int(x) for x in spec.split(",") if x]


def run_h2h(agent_a, agent_b, seeds):
    wins = losses = ties = 0
    margins = []
    for seed in seeds:
        env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": seed})
        env.run([agent_a, agent_b])
        last = env.steps[-1]
        r0 = last[0]["reward"] if last[0] and last[0].get("status") == "DONE" else None
        r1 = last[1]["reward"] if last[1] and last[1].get("status") == "DONE" else None
        if r0 is None or r1 is None:
            print(f"    [seed {seed}] BAD r0={r0} r1={r1}", flush=True)
            continue
        margins.append(r0 - r1)
        if r0 > r1:
            wins += 1
        elif r1 > r0:
            losses += 1
        else:
            ties += 1
    return wins, losses, ties, margins


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", default="1-12")
    ap.add_argument("--configs", default=None,
                    help="config indices, ex '0-8' ou '0,3' (default: todos)")
    ap.add_argument("--opp", default="v2",
                    help="oponente: 'v2' (submissions/hybrid_v2/main.py) ou 'base' (hybrid_single)")
    args = ap.parse_args()
    seeds = parse_seeds(args.seeds)

    if args.opp == "v2":
        opp_path = os.path.join(_HERE, "submissions", "hybrid_v2", "main.py")
    else:
        opp_path = _BASE_PATH
    ospec = importlib.util.spec_from_file_location("h2_base", opp_path)
    opp = importlib.util.module_from_spec(ospec)
    ospec.loader.exec_module(opp)
    opp_agent = opp.agent

    if args.configs is not None:
        if "-" in args.configs:
            a, b = args.configs.split("-")
            idxs = list(range(int(a), int(b) + 1))
        else:
            idxs = [int(x) for x in args.configs.split(",") if x]
        configs = [CONFIGS[i] for i in idxs]
    else:
        configs = CONFIGS

    print(f"=== SWEEP glut_guard vs {args.opp}, seeds={seeds} ===", flush=True)
    results = []
    for label, cfg in configs:
        print(f"\n### {label}", flush=True)
        cand = _make_agent(cfg)
        wins, losses, ties, margins = run_h2h(cand, opp_agent, seeds)
        mean_d = statistics.mean(margins) if margins else float("nan")
        total_d = sum(margins)
        results.append((label, wins, losses, ties, mean_d, total_d, len(margins)))
        print(f"    -> {wins}W-{losses}L (ties={ties}, n={len(margins)})  "
              f"mean_d={mean_d:+.0f}  total_d={total_d:+.0f}", flush=True)

    print("\n=== SUMMARY (sorted by W-L) ===")
    results.sort(key=lambda r: -(r[1] - r[2]))
    for label, w, l, t, mean_d, total_d, n in results:
        print(f"  {w}W-{l}L (ties={t}, n={n})  total_d={total_d:>+8}  {label}")


if __name__ == "__main__":
    main()
