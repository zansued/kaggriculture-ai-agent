# Plano Estrutural para o Top 10 — Kaggriculture

> 31/08/2026. Objetivo: elevar o v17 (ELO ~1550-1640) para o TOP 10 (~2850-3090).
> A lacuna (~1300-1500 ELO) NÃO é fechável por overlay (~29 refutações).
> Exige re-engenharia ESTRUTURAL da base Moon (como o v17 fez com GOOSE).

## Diagnóstico (docs/TOPS_ADAPTIVE_27AGO.md)

Os tops (Crop Dusta, Ryo, tetsuya, Blu3s) são **ADAPTATIVOS**: extraem mais valor
do MESMO preço de partida reagindo em tempo real. Nosso v17 = fita fixa 719-ações
+ overlays. O teto da fita fixa está atingido.

## 5 mudanças estruturais (por impacto/risco)

### DIAGNÓSTICO REFINADO (31/08): o Moon JÁ tem os padrões dos tops
Análise da fita 10c4s do v17: **10 COW** + 4 SHEEP, **BUY_PRODUCT WHEAT 487**,
**HIRE 277**, **482 ordens SELL** (fracionado), SELL WHEAT 856 / FERT 2932 / MILK 279.
⇒ Rebanho grande, compra de WHEAT, HIRE e vendas fracionadas JÁ existem na fita.
**A lacuna real é ADAPTATIVIDADE** (reagir ao preço real da partida), não produção.

### Fase A — ADAPTATIVIDADE de venda NA BASE (agora a MAIOR alavanca)
- **O que**: substituir o glut-guard FIXO (base estática) por decisão baseada na
  série de preços REAL da partida (média recente + momentum + piso dinâmico).
  O overlay adaptativo deu 5-7 vs v17 (quase neutro) porque pós-processa tarde e
  não influencia o plantio. NA BASE integrado decide vendas com histórico completo.
- **Como**: modificar `research/public/moon_v17_goose.py`:
  - Manter histórico de preços por item no estado do agente.
  - O _glut_guard (embutido) usa base dinâmica (média recente) + momentum:
    momentum negativo => vender antes do crash; positivo => segurar p/ pico.
  - Vender em FRAÇÕES (lotes 3-16) como os tops, não dump em bloco.
- **Risco**: médio. Mexe na lógica de venda da base (não na fita de produção).
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

## Resultado 31/08 (Fases testadas)
- **Fase B (adaptatividade venda)**: ✅ FEITO no v18 (124-20 vs v17, 86%). NOVO CAMPEÃO.
- **Fase E (CARROT/TOMATO tardio)**: ❌ INVIÁVEL — v17/v18 usam toda a terra (só 2 tiles
  vazios d15-26). Overlay de plantio tardio 2-10; plantio adaptativo ao preço 2-5.
- **Fase D (HIRE escalável via overlay)**: ❌ 0-12 (mean -61.492) — overlay quebra a
  coordenação (hands extras indistinguíveis; HIRE drena dinheiro). Confirmado o doc:
  HIRE só funciona RE-COREOGRAFANDO a fita (projeto grande).
- **Gap real do v18 vs tops**: ~12-15k reward (seeds 1017826910, 2011797993) = ~1300 ELO.
  A diferença é PRODUÇÃO (tops usam 591-602 HIRE vs nossos 277) — a Fase D real é
  re-coreografia da fita (dias de engenharia).

## Fase D (31/08, iterações) — overlay definitivamente inviável
- manager_v1 (HIRE 12 + mexer em todos PASS): 0-12 (mean -61.492).
- manager_v2 (HIRE 10 + só hands no shed): 0-12 (mean -87.785).
- Transformação fita PASS->WATER (29 casos): 2-2 (neutro).
- CONCLUSÃO: HIRE escalável exige RE-COREOGRAFAR a fita (projeto de engenharia,
  dias). Qualquer overlay de HIRE/movimento quebra a coordenação. v18 permanece
  campeão; Fase D fica como projeto dedicado.

## 01/09 — glut-guard adaptativo esgotado (v19 é o ótimo)
- v19 (média + parâmetros por item): campeão (62% vs v18, mean +22, 144 jogos).
- v20 (janelas curtas): 50-42 vs v19 (54.3%, mean +1) — MARGINAL, não robusto.
- peak (referência = pico recente): 32-36 vs v19 (47.1%, mean +45) — ganha margem
  mas perde frequência => ELO negativo.
- CONCLUSÃO: venda adaptativa chegou ao limite. Próxima dimensão = PRODUÇÃO
  (plantio ao preço / fertilização adaptativa) NA BASE, não overlay.
