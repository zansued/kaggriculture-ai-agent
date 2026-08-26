# Mudança Estrutural — Agente Wheat-Heavy (v12+)

> Projeto iniciado 26/08/2026. Base: hybrid_v6 (Moon V56 + overlays). Objetivo:
> fechar o gap de ~600 ELO para o top (~3100) reestruturando a economia de
> produção, seguindo o padrão observado no replay do Crop Dusta.

## 1. Evidência (replay episode 99954642 — Ryo vs CropDusta, seed 507467650)

Partida real entre os 2 top agents. Resultado: CropDusta 125.270 vs Ryo 124.243
(+1.027). CropDusta venceu com estratégia wheat-heavy.

### CropDusta — ciclo do WHEAT (o que faz de diferente)
| Fase | Dias | Comportamento |
|---|---|---|
| Base | 0-3 | Planta 8→13 tiles de wheat |
| Manutenção | 4-10 | 7-15 tiles; vendas pequenas (3-60) |
| **Venda massiva** | **11-14** | Vende **222-244/dia** (preço 36-40 = 1.44-1.6×base) |
| **Escala** | **15-27** | Expande para **37 tiles**; colhe 14-27/dia; vende 54-178/dia |
| Dump final | 28-29 | Liquida resto (149 no d29) |

- Preço do wheat: base 25 → pico ~44 (d24-26) → cai para 41-43 no fim.
- Total wheat vendido (tentativas SELL): **2.272**.
- Rebanho: 4 vacas + 13 ovelhas; BUY_LAND ×2 (3 quadrants); HIRE ~293 (12 hands máx).

### v6 (Moon) no MESMO seed — onde perde
- Reward **75.889** vs CropDusta **125.270** → **gap de 49.381**.
- Paridade de terra/plantio: ~100 tiles, 3 quadrants, 36 wheat no pico (d26).
- **Mas vende wheat tarde**: dump só no d26 (202) e d29 (190); quase nada d11-14.
- **Spam de fertilizante**: 5.870 tentativas SELL FERTILIZER (preço baixo, decai)
  vs CropDusta 181 → desperdiça slots de market e mão de obra.
- Mix v6: FERT 5870, WHEAT 1712, STRAWB 592, MILK 572, WOOL 308, MELON 144.

### Conclusão do diagnóstico
A lacuna **não** é escala de plantio nem terra (paridade). É:
1. **Timing de venda de wheat** — o CropDusta monetiza wheat no meio do jogo
   (d11-14, preço 1.4×base+), o v6 segura até o fim.
2. **Eficiência de ordens** — o v6 spama SELL FERTILIZER barato, ocupando slots
   e tempo de colheita que deveriam ir para itens de maior valor.
3. **Composição do rebanho** — CropDusta prioriza ovelhas (13) sobre vacas (4);
   o v6 tem mais vacas. (Hipótese secundária a validar.)

## 2. Especificação das mudanças (faseadas)

### Fase 1 — Overlays de market (baixo risco, baseados em evidência)
1. **`_wheat_early_sell`** (ESQUELETO v12): quando preço do wheat >= 1.4×base
   (~35) e step na janela d10-27, forçar SELL do **EXCEDENTE** (shed − reserva
   de feed). ⚠️ **LIÇÃO 26/08**: vender TODO o shed de wheat MATA os animais
   (wheat = FEED; reward colapsa 146k→56k). Com reserva de 60, o v12 é seguro
   mas quase inócuo → a lacuna real é **excedente de produção**, não venda.
2. **`_fert_dampen`** (adiado): limitar ordens SELL FERTILIZER a preço baixo —
   o v6 spama 5870 tentativas (preço decai) vs CropDusta 181. Segurar fertilizante
   pode perder produção (não acumula) — precisa agregar, não segurar.
3. Validar via h2h vs v6 (W/L, 2 lados). Critério: superar v6 em W/L.

### Fase 2 — Produção (médio risco)
4. Ajustar mix de plantio para manter wheat estável e escalar no meio-tarde
   (já parcial: Moon chega a 36-41 wheat; validar se mais cedo ajuda).
5. Rebanho: testar 4-5 vacas + 10-13 ovelhas (padrão CropDusta) vs atual.

### Fase 3 — Estrutural (alto risco, requer reavaliação da base)
6. Se overlays não bastarem: reescrever a camada de decisão de produção/venda
   do Moon com economia wheat-heavy própria (top-down, não overlay).

## 3. Métricas de sucesso
- h2h vs hybrid_v6 (24-36 seeds, 2 lados): novo agente vence em W/L.
- Seed de referência 507467650: reward > 125.270 (batendo o CropDusta no
  confronto local) ou ao menos > 75.889 (v6 atual).
- Submissão: só após validação h2h; NUNCA submeter variação não validada.

## 4. Estado do projeto
- [x] Diagnóstico (26/08): replay analisado, gap quantificado (49k no seed).
- [x] Especificação (este documento).
- [x] Fase 1: `_wheat_early_sell` com reserva de feed (build v12). VALIDADO
      26/08: h2h 2 lados vs v6 (seeds 1-12) = **2-2, 8 ties, mean d=+84 → NEUTRO**.
      LIÇÃO: sem excedente de produção não há o que vender cedo.
- [x] Fase 2 EXPLORADA (26/08) — TODAS as hipóteses de overlay FALHARAM:
  - `fert_dampen` (suprimir venda de fert barato): **1-11** vs v6 — enche o shed
    (cap 100) e bloqueia itens premium. O v6 ESTÁ certo em despejar fert.
  - `wheat_sell` (vender excedente wheat >= $30, reserva 40): **2-2** neutro.
  - `strawb2wheat` (converter 50% dos plantios de strawberry p/ wheat): **0-12**
    (mean -12.780) — strawberry (~$209/tile) vale muito mais que wheat (~$44).
  - `wheat_arb` (comprar wheat barato e revender no pico): **2-2** neutro — o v6
    já arbitra (BUY_PRODUCT WHEAT 487/jogo).
  - CONCLUSÃO: o v6 é um ótimo local robusto; o gap de 49k do CropDusta vem de
    uma economia wheat-heavy ESTRUTURAL (produção ~2-3x de wheat + rebanho com
    mais ovelhas + terra 100% ocupada desde d0, sem terra livre p/ overlays).
    Overlays NÃO capturam isso → **Fase 3 é obrigatória**.
- [ ] Fase 3: construir base wheat-heavy do zero (rota nova coerente, top-down).
  Evidência-chave do v6 no seed 507467650: terra livre = 0 em todos os dias
  (grid 100% ocupado d0); vende 856 wheat total (99% após d21); 2935 fert;
  10COW+4SHEEP; compra 487 wheat (arbitragem).
- [ ] OBSERVAÇÃO LADDER (26/08): submissão v6 12:14 = public 1346.0 — queda
  grande vs v2 (2253 em 08-24) e v5 (1990 em 08-25). h2h local não traduz em
  ELO; investigar se é volatilidade de snapshot ou o campo evoluiu demais.

## 5. Referências
- Replay local: `C:/Users/zan_s/AppData/Local/Temp/replays/episode-99954642-replay.json`
- Scripts de análise: `/tmp/profile_tops2.py`, `/tmp/wheat_cycle.py`,
  `/tmp/moon_wheat_cycle.py`, `/tmp/moon_sell_mix.py`
- Build base: `build_hybrid_v6.py` → `submissions/hybrid_v6/main.py`
