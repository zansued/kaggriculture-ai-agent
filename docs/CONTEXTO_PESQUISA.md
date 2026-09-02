# Contexto Exaustivo para Pesquisa — Kaggriculture (Top 10)

> Gerado em 02/09/2026. Objetivo: consolidar TODO o conhecimento para você
> pesquisar profundamente (fórum Kaggle, replays, mecânica, estratégia dos tops).

---

## 1. A Competição

- **Nome**: Kaggriculture (Kaggle, competição 147734). $50k, deadline 23/09/2026.
- **Formato**: 2 agentes autônomos jogam uma fazenda 10x10 (100 tiles, 4 quadrantes
  de 5x5), com crops, animais, mão de obra (farmer + hands) e mercado dinâmico.
- **Ladder**: ELO. Submissões (5/dia). Apenas as 2 mais recentes contam para o ranking.
- **Objetivo**: maximizar o ELO (W/L), NÃO o reward absoluto.
- **Premissa-chave**: o preço de cada item depende das vendas dos DOIS jogadores.
  "Extrair mais valor que o oponente dadas as mesmas condições de preço."

## 2. Mecânica do Jogo (engine kaggle_environments 1.32.x)

### Crops
| Crop | Semente$ | Maturação | Yield máx | Colheita | Mercado T |
|---|---|---|---|---|---|
| WHEAT | 10 | d4 | 6 | única | 400 (profundo) |
| CARROT | 20 | d3 | 4 | única | 450 |
| TOMATO | 50 | d8 | 4 | contínua (1d) | 200 |
| STRAWBERRY | 100 | d10 | 4 | contínua (2d) | 100 (crasha) |
| MELON | 80 | d12 | 6 | única | 300 |

### Animais
| Animal | $ | 1ª prod | Intervalo | Produto | Preço base |
|---|---|---|---|---|---|
| GOOSE | 300 | d4 | 1d | EGG | 50 |
| COW | 400 | d8 | 2d | MILK | 160 (pico ~206) |
| SHEEP | 500 | d6 | 3d | WOOL | 200 (recupera ~184 d27) |

### Mecânicas-chave
- **WATER**: +1 yield/dia na janela de crescimento. Fertilizado+regado = **+2 yield/dia**.
- **FERTILIZE**: tile PLANT, consome 1 fert do inventário do unit, ativo 3 dias.
- **2 dias sem rega** => planta vira WEED. **2 dias sem feed** => animal foge.
- **Shed**: capacidade 100. Itens não vendidos no fim do dia vão pro shed (overflow descarta).
- **HIRE**: custo fib (1,1,2,3,5,8,13...). Hands resetam a cada dia (recontratar).
- **Mercado**: preço = f(base, inventário). Cada produto tem `T` (capacidade antes de crashar).
- **BUY_PRODUCT**: só WHEAT e FERTILIZER são compráveis de volta.

## 3. Nossa Arquitetura (base Moon + overlays)

- **Moon V56** (código público ~2736-2913 ELO): agente base com **fitas pré-computadas**
  de 719 ações (uma por step) + cascata de overlays/guards.
- **Fitas**: `_ACTIONS_10C4S_3Q`, `_8C6S_3Q`, `_6C8S_3Q`, `_6C12S_4Q_FIRST/SECOND_YARN`
  (escolhida pelas lojas da cidade). Fita default 10c4s usa 277 HIRE, 10 COW + 4 SHEEP.
- **Overlays**: aplicados DEPOIS da fita (market e algumas ações).
- Documentação: `docs/KAWA_MOON_MAP.md`.

## 4. Nossa Evolução (v6 → v19)

| Agente | Mudança | Validação |
|---|---|---|
| v6 | Moon + front-run + sell_first + glut-guard fixo | campeão por muito tempo |
| v17 | GOOSE expandido (1+ loja EGG) | 57W-37L vs v6 (144 jogos) |
| v18 | **glut-guard ADAPTATIVO** (média recente + momentum + fracionado) | 124-20 vs v17 (86%) |
| v19 | **glut-guard POR ITEM** (MELON/MILK/WOOL/STRAWB com parâmetros próprios) | 57-35 vs v18 (62%) |

