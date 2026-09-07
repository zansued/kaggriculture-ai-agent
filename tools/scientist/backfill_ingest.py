"""Ingere results/backfill_experiments.jsonl na tabela experiments.

Dedupe: pula linha que já exista com mesmo (agent_a, agent_b, wins_a, wins_b,
verdict) — protege contra re-inserir a revalidação v19 39-9 (experiment id=1).

Uso (na VPS, onde o DB é alcançável):
    python tools/scientist/backfill_ingest.py [--path results/backfill_experiments.jsonl]
"""
from __future__ import annotations

import argparse
import json
import sys

from db import get_conn


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--path', default='results/backfill_experiments.jsonl')
    args = ap.parse_args()

    rows = [json.loads(l) for l in open(args.path, encoding='utf-8') if l.strip()]
    conn = get_conn()
    cur = conn.cursor()
    inserted = skipped = 0
    for r in rows:
        cur.execute("""
            SELECT 1 FROM experiments
            WHERE agent_a=%s AND agent_b IS NOT DISTINCT FROM %s
              AND wins_a IS NOT DISTINCT FROM %s AND wins_b IS NOT DISTINCT FROM %s
              AND verdict IS NOT DISTINCT FROM %s LIMIT 1
        """, (r.get('agent_a'), r.get('agent_b'), r.get('wins_a'), r.get('wins_b'), r.get('verdict')))
        if cur.fetchone():
            skipped += 1
            continue
        ties = r.get('ties')
        if ties is None and 'wins_a' in r:
            ties = 0
        source = r.get('source', '')
        notes = r.get('notes', '')
        if source:
            notes = f'{notes} [fonte: {source}]'
        cur.execute("""
            INSERT INTO experiments (agent_a, agent_b, seeds, wins_a, wins_b, ties,
                                     mean_d, git_sha, axis, verdict, notes)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (r.get('agent_a'), r.get('agent_b'), r.get('seeds'), r.get('wins_a'),
              r.get('wins_b'), ties, r.get('mean_d'), r.get('commit'), r.get('axis'),
              r.get('verdict'), notes))
        inserted += 1
    conn.commit()
    cur.close()
    conn.close()
    print(f'backfill: {inserted} inseridos, {skipped} pulados (dedupe), total no arquivo {len(rows)}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
