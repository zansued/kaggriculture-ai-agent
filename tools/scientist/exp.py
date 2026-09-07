"""Registra um experimento no meta-registry (tabela experiments).

Modo JSON (recomendado): passar --json com um OU dois arquivos h2h (p0 e p1),
JÁ NORMALIZADOS com o candidato como 'a' (referência/P0). O placar é somado.

Uso:
    python exp.py --a hybrid_v20_x --b hybrid_v19 --axis producao --verdict refutado \
        --notes "..." --json results/h2h_x_p0.json results/h2h_x_p1.json
    # ou explícito:
    python exp.py --a v19 --b v18 --wins-a 39 --wins-b 9 --ties 0 --mean-d 446.9 \
        --axis revalidacao --verdict campeao --seeds 1-24 --notes "..."
"""
from __future__ import annotations

import argparse
import json
import sys

from db import current_git_sha, get_conn


def stats_from_jsons(paths):
    wa = wb = ties = 0
    weighted = 0.0
    n = 0
    for p in paths:
        d = json.load(open(p, encoding='utf-8'))
        wa += d['wins_a']
        wb += d['wins_b']
        ties += d['ties']
        weighted += d['mean_d'] * d['n']
        n += d['n']
    mean_d = round(weighted / n, 1) if n else 0.0
    return wa, wb, ties, mean_d, n


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--a', required=True, help='agente candidato/referencia')
    ap.add_argument('--b', required=True, help='agente oponente/baseline')
    ap.add_argument('--seeds', default='1-24')
    ap.add_argument('--axis', default=None, help='eixo: market|producao|execucao|estrutura|revalidacao|...')
    ap.add_argument('--verdict', default=None, help='campeao|refutado|inconclusivo|neutro')
    ap.add_argument('--notes', default='')
    ap.add_argument('--git-sha', default=None)
    ap.add_argument('--json', nargs='*', default=[])
    ap.add_argument('--wins-a', type=int, default=None)
    ap.add_argument('--wins-b', type=int, default=None)
    ap.add_argument('--ties', type=int, default=None)
    ap.add_argument('--mean-d', type=float, default=None)
    args = ap.parse_args()

    if args.json:
        wa, wb, ties, mean_d, n = stats_from_jsons(args.json)
        wins_a, wins_b = wa, wb
    else:
        if None in (args.wins_a, args.wins_b, args.ties, args.mean_d):
            print('ERRO: informe --json OU --wins-a/--wins-b/--ties/--mean-d')
            return 1
        wins_a, wins_b, ties, mean_d = args.wins_a, args.wins_b, args.ties, args.mean_d

    sha = args.git_sha or current_git_sha()
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO experiments (agent_a, agent_b, seeds, wins_a, wins_b, ties,
                                 mean_d, json_path, git_sha, axis, verdict, notes)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        RETURNING id
    """, (args.a, args.b, args.seeds, wins_a, wins_b, ties, mean_d,
          ';'.join(args.json) or None, sha, args.axis, args.verdict, args.notes))
    rid = cur.fetchone()[0]
    conn.commit()
    cur.close()
    conn.close()
    print(f'experiment id={rid}: {args.a} {wins_a}-{wins_b} {args.b} '
          f'(ties={ties}, mean_d={mean_d:+}, axis={args.axis}, verdict={args.verdict})')
    return 0


if __name__ == '__main__':
    sys.exit(main())
