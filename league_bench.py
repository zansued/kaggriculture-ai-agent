"""Liga de arquétipos (driver robusto): valida o campeão contra um painel de
oponentes diversos, espelhando os 2 lados por seed. Cada jogo roda num
subprocesso com timeout (league_game.py) — um jogo travado vira BAD e a liga
segue; e não há contaminação de estado module-level entre jogos.

Uso:
    python league_bench.py                          # champ v19, seeds 1-8, painel completo
    python league_bench.py --seeds 1-6
    python league_bench.py --only moon,soil,v18
    python league_bench.py --json results/league_v19.json
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import subprocess
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_GAME = os.path.join(_HERE, "league_game.py")

PANEL = [
    ("v18",      "v18 (sell-adapt prev)",   "submissions/hybrid_v18/main.py"),
    ("moon",     "moon_v56 (mesma familia)", "submissions/moon/main.py"),
    ("soil",     "soil_v19 (rota modal)",   "submissions/soil/main.py"),
    ("mix",      "mix_single (market-flow)", "submissions/mix_single/main.py"),
    ("c27",      "c27 (clone front-run)",   "submissions/c27/main.py"),
    ("purearch", "purearch (baseline fita)", "reference/opponents/purearch_opponent.py"),
    ("trace",    "trace_10c4s",             "submissions/trace_10c4s/main.py"),
]

CHAMP = "submissions/hybrid_v19/main.py"
DEFAULT_TIMEOUT = 90  # s por jogo; acima disso = BAD (travou)


def parse_seeds(spec: str):
    if "-" in spec:
        a, b = spec.split("-")
        return list(range(int(a), int(b) + 1))
    return [int(x) for x in spec.split(",") if x]


def resolve(path: str):
    if path.endswith(".py"):
        return os.path.join(_HERE, path) if not os.path.isabs(path) else path
    for k, _, p in PANEL:
        if k == path:
            return os.path.join(_HERE, p)
    raise ValueError(f"chave desconhecida: {path}")


def play_one(a_path: str, b_path: str, seed: int, steps: int, timeout: int):
    """Roda [a_path, b_path] num subprocesso. Retorna dict."""
    cmd = [sys.executable, _GAME, "--a", a_path, "--b", b_path,
           "--seed", str(seed), "--steps", str(steps)]
    try:
        cp = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                            cwd=_HERE, encoding="utf-8", errors="replace")
    except subprocess.TimeoutExpired:
        return {"ok": False, "err": "TIMEOUT"}
    if cp.returncode != 0:
        return {"ok": False, "err": f"EXIT {cp.returncode}: {cp.stderr[-300:]}"}
    for line in reversed(cp.stdout.strip().splitlines()):
        line = line.strip()
        if line.startswith("{"):
            try:
                d = json.loads(line)
                return {"ok": True, "r0": d.get("r0"), "r1": d.get("r1"),
                        "st0": d.get("st0"), "st1": d.get("st1")}
            except Exception as e:
                return {"ok": False, "err": f"JSON: {e}"}
    return {"ok": False, "err": f"sem JSON no stdout: {cp.stdout[-200:]}"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--champ", default=CHAMP)
    ap.add_argument("--seeds", default="1-8")
    ap.add_argument("--steps", type=int, default=720)
    ap.add_argument("--only", default=None)
    ap.add_argument("--json", default=None)
    ap.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT)
    args = ap.parse_args()
    timeout = args.timeout

    champ = resolve(args.champ)
    if args.only:
        keys = [k.strip() for k in args.only.split(",") if k.strip()]
        panel = [(k, lab, resolve(p)) for k, lab, p in PANEL if k in keys]
    else:
        panel = [(k, lab, resolve(p)) for k, lab, p in PANEL]
    seeds = parse_seeds(args.seeds)

    print(f"=== LIGA champ={os.path.basename(champ)} vs "
          f"{[k for k, _, _ in panel]} seeds={seeds} (2 lados/seed) ===", flush=True)

    rows = []
    for key, lab, opp in panel:
        w = l = t = 0
        margins = []
        games = []
        for seed in seeds:
            for side in (0, 1):
                if side == 0:
                    res = play_one(champ, opp, seed, args.steps, timeout)
                    if res["ok"]:
                        c, o = res["r0"], res["r1"]
                        good = res["st0"] == "DONE" and res["st1"] == "DONE"
                    else:
                        c = o = None; good = False
                else:
                    res = play_one(opp, champ, seed, args.steps, timeout)
                    if res["ok"]:
                        c, o = res["r1"], res["r0"]  # champ é P1
                        good = res["st0"] == "DONE" and res["st1"] == "DONE"
                    else:
                        c = o = None; good = False
                tag = "OK " if (res.get("ok") and good) else "BAD"
                if res.get("ok") and good:
                    if c is None or o is None:
                        tag = "BAD"
                if tag == "BAD":
                    games.append({"seed": seed, "side": side, "err": res.get("err", "bad")})
                    print(f"  [{key:>8} s{seed:>2} {side}] BAD {res.get('err','')}", flush=True)
                    continue
                c, o = float(c), float(o)
                if c > o:
                    w += 1
                elif o > c:
                    l += 1
                else:
                    t += 1
                margins.append(c - o)
                games.append({"seed": seed, "side": side, "champ_r": c, "opp_r": o})
                print(f"  [{key:>8} s{seed:>2} {'P0' if side==0 else 'P1'}] "
                      f"champ={c:>8.0f} opp={o:>8.0f} d={c-o:>+9.0f} "
                      f"{'W' if c>o else 'L' if o>c else 'T'}", flush=True)
        n = w + l + t
        mean_d = statistics.mean(margins) if margins else 0.0
        wl = f"{w}-{l}" + (f"-{t}" if t else "")
        note = "  <<< PERDE P/ ARQUÉTIPO" if n and l > w else ""
        print(f"== {key} ({lab}): champ {wl} n={n} mean_d={mean_d:+.0f}{note}", flush=True)
        rows.append({"key": key, "label": lab, "w": w, "l": l, "t": t, "n": n,
                     "mean_d": round(mean_d, 1), "games": games})
        if args.json:
            out = args.json if os.path.isabs(args.json) else os.path.join(_HERE, args.json)
            os.makedirs(os.path.dirname(out), exist_ok=True)
            json.dump({"champ": champ, "seeds": seeds, "rows": rows}, open(out, "w"), indent=1)
            print(f"  [parcial json -> {out}]", flush=True)

    print("\n=== MATRIZ FINAL (champ vs arquétipo) ===", flush=True)
    for r in rows:
        if r["n"]:
            wl = f"{r['w']}-{r['l']}" + (f"-{r['t']}" if r["t"] else "")
            print(f"  vs {r['key']:>10} ({r['label']:<22}): {wl:>8}  "
                  f"mean_d={r['mean_d']:+.0f}  winrate={(100*r['w']/r['n']):.1f}%", flush=True)
    print("=== fim liga ===", flush=True)

    if args.json:
        out = args.json if os.path.isabs(args.json) else os.path.join(_HERE, args.json)
        os.makedirs(os.path.dirname(out), exist_ok=True)
        json.dump({"champ": champ, "seeds": seeds, "rows": rows}, open(out, "w"), indent=1)
        print(f"wrote {out}", flush=True)


if __name__ == "__main__":
    main()
