# kaggle-brain v0 — Research Scientist toolkit

Ferramentas do ciclo científico (memória no `kaggle-meta-db`, VPS 147.79.87.117):

| Comando | Função |
|---|---|
| `collect/leaderboard.py` | snapshot top-100 → JSON + (cron) Postgres |
| `collect/episodes.py` | baixa replays dos top-10 (manifest) |
| `scientist/observer.py` | drift entre snapshots → top movers → `agent_runs` |
| `scientist/hypothesis.py` | registra/listar/marca hipóteses |
| `scientist/h2h.py` | parser robusto de JSONs h2h |
| `scientist/gate.py` | checklist Skeptic → campeão/refutado/inconclusivo |
| `scientist/finalize_experiment.py` | Runner→Gate→Learner: grava experimento + atualiza hipótese |
| `scientist/exp.py` | registra experimento manual |
| `scientist/roi.py` | ROI por eixo (memória estratégica) |
| `scientist/backfill_ingest.py` | ingere results/backfill_experiments.jsonl |

## Ciclo (Scientist loop v0)

```text
1. Observer:  python scientist/observer.py            # drift -> pergunta
2. Hipótese:  python scientist/hypothesis.py add --statement "..." --axis ...
3. Candidato: criar build_hybrid_vXX.py -> submissions/hybrid_vXX/main.py
4. H2H:       python h2h_bench.py CAND champion --seeds 1-24 --json ..._p0.json
              python h2h_bench.py champion CAND --seeds 1-24 --json ..._p1.json
              (candidato normalizado como 'a'; converter p1 se preciso)
5. Finalize:  python scientist/finalize_experiment.py --candidate X --champion hybrid_v19 \
                  --jsons ..._p0.json ..._p1.json --axis ... --hypothesis-id N
              -> gate aplica regras; grava experiments; marca hipótese suportada/rejeitada.
6. ROI:       python scientist/roi.py                  # aprende onde vale a pena
```

Regras do gate (Skeptic) — não mudar por conveniência:
n≥32 (2×24) · 2 posições · win_rate≥0.58 sobre não-empates · mean_d>0.
Sem essas 4 respostas SIM, o veredito é **inconclusivo**, nunca "campeão".

## Banco (kaggle-meta-db, 127.0.0.1:5433)
Tabelas: `leaderboard_snapshots`, `submissions`, `episodes`, `experiments`
(+`axis`/`notes`), `hypotheses`, `research_findings`, `agent_runs`.
Cron (host): snapshot 6h · observer 6h (min 5) · episodes 12h.
