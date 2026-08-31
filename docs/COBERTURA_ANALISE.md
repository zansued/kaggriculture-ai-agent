# Cobertura de mão de obra — v18 (Passo 1 da re-coreografia)

Simulação do v18 (seed 1, seat 0), rastreando por tile o ciclo
planta -> maduro -> colhido -> vazio -> replantado.

## Gaps
- **Atraso de COLHEITA: 523 tile-dias** (tiles maduros não colhidos no dia
  seguinte). Pico d19-27: 20-41 tiles/dia.
- **Atraso de REPLANTIO: 69 tile-dias**. Pico d7: 16 tiles.
- **Total: 592 tile-dias** de produção atrasada.

## Dimensionamento
- Colheita no pico (d19-27): ~40 tiles maduros/dia; cada hand colhe ~5-8/dia.
  ⇒ **~4-6 hands EXTRAS no pico** para colher na hora.
- Replantio: ~1-2 hands extras.

## Implicação para a re-coreografia
Adicionar ~4-6 hands no pico (d9-27) focados em COLHEITA rápida + replantio.
As zonas dos hands extras devem priorizar os tiles que ficam maduros.
