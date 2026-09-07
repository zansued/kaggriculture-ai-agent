"""Memória estratégica: ROI científico por eixo.

Mostra, por eixo de pesquisa, quantos experimentos foram feitos e o ganho médio
dos que viraram campeões — para saber ONDE vale a pena gastar o próximo ciclo.

Uso:
    python roi.py                # tabela por eixo
    python roi.py --axis venda   # filtra um eixo
"""
from __future__ import annotations

import argparse
import sys

from db import get_conn


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--axis', default=None)
    args = ap.parse_args()

    where = ''
    params = ()
    if args.axis:
        where = 'WHERE axis = %s'
        params = (args.axis,)

    conn = get_conn()
    cur = conn.cursor()
    cur.execute(f"""
        SELECT COALESCE(axis,'(sem eixo)') AS axis,
               count(*) AS n,
               count(*) FILTER (WHERE verdict='campeao') AS campeoes,
               count(*) FILTER (WHERE verdict='refutado') AS refutados,
               round(avg(mean_d) FILTER (WHERE verdict='campeao'), 1) AS ganho_medio_campeao
        FROM experiments
        {where}
        GROUP BY 1
        ORDER BY campeoes DESC, n DESC
    """, params)
    rows = cur.fetchall()
    print(f"{'eixo':<22} {'n':>4} {'camp':>4} {'ref':>4} {'ganho_medio_camp':>16}")
    for axis, n, camp, ref, ganho in rows:
        g = f'{ganho:+.1f}' if ganho is not None else '-'
        print(f'{axis:<22} {n:>4} {camp:>4} {ref:>4} {g:>16}')
    cur.close()
    conn.close()
    return 0


if __name__ == '__main__':
    sys.exit(main())
