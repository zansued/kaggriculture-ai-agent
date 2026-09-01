# Plano de Sprints — Nova Economia na Base (Projeto Estrutural)

> 01/09/2026. Objetivo: construir uma NOVA base (não o Moon) que supere o v19
> (~77-88k reward) e chegue ao nível dos tops (~92k+). Alto risco/retorno.
> Diferente dos overlays (esgotados, ~45 refutações), isto é construir do zero.

## Por que nova base?
- O Moon (fita fixa) atingiu teto estrutural. Todos os patches falharam.
- O gap (~12-15k reward) é PRODUÇÃO: os tops rotacionam mais rápido e produzem
  mais por tile.
- Uma base nova com **coordenador de zonas** pode escalar onde o Moon não escala.

## Arquitetura-alvo: "ZC" (Zone Coordinator)
Em vez de fita pré-computada, um **coordenador por estado** com ZONAS dedicadas:
```
Cada hand = dono de uma zona (conjunto de tiles).
Ciclo por tile: WATER → HARVEST (maduro) → PLANT (replantar) → próximo tile.
Zonas disjuntas => sem colisão => coordenação simples e escalável.
```

### Economia-alvo (baseada nos tops)
| Componente | Papel |
|---|---|
| WHEAT rotacionado | Motor de volume (rotação rápida ~2x) |
| STRAWBERRY (limitada) | Premium (não crashar: ~20-28 tiles) |
| MELON (d0) | Pico cedo (colhe d10-12, tile vira wheat) |
| COW + SHEEP + GOOSE | Milk + Wool + Egg + FERT (rebanho ~14-17) |
| Vendas | glut-guard adaptativo por item (v19) |
| FERTILIZER | Usar p/ fertilizar APENAS se yield capturado (senão vender) |

## Sprints

### Sprint 0 — Fundação (arquitetura + ferramentas)
- [ ] Definir layout do grid (zonas por quadrante/tipo).
- [ ] `zc_core.py`: coordenador de zonas (hand decide por estado).
- [ ] `zc_zones.py`: gera zonas a partir de um layout alvo.
- **Entregável**: agente que coordena 100 tiles (wheat puro) e roda no engine.
- **Critério**: reward > 20k no seed 1 (wheat puro é baixo, mas prova coordenação).

### Sprint 1 — Motor de wheat (rotação rápida)
- [ ] Ciclo wheat por tile: PLANT → WATER → HARVEST(age≥2) → replant IMEDIATO.
- [ ] Rega/fertilização ótima (watered+fertilized = +2 yield/dia).
- [ ] Venda adaptativa de wheat (v19 glut-guard estendido a wheat).
- **Entregável**: base ZC com wheat rotacionado em 100 tiles.
- **Critério**: reward > 12k no seed 1 (wheat puro; referência: wheat_cell 5.4k);
  produção de wheat > 1500 unidades.

### Sprint 2 — Premium crops (strawberry + melon)
- [ ] Melon d0 (pico d10-12), tile vira wheat após colheita.
- [ ] Strawberry limitada (20-28 tiles, pico d15-16).
- [ ] Vendas adaptativas por item (v19).
- **Critério**: reward > 60k no seed 1.

### Sprint 3 — Rebanho (COW + SHEEP + GOOSE)
- [ ] Pastagens/coops, cadeia PICKUP→PLACE, FEED diário.
- [ ] COW (milk) + SHEEP (wool) + GOOSE (egg).
- [ ] Fert dos animais: usar OU vender (trade-off).
- **Critério**: reward > 75k no seed 1; rebanho produtivo estável.

### Sprint 4 — Adaptatividade integrada
- [ ] Plantio ao preço projetado (na base, não overlay).
- [ ] Rebanho adaptativo (mais COW se MILK caro).
- [ ] Vendas adaptativas finas (v19 + novas dimensões).
- **Critério**: reward > 85k no seed 1; h2h > v19 (W/L > 50%).

### Sprint 5 — Validação e submissão
- [ ] h2h vs v19 (144 jogos, 2 lados): W/L > 50%.
- [ ] Seeds de referência: 507467650, 1017826910, 2011797993.
- [ ] Otimização (velocidade: < 1s/ação).
- [ ] Submeter como novo campeão.

## Ferramentas
```
zc_core.py      # coordenador de zonas (hand decide por estado)
zc_zones.py     # gera zonas (tiles por hand)
zc_layout.py    # define o layout alvo (onde cada crop/animal)
build_zc.py     # embute o ZC como bundle single-file
sweep_zc.py     # validação paramétrica
```

## Riscos
- Coordenador reativo pode ser LENTO no ladder → otimizar (menos checks).
- Zonas podem conflitar com a dinâmica do jogo → zonas disjuntas + guards.
- Economia pode não pagar os custos (animais, seeds) → validar margem cedo.

## Metas
- Reward: 77k (v19) → 85k (Sprint 4) → 92k+ (tops).
- ELO: ~1600 → >2000 (passo) → >2850 (top 10).
