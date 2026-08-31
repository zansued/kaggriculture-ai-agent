# Arquitetura da Re-coreografia — HIRE Escalável (Fase D)

> 31/08/2026. Projeto: adicionar hands à fita Moon (277 → ~550 HIRE) para fechar
> o gap de produção (~12-15k reward) vs tops. Overlays REPROVADOS (quebram a
> coordenação). A re-coreografia é uma re-escrita da coreografia de mão de obra.

## 1. Diagnóstico (por que mais hands)

- **Moon atual**: 277 HIRE, ~8-12 hands/dia, terra 100% ocupada (36 wheat + 42
  strawb + 12 melon + 14 animais).
- **Tops**: 591-602 HIRE, 10-15 hands/dia.
- **O que mais hands fazem nos tops**: COLHER mais cedo + REPLANTAR mais rápido
  (rotação ~2x) + alimentar/coletar mais. NÃO plantam em mais terra (cheia) nem
  regam mais (já regam tudo).
- **Gap medido**: ~12-15k reward nos seeds de referência = produção menor por
  rotação mais lenta.

## 2. Abordagem (não é overlay — é re-escrita)

Criar uma **nova fita** (ex: `_ACTIONS_14H_3Q`) com a MESMA economia do v18, mas
com **mais hands e ciclo de produção mais denso**. A fita é o artefato central.

### Princípio: ZONAS DEDICADAS por hand
Cada hand é dono de uma zona (conjunto de tiles) e executa um ciclo nela:
```
WATER → HARVEST (maduro) → PLANT (replantar) → próximo tile da zona
```
Zonas não se sobrepõem → sem colisão de posições → coordenação simples.

### Alocação-alvo (por dia)
| Fase | Hands | Foco |
|---|---|---|
| d0-3 (setup) | 6 | pastagens, animais, plantio inicial |
| d4-8 (crescimento) | 10 | rega + colheita + replantio |
| d9-20 (pico) | 13 | colheita/replantio rápido (rotação 2x) |
| d21-29 (fim) | 11 | colheita final + vendas |

## 3. Passos de implementação

### Passo 1 — Mapear a coreografia atual
- Simular a fita 10c4s e extrair, por step: posição de cada hand, ação, tile sob
  cada hand.
- Identificar a "cobertura": tiles que ficam MADUROS mas não colhidos por N steps
  (atraso de colheita), e tiles VAGOS pós-colheita por N steps (atraso de replantio).
- → São os GAPS que os hands extras vão fechar.

### Passo 2 — Definir as zonas dos hands extras
- Dividir o grid (100 tiles) em 13 zonas (uma por hand).
- Zonas de crops: NW/NW2/NE/NE2/SW/SE (wheat + strawb + melon).
- Zonas de animais: pastagens + coops (FEED + COLLECT_FERT + HARVEST animal).
- Cada zona = lista ordenada de tiles.

### Passo 3 — Gerador de coreografia (script `gen_coreografia.py`)
- Para cada step, cada hand executa na sua zona:
  1. Se tile atual é PLANT maduro (age>=2, yield>0, regado) → HARVEST.
  2. Se tile atual é vazio e semente disponível → PLANT (crop da zona).
  3. Se tile atual é PLANT não regado → WATER.
  4. Senão → move para o próximo tile da zona (ordem serpentina).
- Animais: FEED se não alimentado, COLLECT_FERT, HARVEST produto, CARE.
- Mercado: HIRE (rampa), BUY_SEED, BUY_PRODUCT, SELL (reuso do v18).

### Passo 4 — Gerar a nova fita
- O gerador produz a lista de 719 ações (uma por step) com N hands.
- Embutir como nova fita no `moon_v17_goose.py` (ou num módulo novo).
- O `agent` aplica os overlays do v18 (front-run, sell_first, glut_guard adaptativo)
  por cima.

### Passo 5 — Validar (critério rígido)
- h2h vs v18 (24-36 seeds, 2 lados): SÓ integra se W/L > 50%.
- Se passar: validar 144 jogos (como v18).
- Seeds de referência: 507467650, 1017826910, 2011797993.
- Submeter apenas validado.

## 4. Estrutura de arquivos (proposta)
```
gen_coreografia.py      # gerador da fita 14h (zona por hand)
gen_zones.py            # define zonas (tiles por hand) a partir da fita atual
research/public/moon_14h.py  # nova base Moon com fita 14h (embutida)
build_hybrid_v19.py     # v19 = moon_14h + overlays v18 (front-run, sell_first, glut adaptativo)
sweep_coreografia.py    # validação paramétrica (n_hands, rampa, zonas)
```

## 5. Riscos e mitigação
| Risco | Mitigação |
|---|---|
| Custo de HIRE (fib) drena dinheiro | Rampa gradual; validar margem no h2h |
| Colisão de posições | Zonas disjuntas (hand não sai da zona) |
| Rega duplicada (2 hands no mesmo tile) | Cada tile pertence a 1 zona |
| Fita nova desbalanceada (produção > demanda) | Comparar reward/ELO vs v18; ajustar mix |
| Fita nova não generaliza entre seeds | Guardas (como o Moon): manter weed_repair/feed_guard |

## 6. Critério de sucesso (meta)
- v19 h2h > v18 (W/L > 50%) → v19 é o novo campeão.
- Reward nos seeds de referência: aproximar de 92k (1017826910) e 75.6k (2011797993).
- ELO: subir de ~1618 → > 2000 (passo), depois > 2850 (top 10).

## 7. Timeline estimada
- Passo 1 (mapear cobertura): 1-2h.
- Passos 2-3 (gerador de coreografia): 3-6h.
- Passo 4-5 (gerar fita + validar): 2-4h (iterativo).
- Total: ~2-3 dias de trabalho focado.

## Nota: por que não overlay
Overlays de HIRE/movimento falham porque operam DEPOIS da fita (não conseguem
re-posicionar hands sem conflitar com a coreografia existente). A fita nova é a
única forma de coordenar N hands desde o planejamento.

## Resultado do Passo 3 (31/08) — Fase D ENCERRADA
- gen_coreografia.py: hands extras de zona (colheita) + HIRE rampa.
  - Extras índices 8-12: 0-24 (sobrepôs hands da fita).
  - Extras índices 13+: 0-24 (mean -127.714) — reward NEGATIVO.
- CAUSA: custo de HIRE (fib até 14 hands ~$986/dia) > produção extra da colheita.
- DESCOBERTA: o HIRE dos tops (591) é CONSEQUÊNCIA da maior produção (~92k reward),
  não a causa. Nós (~77k) não pagamos o HIRE extra.
- CONCLUSÃO: Fase D (HIRE) economicamente inviável no estado atual. A evolução
  real é PRODUÇÃO POR TILE (rotação + adaptatividade), já parcialmente no v18.
- v18 permanece o campeão.
