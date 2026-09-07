"""Registro de hipóteses do Scientist (tabela hypotheses).

Uso:
    python hypothesis.py add --statement "..." --axis producao --rationale "..."
    python hypothesis.py list
    python hypothesis.py status --id 3 --status testando
"""
from __future__ import annotations

import argparse
import sys

from db import get_conn


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest='cmd', required=True)

    a = sub.add_parser('add')
    a.add_argument('--statement', required=True)
    a.add_argument('--axis', default=None)
    a.add_argument('--rationale', default='')

    l = sub.add_parser('list')
    l.add_argument('--status', default=None)

    s = sub.add_parser('status')
    s.add_argument('--id', type=int, required=True)
    s.add_argument('--status', required=True, choices=['proposta', 'testando', 'suportada', 'rejeitada'])

    args = ap.parse_args()
    conn = get_conn()
    cur = conn.cursor()

    if args.cmd == 'add':
        cur.execute("""
            INSERT INTO hypotheses (statement, axis, rationale, status)
            VALUES (%s,%s,%s,'proposta') RETURNING id
        """, (args.statement, args.axis, args.rationale))
        hid = cur.fetchone()[0]
        print(f'hipotese id={hid} registrada (status=proposta)')

    elif args.cmd == 'list':
        where, params = '', ()
        if args.status:
            where, params = 'WHERE status=%s', (args.status,)
        cur.execute(f"""
            SELECT id, status, axis, left(statement,90)
            FROM hypotheses {where} ORDER BY id DESC LIMIT 30
        """, params)
        for hid, status, axis, st in cur.fetchall():
            print(f'{hid:>3} [{status:<9}] {str(axis or ""):<12} {st}')

    elif args.cmd == 'status':
        cur.execute("UPDATE hypotheses SET status=%s WHERE id=%s", (args.status, args.id))
        print(f'hipotese {args.id}: status={args.status}')

    conn.commit()
    cur.close()
    conn.close()
    return 0


if __name__ == '__main__':
    sys.exit(main())
