# Design da Base Wheat-Heavy (Fase 3)

> 26/08/2026. Objetivo: construir do zero uma rota coerente no estilo CropDusta
> que use **fertilização integrada** para multiplicar a produção de WHEAT.
> Fundamentado na mecânica real do engine (kaggriculture.py) e nas refutações
> empíricas da Fase 2.

## 1. Mecânica confirmada (engine 1.32.6 — kaggriculture.py)

### Crops
| Crop | seed$ | 1º yield | maturidade | colheita | max yield | mercado T |
|---|---|---|---|---|---|---|
| WHEAT | 10 | d2 | d4 | única | 6 | **400** (profundo, preço estável) |
| CARROT | 20 | d2 | d3 | única | 4 | 450 |
| TOMATO | 50 | d8 | d8 | contínua (1d) | 4 | 200 |
| STRAWBERRY | 100 | d10 | d10 | contínua (2d) | 4 | 100 (crasha rápido) |
| MELON | 80 | d10 | d12 | única | 6 | 300 |

### Animais
| Animal | $ | 1º prod | intervalo | max_held | produto | preço base |
|---|---|---|---|---|---|---|
| GOOSE | 300 | d4 | 1d | 4 | EGG | 50 |
| COW | 400 | d8 | 2d | 6 | MILK | 160 (pico ~206 d12-14) |
| SHEEP | 500 | d6 | 3d | 6 | WOOL | 200 (recupera ~184 d27) |

### Fertilizante — O DIFERENCIAL
- Animais geram **1 FERTILIZER/dia** (não acumula; precisa COLLECT_FERTILIZER).
- `FERTILIZE` (unit em cima de tile PLANT, consome 1 fert): `fertilized_until_day = day + 2` (ativo 3 dias).
- **Bônus (linha 787): tile REGADO E fertilizado → yield_units += 2/dia (vs +1)**.
- ⇒ **WHEAT fertilizado+regado atinge max 6y no d3 (ciclo de 3 dias) vs d4-5 sem fert.**
- ⇒ Rotação ~1.5-2× maior no mesmo tile. **Fertilizar é o multiplicador de produção.**

### Mercado (T = capacidade de 1 campo 5x5 em 24d sem fert)
- T alto = vende muito sem crashar. WHEAT T=400 ⇒ **único crop de escala real**.
- Strawberry T=100 e Milk T=122 ⇒ vendem pouco antes de crashar (picos curtos).
- WHEAT above_target 0.20 (queda suave) ⇒ glut de wheat é absorvido.

## 2. Economia por tile (30 dias, com rega ótima)

| Estratégia de tile | Ciclos | Yield total | Receita est. | Nota |
|---|---|---|---|---|
| WHEAT sem fert (v6) | ~6-7 | ~36-42y | ~$1300-1650 | matura d4-5 |
| **WHEAT fert+rega** | **~9-10** | **~54-60y** | **~$1900-2400** | matura d3, ciclo rápido |
| MELON d0 → WHEAT d12+ | 1 + 5 | 6 + 30 | ~$1500 + ~$1100 | tile liberado d10-12 |
| STRAWBERRY (ongoing) | contínua | ~44y | ~$5300-6600 | ocupa 30d, mas crasha cedo |

**Leitura:** strawberry é rei por tile MAS crasha rápido (todo mundo planta) e trava
o tile 30d. Wheat fert+rega é o motor de VOLUME estável. Melon é pico d10-12 e
depois libera o tile para wheat. **A base wheat-heavy combina os três.**

## 3. Composição-alvo

### Terra (100 tiles, 4 quadrantes)
- **WHEAT: 40-55 tiles ativos no pico** (d14-27), com fertilização e rotação
  contínua. É o motor — alvo ~220-300 plantios/temporada (vs 125 do Moon).
- **MELON: 12-20 no d0** (colhe d10-12, vende no pico ~$271, tile vira wheat).
- **STRAWBERRY: 20-28** (menos que o Moon 42; libera terra para wheat; colhe
  contínua até crashar ~d21, depois tile vira wheat se ainda valer).
- Shed central + pastagens/coops + 0 folga (tudo usado, como o Moon).

### Rebanho (produção de fert + produtos premium)
- **COW: 4-6** (milk pico d12-14, ~$206; poucas p/ não crashar o preço).
- **SHEEP: 8-13** (wool recupera d27 ~$184; vender no fim).
- **GOOSE: 0-2** (egg barato, margem baixa; opcional).
- O rebanho gera o **FERTILIZER** que alimenta a produção de wheat — o ciclo
  fecha: animais → fert → wheat fertilizado → caixa → mais terra/animais.

### Mão de obra
- 8-12 hands (custo fib) — o Moon usa 8-12. Rega + colheita + fertilização
  exigem cobertura; priorizar hands no d4-14 (pico de maturação do wheat).

