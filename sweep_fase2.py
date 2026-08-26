"""Harness rápido de experimentação: embrulha hybrid_v6 com overlays e roda h2h.

Uso:
  python /tmp/exp_harness.py <overlay_name> <seeds> [--p1 OVERLAY] [--mirror]
  python /tmp/exp_harness.py fert_dampen 1-12
  python /tmp/exp_harness.py wheat_sell 1-12 --p1 fert_dampen

Overlays disponíveis (em _OVERLAYS): cada função recebe (action, obs, step, cfg) -> action.
"""
import importlib.util, json, sys, os, argparse

REPO = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, REPO)

# carrega o v6
spec = importlib.util.spec_from_file_location("hv6", os.path.join(REPO, "submissions/hybrid_v6/main.py"))
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

_BASE = {"WHEAT": 25, "CARROT": 35, "TOMATO": 60, "STRAWBERRY": 120,
         "MELON": 250, "EGG": 50, "MILK": 160, "WOOL": 200, "FERTILIZER": 100}

# ---------------------------------------------------------------- overlays

def fert_dampen(action, obs, step, cfg):
    """Limita SELL FERTILIZER: só vende se preço >= limiar, e em lotes pequenos."""
    limiar = cfg.get("price", 25)
    max_qty = cfg.get("max_qty", 9999)
    prices = ((obs.get("market") or {}).get("prices") or {})
    fp = float(prices.get("FERTILIZER", 0) or 0)
    mkt = list(action.get("market") or [])
    new = []
    for o in mkt:
        if isinstance(o, list) and len(o) >= 3 and o[0] == "SELL" and o[1] == "FERTILIZER":
            if fp < limiar:
                continue  # suprime venda barata
            q = min(int(o[2]), max_qty)
            if q > 0:
                new.append(["SELL", "FERTILIZER", q])
        else:
            new.append(o)
    action["market"] = new[:10]
    return action


def fert_hold_all(action, obs, step, cfg):
    """Segura TODO fertilizante até o fim (d28+)."""
    if step < 672:
        action["market"] = [o for o in (action.get("market") or []) if not (isinstance(o, list) and len(o) >= 3 and o[0] == "SELL" and o[1] == "FERTILIZER")]
    return action


def wheat_sell(action, obs, step, cfg):
    """Vende excedente de wheat (shed - reserva) quando preço >= limiar (default 30)."""
    trigger = cfg.get("price", 30)
    reserve = cfg.get("reserve", 40)
    start = cfg.get("start", 8*24)
    stop = cfg.get("stop", 29*24)
    if not (start <= step < stop):
        return action
    prices = ((obs.get("market") or {}).get("prices") or {})
    shed = ((obs.get("private") or {}).get("shed") or {})
    mkt = list(action.get("market") or [])
    price = float(prices.get("WHEAT", 0) or 0)
    sq = int(shed.get("WHEAT", 0) or 0)
    qty = max(0, sq - reserve)
    if price >= trigger and qty > 0:
        has = any(isinstance(o, list) and len(o) >= 2 and o[0] == "SELL" and o[1] == "WHEAT" for o in mkt)
        if not has and len(mkt) < 10:
            mkt.append(["SELL", "WHEAT", qty])
            action["market"] = mkt[:10]
    return action


def wheat_aggressive(action, obs, step, cfg):
    """Aumenta a QUANTIDADE de qualquer SELL WHEAT existente para o excedente total."""
    reserve = cfg.get("reserve", 40)
    prices = ((obs.get("market") or {}).get("prices") or {})
    shed = ((obs.get("private") or {}).get("shed") or {})
    mkt = list(action.get("market") or [])
    sq = int(shed.get("WHEAT", 0) or 0)
    qty = max(0, sq - reserve)
    changed = False
    for o in mkt:
        if isinstance(o, list) and len(o) >= 3 and o[0] == "SELL" and o[1] == "WHEAT" and qty > int(o[2]):
            o[2] = qty
            changed = True
    if changed:
        action["market"] = mkt[:10]
    return action


def strawb_to_wheat(action, obs, step, cfg):
    """Re-aloca: converte PLANT STRAWBERRY em PLANT WHEAT (e BUY_SEED correspondente)
    nos dias 0..day_cut, para uma fração 'frac' dos steps de plantio de strawberry."""
    frac = cfg.get("frac", 0.5)
    day_cut = cfg.get("day_cut", 10)
    day = step // 24
    if day > day_cut:
        return action
    seed = hash((obs.get("seed"), step))  # determinístico
    convert = (seed % 100) / 100.0 < frac
    # converte farmer/hands PLANT STRAWBERRY -> WHEAT
    for key in ("farmer", "hands"):
        orders = action.get(key)
        if isinstance(orders, list):
            for o in orders:
                if isinstance(o, list) and len(o) >= 2 and o[0] == "PLANT" and o[1] == "STRAWBERRY" and convert:
                    o[1] = "WHEAT"
    # converte BUY_SEED STRAWBERRY -> WHEAT
    mkt = list(action.get("market") or [])
    for o in mkt:
        if isinstance(o, list) and len(o) >= 3 and o[0] == "BUY_SEED" and o[1] == "STRAWBERRY" and convert:
            o[1] = "WHEAT"
    return action


