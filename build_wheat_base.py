"""build_wheat_base — gerador de fita wheat-heavy (Fase 3).

Pipeline: agente gerador -> fita 720-step -> bundle single-file para Kaggle.

Estado (26/08): o agente gerador (src/wheat_base_v1.py) AINDA NÃO produz uma
fita competitiva — a coordenação reativa simples não escala (ver docs/
WHEAT_BASE_DESIGN.md §8). Este script estabelece o PIPELINE: gera a fita,
valida o reward e embute num bundle. Quando o gerador melhorar, a fita resultante
é o agente do ladder.

Uso:
    python build_wheat_base.py --seed 1 --tape /tmp/wheat_tape.json
    python build_wheat_base.py --tape /tmp/wheat_tape.json --build
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

OUT = ROOT / "submissions" / "wheat_base" / "main.py"


def generate_tape(seed: int, steps: int = 720):
    """Roda o agente gerador num seed e devolve a fita (lista de ações)."""
    from wheat_base_v1 import WheatBaseV1

    from kaggle_environments import make

    brain = WheatBaseV1()
    tape = [None] * steps

    def wrapper(obs, config=None):
        action = brain.decide(obs, config)
        step = min(int((obs or {}).get("step", 0) or 0), steps - 1)
        tape[step] = action
        return action

    env = make("kaggriculture", configuration={"episodeSteps": steps, "seed": seed})
    env.run([wrapper, wrapper])
    # preenche possíveis None com PASS
    for i, a in enumerate(tape):
        if a is None:
            tape[i] = {"farmer": ["PASS"], "hands": [], "market": []}
    return tape


def validate_tape(tape: list, seed: int = 1):
    """Roda a fita como agente estático e mede o reward."""
    from kaggle_environments import make

    def agent(obs, config=None):
        step = int((obs or {}).get("step", 0) or 0)
        return tape[min(step, len(tape) - 1)]

    env = make("kaggriculture", configuration={"episodeSteps": len(tape), "seed": seed})
    env.run([agent, agent])
    last = env.steps[-1]
    r0 = last[0]["reward"] if last[0] else None
    r1 = last[1]["reward"] if last[1] else None
    return r0, r1


def build_bundle(tape: list, out: Path = OUT):
    """Embute a fita num bundle single-file (padrão Moon)."""
    out.parent.mkdir(parents=True, exist_ok=True)
    blob = base64.b85encode(zlib.compress(json.dumps(tape).encode("utf-8"))).decode("utf-8")
    bundle = f'''"""wheat_base - fita wheat-heavy (Fase 3). Gerada por build_wheat_base.py.

A fita é uma lista de 720 ações pré-computadas (uma por step). O agente apenas
reproduz a ação do step atual. Validar antes de submeter.
"""
from __future__ import annotations

import base64
import json
import zlib

_TAPE_B85 = {blob!r}


def _load():
    return json.loads(zlib.decompress(base64.b85decode(_TAPE_B85)).decode("utf-8"))


_TAPE = _load()


def agent(obs, config=None):
    step = int((obs or {{}}).get("step", 0) or 0)
    if step >= len(_TAPE):
        return {{"farmer": ["PASS"], "hands": [], "market": []}}
    return _TAPE[step]


def _kaggle_submission_entrypoint(obs):
    return agent(obs)
'''
    out.write_text(bundle, encoding="utf-8")
    print(f"OK -> {out} ({out.stat().st_size} bytes)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--tape", default="")
    ap.add_argument("--build", action="store_true", help="gera o bundle")
    ap.add_argument("--validate", action="store_true", help="valida a fita no engine")
    args = ap.parse_args()

    if args.tape and os.path.exists(args.tape):
        tape = json.load(open(args.tape))
    else:
        print(f"Gerando fita com seed {args.seed}...")
        tape = generate_tape(args.seed)
        if args.tape:
            json.dump(tape, open(args.tape, "w"))
            print(f"fita salva em {args.tape}")

    print(f"fita: {len(tape)} steps")
    if args.validate:
        r0, r1 = validate_tape(tape, seed=args.seed)
        print(f"reward mirror no seed {args.seed}: {r0:.0f} / {r1:.0f}")
    if args.build:
        build_bundle(tape)


if __name__ == "__main__":
    main()