## 4. Rota da temporada (esqueleto)

| Fase | Dias | Ações-chave |
|---|---|---|
| **Setup** | d0-3 | BUY_LAND (2-3 quadrantes), 4-6 COW + 8-10 SHEEP, 12-16 MELON d0, **14-20 WHEAT d0-2**, HIRE 8+ |
| **Crescimento** | d4-10 | **Replantar wheat a cada colheita (d3, d6, d9...)**, fertilizar tudo (usar TODO o fert), rega intensa, colher melon d10-12 |
| **Monetização** | d11-18 | **Vender excedente de wheat d11-14** (preço 36-40 = 1.44-1.6×base), melon no pico, milk no pico d12-14, strawberry d15-16 |
| **Escala** | d15-27 | Expandir wheat para 40-55 tiles, vender wheat continuamente (reserva de feed), wool no fim d27 (~184) |
| **Liquidação** | d28-29 | Vender tudo (wheat, wool, strawberry restante), NUNCA deixar estoque |

## 5. Diferenças deliberadas vs Moon (v6)

| Dimensão | Moon/v6 | Base wheat-heavy |
|---|---|---|
| Wheat plantios | 125 | **220-300** (rotação fert) |
| Venda de wheat | 856, 99% após d21 | **~1200-1800, contínua d11-27** |
| Fertilizante | vende 2935 (barato) | **usa tudo p/ fertilizar** |
| Strawberry | 42 | 20-28 |
| Melon | 12 | 12-20 |
| COW/SHEEP | 10/4 | 4-6/8-13 |
| BUY_LAND | 0-2 | **3 (4 quadrantes)** |

## 6. Estratégia de implementação — EVIDÊNCIA 26/08: requer ROTA NOVA

**Refutações empíricas de hoje (todas vs v6):**
| Abordagem | Resultado |
|---|---|
| Overlay `fert_dampen` (parar venda de fert barato) | ❌ 1-11 (enche shed) |
| Overlay `wheat_sell` (vender excedente cedo) | ⚖️ neutro (sem excedente) |
| Overlay `strawb2wheat` (trocar 50% strawb→wheat) | ❌ 0-12 (mean -12.780) |
| Overlay `wheat_arb` (comprar wheat barato) | ⚖️ neutro (v6 já arbitra) |
| Overlay `fert_farm` (fertilizar crops via substituição de ações) | ❌ 0-12 (mean -131.661) — quebra coordenação |
| **Transformação da FITA 10c4s** strawb→wheat 30% | ❌ 1-6 (mean -14.637) |
| Overlay `buy_land3` (mais terra cedo) | ⚖️ neutro (sem efeito) |

**Conclusão:** nem overlay nem modificação pontual da fita Moon alcançam a
economia wheat-heavy. O Moon é um ótimo local de coordenação rígida — qualquer
patch quebra ou é neutro. **A Fase 3 exige construir uma ROTA NOVA** (720 steps)
com a fertilização, o mix e o timing de venda integrados desde o design
(top-down), não como transformação sobre a Moon.

### Plano da rota nova
1. **build_wheat_base.py**: gera uma fita 720-step do zero, seguindo o esqueleto
   da seção 4, com:
   - Setup d0-3: BUY_LAND ×3, 4-6 COW + 8-13 SHEEP, 12-20 MELON, 14-20 WHEAT.
   - Loop de wheat fertilizado: PLANT → WATER → FERTILIZE → HARVEST → replant
     (ciclo ~3 dias), cobrindo 40-55 tiles no pico.
   - Vendas: wheat excedente d11-27 contínuo, melon d10-12, milk d12-14,
     strawberry d15-16, wool d27.
   - Fertilizante: TODO usado em FERTILIZE (nunca SELL barato).
2. **Validação iterativa**: a fita nova roda no engine desde o seed 1; medir
   produção de wheat, reward e sanidade (sem crop morto, sem animal fugido).
3. **h2h vs v6** (24-36 seeds, 2 lados): critério W/L > 0.5 E seed 507467650
   > 75.889.
4. Submissão só após validação; NUNCA submeter variação não validada.

### Ferramenta
`sweep_fase2.py` (repo) — harness de overlays + transformação de fita, já com
todas as hipóteses refutadas documentadas nos resultados h2h.

## 7. Métricas de sucesso
- h2h vs hybrid_v6 (24-36 seeds, 2 lados): base wheat-heavy vence em W/L.
- Seed 507467650: reward > 125.270 (batendo CropDusta) ou ao menos > 75.889.
- Produção de wheat no seed: > 1500 unidades (vs 856 do v6).
- Fertilizante vendido: < 500 (vs 2935 do v6) — sinal de que está sendo usado.