- **v19 é o campeão atual** (build_hybrid_v19.py). ELO ~1608 no ladder.
- Cadeia de overlays: mature_opp_front_run → sell_first → glut_guard adaptativo.

## 5. O que os TOPS fazem (docs/TOPS_ADAPTIVE_27AGO.md)

Análise de replays reais (ranks 1-5: Crop Dusta, Ryo, tetsuya, Blu3s):
1. **Front-run MELON/STRAWBERRY** (vender antes do crash).
2. **Rebanho COW é o motor** (10-12 COW, MILK o jogo todo).
3. **Compra WHEAT no mercado** (BUY_PRODUCT d0-13) para FEED — permite rebanho maior.
4. **HIRE agressivo** (591-602 vs nossos 277).
5. **Vendas FRACIONADAS** (lotes 3-16, 10-40×/dia).
6. **FERTILIZER dump cedo** (preço alto ~100→30).
7. **CARROT tardio** (d15-26, 35→56) e **TOMATO** (d21-24, 60→147).
8. **GOOSE/EGG** (Crop Dusta).
9. **Adaptatividade** (reagem ao preço real da partida).

**O Moon v19 JÁ TEM**: 10 COW, BUY_WHEAT 487, HIRE 277, vendas fracionadas, GOOSE,
adaptatividade de venda. **O que falta é PRODUÇÃO por tile.**

## 6. O que TESTAMOS E REFUTAMOS (~52 abordagens)

### Overlays de VENDA (no glut-guard / sell)
| Abordagem | Resultado |
|---|---|
| glut-guard fixo (v5/v6) | ✅ base |
| dump global 0.40, janela 250-650 | ✅ v4 |
| dump_floor por item 0.45/0.40 | ✅ v5 |
| glut-guard adaptativo (média+momentum) | ✅ v18 (124-20) |
| glut-guard por item (parâmetros próprios) | ✅ v19 (57-35) |
| v13 piso adaptativo ao pico | ❌ 19-21-32 |
| v14 venda fracionada extra | ❌ 2-6 |
| v20 janelas curtas | ❌ 54.3% marginal |
| peak (referência = pico) | ❌ 47.1% W/L negativo |
| v21 overlays de market (wheat lote + fert gate) | ❌ 0-18 |
| adaptar grãos (WHEAT/CARROT/TOMATO) | ❌ 0-24 |
| ordem de venda por preço relativo | ❌ 0-24 |

### Overlays de PRODUÇÃO
| Abordagem | Resultado |
|---|---|
| v15 compra WHEAT cedo | ❌ 1-7 |
| v19 BUY WHEAT cedo (de casa) | ❌ 3-2-31 |
| v20 TOMATO tardio (de casa) | ❌ 0-36 |
| strawb→wheat (overlay e fita) | ❌ 0-12 / 1-6 |
| CARROT/TOMATO tardio | ❌ 2-10 |
| plantio adaptativo ao preço | ❌ 2-5 |
| PASS→FERTILIZE (v6 e v19) | ❌ -31k / 2-9 |
| fert_farm (fertilizar) | ❌ 0-12 |
| fert_dampen (parar venda fert) | ❌ 1-11 (enche shed) |
| replantio imediato (PASS→PLANT) | ❌ 1-8 |
| wheat_arb (comprar barato revender) | ❌ 2-2 neutro |
| buy_land3 (mais terra) | ❌ 2-2 neutro |

### Estrutural / Coordenação
| Abordagem | Resultado |
|---|---|
| FarmBrain + terra/clone | ❌ 0-8 |
| Coordenador greedy (wheat_base_v0/v1/v2) | ❌ ~0-5k |
| wheat_cell (rotação pura) | ❌ 5.4k (teto baixo) |
| wheat_cell_v2 (+COW) | ❌ 3.1k |
| zc_core (coordenador de zonas do zero) | ❌ 44-2.1k (15x pior) |
| hybrid_expand (fita FarmBrain + NE) | ❌ ~2k |
| HIRE escalável (overlay/fita) | ❌ 0-12 (custo > produção) |
| transformações da fita Moon | ❌ todas (~10) |

