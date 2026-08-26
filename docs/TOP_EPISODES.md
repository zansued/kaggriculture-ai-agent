# Episódios de referência — Top agents (ladder)

> Baixados 26/08/2026 via `GetEpisode` (novo endpoint `/api/i/competitions.EpisodeService/GetEpisode`).
> NOTA: o endpoint retorna METADADOS (rewards, seed, teams) mas NÃO o replay completo
> (steps). O Kaggle não expõe o replay via API pública. Para os steps, é preciso
> baixar via browser na página do episódio.

## Episódio 100148654 — Crop Dusta vs Ryo Hasegawa
- **URL**: `https://www.kaggle.com/competitions/kaggriculture/leaderboard?submissionId=55714246&episodeId=100148654`
- **Seed**: 1017826910
- **Resultado**: **Ryo Hasegawa venceu** 92.656 vs 92.029 (Crop Dusta)
- **Agentes**:
  - Crop Dusta (sub 55714246, team 16714457): reward 92.029, score 3095.9→3090.3
  - Ryo Hasegawa (sub 55614463, team 16644287): reward 92.656, score 3027.0→3032.7
- **Observação**: Crop Dusta é o wheat-heavy (#1 do ladder). Ryo é melon-heavy. Ryo venceu por ~627 no reward (0.7%).

## Episódio 100148657 — Subramanya N vs Ryo Hasegawa
- **URL**: `https://www.kaggle.com/competitions/kaggriculture/leaderboard?submissionId=55614463&episodeId=100148657`
- **Seed**: 2011797993
- **Resultado**: **Subramanya N venceu** 75.618 vs 69.389 (Ryo)
- **Agentes**:
  - Subramanya N (sub 55616096, team 16705390): reward 75.618, score 2961.9→2967.6
  - Ryo Hasegawa (sub 55614463, team 16644287): reward 69.389, score 3036.1→3030.4

## Gap do nosso v6 nesses seeds (26/08)
| Seed | Tops (reward) | v6 mirror | Gap |
|---|---|---|---|
| 1017826910 | 92.0-92.7k | 74.6-78.3k | **~14-18k** |
| 2011797993 | 69.4-75.6k | 64.1k | **~5-11k** |

## Uso como benchmark da Fase 3
- A rota nova (wheat-heavy) deve superar:
  - seed 1017826910: > 92.656 (Ryo) e > 92.029 (CropDusta)
  - seed 2011797993: > 75.618 (Subramanya)
- Juntamente com o seed 507467650 (replay 99954642): > 125.270 (CropDusta).
- Os tops fazem ~92k em seed que o v6 faz ~75k — o gap de ELO (~1700) é consistente
  com ~15-20% de diferença de reward.
