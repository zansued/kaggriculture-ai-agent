# Plano Estrutural para o Top 10 — Kaggriculture

> 31/08/2026. Objetivo: elevar o v17 (ELO ~1550-1640) para o TOP 10 (~2850-3090).
> A lacuna (~1300-1500 ELO) NÃO é fechável por overlay (~29 refutações).
> Exige re-engenharia ESTRUTURAL da base Moon (como o v17 fez com GOOSE).

## Diagnóstico (docs/TOPS_ADAPTIVE_27AGO.md)

Os tops (Crop Dusta, Ryo, tetsuya, Blu3s) são **ADAPTATIVOS**: extraem mais valor
do MESMO preço de partida reagindo em tempo real. Nosso v17 = fita fixa 719-ações
+ overlays. O teto da fita fixa está atingido.

## 5 mudanças estruturais (por impacto/risco)

### Fase A — Rebanho COW grande + compra de WHEAT (MAIOR alavanca)
- **O que**: elevar COW para 10-12 + comprar WHEAT (BUY_PRODUCT) d0-13 para feed,
  permitindo rebanho maior sem plantar tanto WHEAT. Padrão de TODOS os tops.
- **Por que**: MILK é o motor (preço alto, demanda). Mais COW = mais MILK = mais
  receita estável. WHEAT comprado é mais barato que o plantio (libera tiles/hands).
- **Como**: modificar `research/public/moon_v17_goose.py`:
  - Fita: +BUY_ANIMAL COW (até 10-12), pastagens extras.
  - Market: BUY_PRODUCT WHEAT quando money alto e preço WHEAT baixo.
  - Fita: redistribuir plantio (menos WHEAT plantado, mais COW).
- **Risco**: médio. Mexe no equilíbrio da fita (como o v17 GOOSE).
- **Validação**: h2h vs v17 (24-36 seeds, 2 lados). Critério: W/L > 50%.

### Fase B — Adaptatividade de venda (base dinâmica + momentum) NA BASE
- **O que**: substituir o glut-guard FIXO por decisão baseada na série de preços
  real da partida (média recente + momentum). O overlay adaptativo deu 5-7 vs v17
  (quase neutro); NA BASE integrado pode render mais (o overlay pós-processa tarde).
- **Como**: na base, o agente mantém histórico de preços e decide dump/hold por item.
- **Risco**: médio.

### Fase C — Vendas fracionadas
- **O que**: vender em lotes de 3-16 (10-40×/dia) em vez de bloco — suaviza o impacto
  no preço (não crasha o mercado). Padrão dos tops.
- **Como**: na base, SELL em frações do shed ao longo do dia.
- **Risco**: baixo-médio.

### Fase D — HIRE escalável na base
- **O que**: contratar 10-15 hands/dia conforme a produção (o Moon usa ~8-12 na fita;
  os tops 10-15). Overlay de HIRE quebra (143k→6.5k); NA FITA integrado não.
- **Como**: modificar a fita para mais HIRE + ações para os hands extras.
- **Risco**: médio (overlay quebrou; na fita é estrutural).

### Fase E — CARROT/TOMATO tardio
- **O que**: plantar CARROT (d15-26) e TOMATO (d20-24) em tiles liberados pós-colheita
  para vender no fim (CARROT 35→56, TOMATO 60→147). Overlay reprovou (2-10); na fita
  integrado pode render.
- **Como**: fita +PLANT CARROT/TOMATO nos dias finais.
- **Risco**: médio.

## Metodologia (igual ao v17)
1. Modificar `research/public/moon_v17_goose.py` (a base).
2. `python build_hybrid_vN.py` → bundle.
3. h2h vs v17 (2 lados, 24-36 seeds): SÓ integra se W/L > 50%.
4. Submeter apenas validado.

## Critério de sucesso
- h2h > v17 em W/L (o v17 é o campeão atual).
- Seeds de referência: 507467650, 1017826910, 2011797993.
- Meta ELO: > 2500 (próximo passo), depois > 2850 (top 10).
