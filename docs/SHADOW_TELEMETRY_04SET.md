# Shadow Interpreter — telemetria do Moon (04/09)

Fase de telemetria do PESQUISA_DEEP3 sem alterar política: classificar cada
comando do champion v19 como MOVE / PASS / USEFUL / NOOP replicando as regras de
no-op do engine, e medir day-slip / WATER-HARVEST desperdiçados.

Ferramenta: `shadow_telemetry.py` (usa o champion `submissions/hybrid_v19/main.py`
contra purearch, seats P0 e P1, clock-safe).

## Resultado (seeds 1-6, ~4.314 steps / ~41.5k unit-commands por seat)

| Métrica | P0 | P1 |
|---|---|---|
| units (comandos de worker) | 41.484 | 41.484 |
| MOVE | 21.574 | 21.573 |
| PASS | 3.321 | 3.320 |
| non-MOVE classificados | 16.589 | 16.591 |
| **USEFUL** | 14.757 | 14.790 |
| **NOOP (silent)** | **177 (1.1%)** | **146 (0.9%)** |
| UNCLASSIFIED (PICKUP/PLACE/DROP/BUILD…) | 1.655 | 1.655 |
| NOOP por tipo | water 54 · harvest 43 · dig 62 · plant 8 · feed 5 · fert 3 · care 2 | análogo |
| NOOP sobre tile produtivo | 89 | 88 |
| **PASS sobre tile produtivo** | **2.824** | **2.835** |
| plant_without_water_eod | 2 | 0 |
| plant_water_same_day | 979 | 982 |
| harvest events | 2.360 | 2.369 |
| replant same-day (mesmo turno) | 872 | 880 |

## Leitura

1. **Silent no-ops são raros (~1%).** O Moon executa o plano com eficiência
   quase perfeita: WATER redundante, HARVEST sem yield, FEED/CARE impossíveis e
   PLANT bloqueado somam ~177 em ~16.6k comandos não-MOVE (6 seeds).
   A hipótese "semantic no-ops escondem muita capacidade" **não se confirma**
   nesta medição.
2. **PASS sobre tile produtivo é abundante (~2.830)** mas **não explorável**:
   são workers ociosos JÁ posicionados sobre planta/animal cujas obrigações do
   dia (WATER/FEED/CARE) já foram cumpridas. Não há mutação útil pendente para
   preencher o slot sem MOVE (e MOVE quebra a fita). Confirmam o "impasse de
   escala": a restrição é ESTRUTURA (nº de tiles produtivos/animais), não
   execução.
3. **Replant same-day** acontece em ~37% das colheitas; o restante fica para o
   dia seguinte (day-slip). Porém os workers não ficam co-localizados no tile
   recém-colhido (janela de splice gratuito = 0 nas seeds medidas) → fechar esse
   gap exige realocar mão de obra (MOVE) ou mais hands = o mesmo custo estrutural
   que já falhou (HIRE/re-coreografia).
4. `plant_without_water_eod` ≈ 0 → o Moon quase nunca planta sem garantir água
   no mesmo dia.

## Conclusão

O v19 não tem "gordura" de execução explorável por micro-transações. Qualquer
ganho real exige aumentar a capacidade produtiva (mais COWs/crops com a mesma
eficiência de execução), o que historicamente falhou via HIRE/re-coreografia
porque o custo (feed/hands) > produção marginal. Direção que resta: encontrar
uma forma de financiar/operar mais tiles produtivos com a ESTRUTURA DE CUSTO
certa (não overlay de HIRE), ou melhorias de market que só valem em subconjunto
de partidas (já explorado no v19 por-item).

Arquivo gerado: `shadow_telemetry.py`. Comandos UNCLASSIFIED (PICKUP/PLACE/DROP/
BUILD/FERTILIZE, ~10%) não foram modelados — tratados como potencialmente úteis,
portanto o noop real pode ser levemente maior, mas não o suficiente para mudar a
conclusão.