def wheat_arb(action, obs, step, cfg):
    """Intensifica arbitragem: compra wheat barato (preço <= lo) em lotes, até o shed
    estar quase cheio, para revender no pico."""
    price_lo = cfg.get("price_lo", 28)
    max_qty = cfg.get("max", 40)
    shed_cap = cfg.get("shed_cap", 85)
    start = cfg.get("start", 5*24)
    stop = cfg.get("stop", 18*24)
    if not (start <= step < stop):
        return action
    prices = ((obs.get("market") or {}).get("prices") or {})
    shed = ((obs.get("private") or {}).get("shed") or {})
    farms = obs.get("farms", []) or []
    seat = int((obs or {}).get("index", 0) or 0)
    money = 0
    if seat < len(farms):
        money = float((farms[seat] or {}).get("money", 0) or 0)
    wp = float(prices.get("WHEAT", 0) or 0)
    sq = int(shed.get("WHEAT", 0) or 0)
    total = sum(int(v or 0) for v in shed.values())
    mkt = list(action.get("market") or [])
    if wp <= price_lo and sq < shed_cap and total < 95 and money > 500 and len(mkt) < 10:
        q = min(max_qty, int(money // (wp + 1)), shed_cap - sq)
        if q > 0:
            mkt.append(["BUY_PRODUCT", "WHEAT", q])
            action["market"] = mkt[:10]
    return action


_OVERLAYS = {
    "fert_dampen": fert_dampen,
    "fert_hold": fert_hold_all,
    "wheat_sell": wheat_sell,
    "wheat_agg": wheat_aggressive,
    "strawb2wheat": strawb_to_wheat,
    "wheat_arb": wheat_arb,
}

# ---------------------------------------------------------------- runner

def make_agent(overlay_name, cfg):
    if overlay_name is None or overlay_name == "base":
        return mod.agent
    ov = _OVERLAYS[overlay_name]
    def agent(obs, config=None):
        action = mod.agent(obs, config)
        return ov(action, obs, int((obs or {}).get("step", 0) or 0), cfg)
    return agent


def parse_seeds(spec):
    if "-" in spec:
        a, b = spec.split("-")
        return list(range(int(a), int(b) + 1))
    return [int(x) for x in spec.split(",")]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("a", help="overlay para P0 (base | nome | nome:param=val,...)")
    ap.add_argument("seeds", help="ex: 1-12")
    ap.add_argument("--p1", default="base", help="overlay para P1")
    ap.add_argument("--cfg", default="", help="cfg para P0: price=30,reserve=40,...")
    ap.add_argument("--json", default="")
    args = ap.parse_args()

    def parse_overlay(s):
        name = s
        cfg = {}
        if ":" in s:
            name, cfgpart = s.split(":", 1)
            for kv in cfgpart.split(","):
                if not kv: continue
                k, v = kv.split("=")
                cfg[k] = float(v) if "." in v else int(v)
        return name, cfg

    a0, cfg0 = parse_overlay(args.a)
    a1, cfg1 = parse_overlay(args.p1)
    # funde cfg extra
    for kv in args.cfg.split(","):
        if not kv: continue
        k, v = kv.split("=")
        cfg0[k] = float(v) if "." in v else int(v)

    from kaggle_environments import make
    seeds = parse_seeds(args.seeds)
    wins_a = wins_b = ties = 0
    margins = []
    games = []
    for seed in seeds:
        env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": seed})
        env.run([make_agent(a0, cfg0), make_agent(a1, cfg1)])
        last = env.steps[-1]
        r0 = last[0]["reward"] if last[0] else None
        r1 = last[1]["reward"] if last[1] else None
        st0 = last[0]["status"] if last[0] else None
        st1 = last[1]["status"] if last[1] else None
        if r0 is None or r1 is None:
            print(f"  [seed {seed:>2}] BAD r0={r0} r1={r1}", flush=True)
            continue
        if r0 > r1: wins_a += 1
        elif r1 > r0: wins_b += 1
        else: ties += 1
        margins.append(r0 - r1)
        games.append({"seed": seed, "r0": r0, "r1": r1})
        print(f"  [seed {seed:>2}] {r0:>7.0f} vs {r1:>7.0f} d={r0-r1:>+8.0f} {'A' if r0>r1 else 'B' if r1>r0 else 'T'}", flush=True)
    n = len(margins)
    print(f"\n=== {args.a} vs {args.p1}: {wins_a}-{wins_b} (ties={ties}, n={n}) ===")
    if n:
        import statistics
        print(f"  mean P0={statistics.mean(g['r0'] for g in games):.0f}  mean P1={statistics.mean(g['r1'] for g in games):.0f}  mean d={statistics.mean(margins):+.0f}")
    if args.json:
        json.dump({"a": args.a, "b": args.p1, "games": games}, open(args.json, "w"), indent=1)


if __name__ == "__main__":
    main()
