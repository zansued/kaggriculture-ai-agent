# v20_tps_cowphase — experimento (04/09)

Implementação parcial da rota do `PESQUISA_DEEP3_04SET.md`: clock robusto +
Tape-Preserving Transaction Splicer (crop) + Phase-Locked Cow Service.

## O que foi construído

- `src/clock_utils.py` — `logical_step = day*24 + hour` (fonte canônica) +
  `clock_safe()` para embrulhar agentes.
- **Fix de harness**: `h2h_bench.py` e `league_game.py` agora embrulham todo
  agente com `clock_safe`. **Confirmado empiricamente** que o kaggle-environments
  local (1.32.7) injeta `obs["step"]` SOMENTE no seat 0; o seat 1 não tem `step`
  (só `day/hour`). Como o Moon indexa `actions[step]`, o lado P1 de qualquer
  h2h/liga local Moon-derivado rodava `actions[0]` sempre → **resultados "2
  lados" históricos são clock-unverified**. Com o fix, P1 volta a executar a
  política correta.
- `build_hybrid_v20_tps_cowphase.py` → `submissions/hybrid_v20_tps_cowphase/main.py`
  = champion v19 (moon + market overlays intactos) + overlay posicional:
  1. CLOCK-0: injeta `obs["step"]` canônico antes de tudo (P0 e P1).
  2. Cow CARE: worker em PASS sobre COW ainda não cuidada → `["CARE"]`.
  3. TPS-crop: tile de WHEAT colhido HOJE (memória entre turns) com 2+ workers
     PASS co-localizados → PLANT (índice menor) + WATER (índice maior) no mesmo
     turno (água garantida antes do EOD; fecha day-slip sem MOVE, zero HIRE).
- `probe_tps.py` — telemetria de oportunidade (PASS slots, co-localização,
  cadência FEED/CARE de COWs, prod-eve unfed/uncared).

## Telemetria (seed 1, champion v19 vs purearch, 2 seats)

- Cow: Moon alimenta ~todos os dias e cuida em ~todos (P0: 21 dias, 20 cared;
  P1: 60 dias, 54 cared). Produtive-eve unfed = 0 nos dois seats; uncared = 0
  (P0) / 6 (P1).
- PASS slots sobre COW: 44 (P0) / 268 (P1). **PASS sobre COW não cuidada com
  fed_today=True = 0** → CARE injetado em PASS pré-feed NÃO banqueia (engine
  exige `fed AND cared` no EOD para +1 pending) → efeito econômico zero.
- Co-localização para transação H→P→W same-turn: rara (P0: 27 grupos, max 3;
  P1: 375, max 7). Tile de WHEAT colhido no dia + 2 PASS co-localizados = **0**
  nos seeds testados.
- `ripe_wheat_wasted` alto (564) mas supercontado (yield ainda pode crescer;
  Moon não colhe antes do cap).

## Resultado

- **v20 ≡ v19 comportamentalmente** em seeds 1-6 (h2h 2 lados: rewards idênticos,
  0-1-5 e 0-1-5 simétricos). Nenhuma regressão — e nenhum ganho.
- **Conclusão**: o champion v19 NÃO tem a folga de "slots PASS semanticamente
  no-op sobre tiles produtivos" que a hipótese TPS previa — pelo menos não nas
  janelas observáveis (PASS pós-feed sobre COW e co-locação pós-colheita de
  WHEAT). A alavanca animal mais provável passa a ser a P3 do doc: **reduzir o
  FEED diário redundante** do Moon (que alimenta COW todo dia, quando a mecânica
  tolera 1 noite sem feed e a paridade de produção é 2 dias), liberando WHEAT, e
  emparelhar FEED+CARE apenas na fase correta.

## Valor líquido desta rodada

1. Fix de relógio no harness (P0 real): todo h2h/liga local futuro é confiável
   nos 2 seats. Revalidar canários-chave (v19 vs v18, mirror) sob clock correto.
2. Base `v20_tps_cowphase` segura (clock-safe) como ponto de partida para o
   próximo overlay — sem regressão vs v19.
3. Resultado negativo documentado: evita repetir a tentativa micro-splice.

Próximo passo recomendado: medir cadência real de FEED por COW por seed (probe já
coleta) e implementar **skip de FEED fora de fase** (off-parity) com safety
(consecutive_unfed < 2), testando primeiro em mecanístico.
