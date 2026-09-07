"""Finalizador do Scientist loop — valida um candidato e grava o veredito.

Fluxo (Runner -> Gate -> Learner):
  1. Lê os JSONs h2h 2 lados (candidato como 'a', JÁ normalizados).
  2. Aplica o gate (Skeptic): n>=min-n, 2 posições, win_rate>=threshold, mean_d>0.
  3. Se --dry-run: só imprime. Senão:
       - insere em experiments (dedupe por agente/placar/verdict);
       - marca a hipótese (--hypothesis-id) como suportada/rejeitada e liga ao experimento.
  4. Exit code: 0=campeao, 1=refutado, 2=inconclusivo, 3=erro.

Uso:
    python finalize_experiment.py --candidate hybrid_v20_x --champion hybrid_v19 \
        --jsons results/x_p0.json results/x_p1.json \
        --axis producao --hypothesis-id 3 --notes "..." [--dry-run]
"""
from __future__ import annotations

import argparse
import sys

from db import current_git_sha, get_conn
from h2h import combine_stats


def verdict_of(wa, wb, ties, mean_d, n, n_files, win_rate, min_n):
    total = wa + wb
    wr = wa / total if total else None
    checks = {
        'n_suficiente': n >= min_n,
        'duas_posicoes': n_files >= 2,
        'taxa_vitoria': (wr is not None and wr >= win_rate),
        'mean_d_positivo': mean_d > 0,
    }
    if all(checks.values()):
        return 'campeao', wr, checks
    if wr is not None and wr <= 1 - win_rate and mean_d < 0:
        return 'refutado', wr, checks
    return 'inconclusivo', wr, checks


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--candidate', required=True)
    ap.add_argument('--champion', required=True)
    ap.add_argument('--jsons', nargs='+', required=True)
    ap.add_argument('--axis', default=None)
    ap.add_argument('--notes', default='')
    ap.add_argument('--hypothesis-id', type=int, default=None)
    ap.add_argument('--win-rate', type=float, default=0.58)
    ap.add_argument('--min-n', type=int, default=32)
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--git-sha', default=None)
    args = ap.parse_args()

    wa, wb, ties, mean_d, n, n_files = combine_stats(args.jsons)
    verdict, wr, checks = verdict_of(wa, wb, ties, mean_d, n, n_files,
                                     args.win_rate, args.min_n)
    is_reval = args.candidate == args.champion

    print(f'=== FINALIZE: {args.candidate} vs {args.champion} ===')
    print(f'  placar {wa}-{wb} (ties={ties}, n={n}, files={n_files})  '
          f'win_rate={wr and round(wr,3)}  mean_d={mean_d:+}')
    if is_reval:
        print('  (revalidacao: candidato == campeao)')
    for k, ok in checks.items():
        print(f'  [{"PASS" if ok else "FAIL"}] {k}')
    print(f'=== VEREDITO: {verdict} ===')

    if args.dry_run:
        print('(dry-run: nada gravado)')
        return 0 if verdict == 'campeao' else (1 if verdict == 'refutado' else 2)

    sha = args.git_sha or current_git_sha()
    conn = get_conn()
    cur = conn.cursor()

    # dedupe
    cur.execute("""
        SELECT 1 FROM experiments
        WHERE agent_a=%s AND agent_b=%s AND wins_a=%s AND wins_b=%s AND verdict=%s LIMIT 1
    """, (args.candidate, args.champion, wa, wb, verdict))
    exists = cur.fetchone()
    if exists:
        print('  (experimento ja registrado; apenas atualiza hipotese)')
        eid = None
    else:
        cur.execute("""
            INSERT INTO experiments (agent_a, agent_b, seeds, wins_a, wins_b, ties,
                                     mean_d, json_path, git_sha, axis, verdict, notes)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id
        """, (args.candidate, args.champion, None, wa, wb, ties, mean_d,
              ';'.join(args.jsons), sha, args.axis, verdict, args.notes))
        eid = cur.fetchone()[0]
        print(f'  experiment id={eid} gravado ({verdict})')

    if args.hypothesis_id:
        hstatus = 'suportada' if verdict == 'campeao' else ('rejeitada' if verdict == 'refutado' else 'testando')
        cur.execute("UPDATE hypotheses SET status=%s, experiment_id=%s WHERE id=%s",
                    (hstatus, eid, args.hypothesis_id))
        print(f'  hipotese {args.hypothesis_id} -> {hstatus}')

    conn.commit()
    cur.close()
    conn.close()
    return 0 if verdict == 'campeao' else (1 if verdict == 'refutado' else 2)


if __name__ == '__main__':
    sys.exit(main())
