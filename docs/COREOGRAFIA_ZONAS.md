# Zonas dos Hands Extras — Re-coreografia (Passo 2)

Base: mapa de calor de atraso de colheita (v18, seed 1). O atraso concentra-se
no NW (strawberry, 22-28 dias maduros) + NE/SW esparsos.

## Mapa de atraso (grade 10x10)
```
9 9 9 9 9 9 9 7 7 6
9 9 9 9 9 9 7 . 7 5
9 9 9 9 . . 9 7 7 7
9 9 9 . . . . 7 8 9
9 9 . . . . . . 7 8
4 9 6 . . . . . . .
4 4 9 4 6 . . . . .
5 4 4 4 6 . . . . .
4 5 4 8 4 . . . . .
6 6 9 9 9 . . . . .
```
Legenda: dígito = dias maduros não colhidos. Concentração no NW (strawberry) e
canto NE/SW (9,3 / 2,9 / 3,9).

## Zonas dos hands extras (4-6 hands no pico)
| Zona | Tiles | Foco | Hand |
|---|---|---|---|
| A | NW centro (1-3, 1-3) | strawberry colheita | extra 1 |
| B | NW bordas (0-4, 0-4) | strawberry colheita | extra 2 |
| C | NE (5-9, 0-4) | wheat/crops | extra 3 |
| D | SW (0-4, 5-9) | wheat/crops | extra 4 |
| E | SE (5-9, 5-9) | crops (se liberar) | extra 5 |

## Rampa de HIRE (proposta)
| Dias | Hands totais | Hands extras |
|---|---|---|
| d0-3 | 6 | 0 |
| d4-8 | 10 | 2 (NW strawberry) |
| d9-20 | 13 | 5 (A-E) |
| d21-29 | 12 | 4 |

## Ciclo por zona (cada hand extra)
```
Na zona: WATER → HARVEST (maduro) → PLANT (replantar se vazio) → próximo tile
```
Strawberry (ongoing): colher a cada intervalo (não deixar yield no max).
Wheat: colher cedo (age>=2) e replantar imediato.

## Próximo passo (Passo 3)
Gerador de coreografia (`gen_coreografia.py`): para cada hand extra, gerar a
sequência de movimentos+ações na sua zona (ordem serpentina), começando no shed.
Integrar com a fita base (hands existentes) + HIRE na rampa.
