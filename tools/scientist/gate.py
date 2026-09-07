"""Gate estatístico — a "checklist do Skeptic".

Decide, a partir dos JSONs h2h 2 lados (normalizados com o candidato como 'a'),
se o candidato VENCEU o campeão com disciplina estatística mínima.

Regras pré-registradas (não mudar por conveniência):
  1. n_total >= --min-n (default 32)
  2. duas posições presentes (P0 e P1) -> --jsons tem 2 arquivos
  3. taxa de vitória sobre não-empates >= --win-rate (default 0.58)
  4. mean_d > 0

Uso:
    python gate.py --candidate hybrid_v20_x --champion hybrid_v19 \
        --jsons results/x_p0.json results/x_p1.json
"""
from __future__ import annotations

import argparse
import sys

from h2h import combine_stats


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--candidate', required=True)
    ap.add_argument('--champion', required=True)
    ap.add_argument('--jsons', nargs='+', required=True)
    ap.add_argument('--win-rate', type=float, default=0.58)
    ap.add_argument('--min-n', type=int, default=32)
    args = ap.parse_args()

    wa, wb, ties, mean_d, n, n_files = combine_stats(args.jsons)
    total = wa + wb
    win_rate = wa / total if total else None
    is_reval = args.candidate == args.champion

    checks = {
        'n_suficiente': n >= args.min_n,
        'duas_posicoes': n_files >= 2,
        'taxa_vitoria': (win_rate is not None and win_rate >= args.win_rate),
        'mean_d_positivo': mean_d > 0,
    }
    print(f'=== GATE: {args.candidate} vs {args.champion} ===')
    print(f'  placar {wa}-{wb} (ties={ties}, n={n})  win_rate={win_rate and round(win_rate,3)}  mean_d={mean_d:+}')
    if is_reval:
        print('  (revalidacao: candidato == campeao)')
    for k, ok in checks.items():
        print(f'  [{"PASS" if ok else "FAIL"}] {k}')

    if all(checks.values()):
        verdict = 'campeao'
    elif win_rate is not None and win_rate <= 1 - args.win_rate and mean_d < 0:
        verdict = 'refutado'
    else:
        verdict = 'inconclusivo'
    print(f'=== VEREDITO: {verdict} ===')
    return 0 if verdict == 'campeao' else (1 if verdict == 'refutado' else 2)


if __name__ == '__main__':
    sys.exit(main())