## 7. O GAP REAL (por que não top 10)

- **Reward**: v19 ~77-88k nos seeds de referência. Tops ~92k (Crop Dusta até 125k).
- **Gap**: ~12-15k reward = ~1300 ELO.
- **Causa fundamental**: PRODUÇÃO POR TILE. Os tops rotacionam ~2x mais rápido
  (colhem cedo, replantam imediato) e produzem mais por tile.
- **O HIRE dos tops NÃO é a causa — é a CONSEQUÊNCIA** (eles produzem mais e pagam
  mais hands). Adicionar hands a nós (77k) não paga o custo.

## 8. PERGUNTAS DE PESQUISA ABERTAS (as mais importantes)

1. **Por que o h2h local não traduz em ELO?** (v19 62% vs v18 no mirror, mas ELO
   estagnado ~1608). O mirror é representativo? O campo evoluiu? Há viés?
2. **Como os tops produzem 2x mais por tile?** Qual a coreografia exata deles?
3. **Qual a "adaptatividade de PLANTIO" que os tops usam?** (não conseguimos via overlay).
4. **O fertilizante vale a pena em que contexto?** (no Moon, vendido vale mais;
   no CropDusta, usado vale mais — por quê?).
5. **Como escalar mão de obra sem quebrar a coordenação?** (overlays falham; os tops
   conseguem com 591 HIRE).
6. **Há uma economia diferente do Moon que renda 92k+?** (wheat-heavy puro falhou).

## 9. TÓPICOS PARA PESQUISAR EXTERNAMENTE

### No Fórum do Kaggle / Discussões da competição
- Procure posts dos TOP players (Crop Dusta = Rishi Gottumukkala, Ryo Hasegawa).
- Busque: "kaggriculture strategy", "kaggriculture agent", "kaggriculture wheat",
  "kaggriculture goose", "kaggriculture fertilizer".
- Veja se os tops publicaram notebooks/estratégias.

### Mecânica e teoria
- **Teoria de mercado do jogo**: como o preço reage a volume (curva por item).
- **Otimização de rotação**: colher cedo vs esperar max yield — qual rende mais?
- **Valor do fertilizante**: quando fertilizar paga (trade-off vs vender).
- **Escala de mão de obra**: como coordenar N hands sem fita pré-computada.
- **Adaptatividade em jogos**: técnicas de opponent modeling, market making.

### Código dos tops (se disponível)
- Procure o código de Crop Dusta/Ryo (podem ter publicado ou vazado).
- Busque no GitHub por "kaggriculture" + nomes.

### Replays
- Replays completos NÃO são baixáveis (anti-clonagem). Mas metadados (rewards, seeds)
  são obtíveis via GetEpisode. Seeds de referência: 507467650, 1017826910, 2011797993.

## 10. DADOS E ARQUIVOS RELEVANTES (no repo)

```
build_hybrid_v19.py            # CAMPEÃO (glut-guard por item)
build_hybrid_v18.py            # glut-guard adaptativo
build_hybrid_v17.py            # GOOSE expandido
research/public/moon_v17_goose.py  # base Moon (com GOOSE)
docs/KAWA_MOON_MAP.md          # arquitetura do Moon
docs/TOPS_ADAPTIVE_27AGO.md    # análise dos tops
docs/PLANO_TOP10.md            # plano estratégico
docs/SPRINTS.md                # plano de sprints (projeto estrutural)
docs/CONTEXTO_PESQUISA.md      # ESTE documento
sweep_v18_refinado.py          # harness de sweep do glut-guard
analyze_adaptive.py            # análise de replays
submissions/hybrid_v19/main.py # bundle do campeão
```

## 11. MÉTRICAS DE REFERÊNCIA (para testar novas ideias)

| Seed | Tops | v19 | Meta |
|---|---|---|---|
| 507467650 | CropDusta 125.3k | ~88.6k | >100k |
| 1017826910 | Ryo/CropDusta ~92k | ~77.7k | >85k |
| 2011797993 | Subramanya 75.6k | ~63.8k | >70k |

**Critério de aceite**: h2h vs v19 (24-36 seeds, 2 lados), W/L > 50%. Depois 144 jogos.
