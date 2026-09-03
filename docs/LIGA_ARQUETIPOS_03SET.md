# Liga de Arquétipos + Teste Anti-Resubmit — 03/09/2026

> Objetivo: entender por que o h2h local (reward) não traduz em ELO no ladder.
> O v19 ganha 62% do v18 no mirror, mas o ELO fica estagnado ~1500-1560.

## Ferramentas novas

| Arquivo | Papel |
|---|---|
| `league_game.py` | Worker: joga UMA partida (2 agentes, 1 seed) e imprime JSON. |
| `league_bench.py` | Driver da liga: roda cada jogo em subprocesso com timeout (90s) — jogo travado vira BAD e não derruba a liga; elimina contaminação de estado module-level entre jogos. |
| `elo_track.py` | Monitor do teste anti-resubmit: registra (ts, sub_date, elo) do hybrid_v19 mais recente em `results/elo_track_v19.csv`. Nunca submete. |

## Resultado da liga (v19 = campeão, seeds 1-6 × 2 lados)

| vs arquétipo | W-L-T | winrate | mean Δ reward |
|---|---|---|---|
| v18 (sell-adapt prev) | 1-3-8 | 8% | −7 |
| moon_v56 (mesma família) | 12-0 | 100% | +3.208 |
| soil_v19 (rota modal) | 10-2 | 83% | +9.937 |
| mix_single (market-flow) | 12-0 | 100% | +21.309 |
| c27 (clone front-run) | 12-0 | 100% | +23.507 |
| purearch (baseline fita) | 12-0 | 100% | +20.603 |
| trace_10c4s | 12-0 | 100% | +20.608 |

**Expansão v19 × v18 (seeds 1-24, 48 jogos): 18-10-20, mean +28.**
Nos não-empates o v19 vence ~64% — vantagem real sobre o v18, mas pequena e
dominada por empates exatos (produção idêntica; difere só o timing de venda).

## Paradoxo

O v19 esmaga localmente agentes que correspondem a ELO ~2800-2900 no ladder
(soil_v19, moon_v56), mas está em ~1550. **Conclusão: o h2h local (reward) NÃO
prediz ELO.** O gargalo não é "contra qual arquétipo perder" — é a dinâmica do
ladder (matchmaking perto do rating atual + convergência de submissões novas).

## Teste anti-resubmit (em andamento)

- **Hipótese** (baseada em análise empírica do Ryo): submissões novas começam em
  ~600 ELO e convergem ao longo de dezenas de partidas. A rotina de resubmit
  (a cada 12h, quando ELO < 2200 = sempre) resetava o rating antes de convergir,
  prendendo o ELO no platô ~1500.
- **Ação**: cron `kaggriculture-hybridv19-resubmit` REMOVIDO. Submissão v19 de
  09-03 11:28 deixada em paz (baseline ELO **1553.9**).
- **Monitor**: `kaggriculture-elo-monitor` (a cada 4h) roda `elo_track.py`, nunca
  submete, e notifica o Gui se ELO subir ≥ +40 (convergência confirmada) ou se
  surgir submissão nova (teste comprometido).
- **Decisão**: revisar a trajetória em 24-48h; se subir sozinho → política
  "submete 1x e deixa convergir"; se estagnar → o platô é o teto real do v19.

## Critério de validação para mudanças futuras

- H2H mirror sozinho NÃO basta (best-response à própria família).
- Usar **liga de arquétipos** (mirror + painel diverso) sem regressão por arquétipo.
