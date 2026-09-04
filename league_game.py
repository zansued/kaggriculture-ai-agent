"""Worker: joga UMA partida entre dois agentes (paths de main.py) e imprime
uma linha JSON. Usado pelo league_bench (driver) via subprocess com timeout,
para que um jogo travado não derrube a liga e não haja contaminação de estado
(module-level) entre jogos.

Uso:
    python league_game.py --a <path_a> --b <path_b> --seed N [--steps 720]
"""
from __future__ import annotations

import argparse
import importlib.util
import inspect
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from src.clock_utils import clock_safe  # noqa: E402


def _modname(path: str) -> str:
    base = os.path.basename(path).replace(".py", "")
    base = re.sub(r"[^A-Za-z0-9_]", "_", base)
    return "ag_" + base + "_" + str(abs(len(path) * 7919 + sum(map(ord, path)) % 100000))


def _wrap(fn):
    try:
        n = len([p for p in inspect.signature(fn).parameters.values()
                 if p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)])
    except Exception:
        n = 2
    if n >= 2:
        return fn
    return (lambda obs, cfg=None: fn(obs))


def load(path: str):
    spec = importlib.util.spec_from_file_location(_modname(path), path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return clock_safe(_wrap(mod.agent))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--a", required=True)
    ap.add_argument("--b", required=True)
    ap.add_argument("--seed", type=int, required=True)
    ap.add_argument("--steps", type=int, default=720)
    args = ap.parse_args()

    from kaggle_environments import make
    a = load(args.a)
    b = load(args.b)
    env = make("kaggriculture", configuration={"episodeSteps": args.steps, "seed": args.seed})
    env.run([a, b])
    last = env.steps[-1]
    r0 = last[0]["reward"] if last[0] else None
    r1 = last[1]["reward"] if last[1] else None
    st0 = last[0]["status"] if last[0] else None
    st1 = last[1]["status"] if last[1] else None
    print(json.dumps({"seed": args.seed, "r0": r0, "r1": r1, "st0": st0, "st1": st1}))
    sys.stdout.flush()


if __name__ == "__main__":
    main()
