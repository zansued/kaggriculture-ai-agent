# Kaggriculture AI Agent

Autonomous agent for the [Kaggriculture](https://www.kaggle.com/competitions/kaggriculture) farming-simulation competition — an agent earns coins by managing crops, animals, land and market trades across a 30-day (720-step) season, **against a live opponent in the same shared market**.

- **Prize pool**: $50,000 · **Entry deadline**: Sep 23, 2026
- **Platform**: Kaggle `kaggle-environments` (ELO ladder, 5 submissions/day, only latest 2 active)
- **Repo**: [github.com/zansued/kaggriculture-ai-agent](https://github.com/zansued/kaggriculture-ai-agent)

---

## 🏆 Current status

| Item | Value |
|---|---|
| **Best agent** | `purearch` trace (181k vs starter) — active on ladder |
| **Ladder ELO** | purearch trace **~1096**, reactive `main.py` ~1074 (Aug 17) |
| **Field top** | ~3260 (adaptive agents) |
| **Hard truth** | fixed traces **depreciate ~30-40 ELO/day** — the field improves faster than any precomputed schedule |

**Strategic conclusion (hard-won over 13+ sessions):** production-side tuning is exhausted. `purearch` is a *tight local optimum* — every mutation/overlay/surgery/sell-recalibration tested loses head-to-head. The remaining gap to the top (~1000+ ELO) belongs to **adaptive/opponent-aware agents**; the `dispatcher` (below) is the leading experiment toward that.

---

## 🤖 The agents

| Agent | File | vs starter | Role |
|---|---|---|---|
| **purearch trace** ⭐ | `reference/opponents/purearch_opponent.py` | **~181k** (mean 156k, range 107-184k) | **Best agent.** Precomputed 8 COW + 6 SHEEP schedule; buys NE d7 + SW d10; 39 strawberry + 32 wheat; aggressive price-timed selling. Self-contained (works as submission `main.py`). |
| **reactive (FarmBrain)** | `src/kaggriculture_real.py` | ~85k | Hand-coded greedy coordinator on 25 tiles. 9 COW + 4 SHEEP. Healthy economy but structurally can't match a 75-tile trace. |
| **trace_10c4s** | `data/kawasagi/trace_10c4s.json` (via `trace_agent.py`) | ~183k vs starter | purearch animal mix swapped to 10 COW + 4 SHEEP. *Loses* to purearch h2h 8-12 — market interaction, not money-vs-starter, decides. |
| **cronograma** | `cronograma_agent.py` | 25-29k | Zone-based scaling agent (each hand owns a quadrant). Concept validated (plants across NE/SW), production plateaus ~40 plants. WIP. |
| **dispatcher v1** | `dispatcher_agent.py` | **0** | Learned RandomForest (75% acc on held-out replays) trained on top-agent hands. Runtime economy broke: classifier out-of-distribution on an empty farm → never harvested → bankrupt by day 8. |
| **dispatcher v2** | `dispatcher_v2.py` | **~32k** | v1 + hard crop-lifecycle overrides (HARVEST>WATER>DIG>PLANT) + unit coordination + FarmBrain-style market. Economy now survives. **Land experiment negative** (31.8k → 13.7k with NE/SW): the learned coordinator also can't scale 75 tiles. |

> **Dead-ends kept for reference** (all tested, all lose h2h vs purearch): `market_agent.py`, `market_agent10.py`, `hybrid_agent.py`, `hybrid_switch.py`, `opponent_aware_trace.py`, `hold_wheat_late.py`, `lns_sell.py`, `convert_wheat_to_strawberry.py`, `trace_game.py`.

---

## 📊 Performance & head-to-head

Always compare on **paired seeds** — vs-starter reward has huge variance (107-184k).

| Matchup | Result |
|---|---|
| purearch vs starter | ~181k mean |
| purearch vs trace_10c4s (20 seeds) | **12-8** |
| top agent vs purearch (10 replays) | **8-10** (top wins) — its *coherent schedule* beats purearch, but it's adaptive & unreplicable as a trace |
| reactive vs purearch | 0/5 (every reactive variant) |
| any sell overlay / cap / re-calibration on purearch | loses |

---

## 🛠️ Usage

### Requirements
```bash
pip install -r requirements.txt   # kaggle-environments, numpy, joblib (dispatcher only)
```

### Benchmark vs starter / random
```bash
python benchmark.py                        # FarmBrain variants vs starter, 3 seeds
python benchmark.py --opponent random --seeds 5
```

### Head-to-head (the metric that matters)
```bash
python h2h_bench.py purearch trace_10c4s --seeds 1-20
python h2h_bench.py purearch reactive --seeds 1-20
python h2h_bench.py dispatcher_v2 purearch --seeds 1-10
```

### Build a submission bundle (embeds the trace + robustness layer)
```bash
python data/kawasagi/build_submission.py data/kawasagi/trace_purearch.json --tar submissions/trace_purearch.tar.gz
```
The competition expects a root `main.py` exposing `agent(obs, config)`. The repo `main.py` is the reactive FarmBrain; **the best ladder submission is the purearch trace bundle** (tar with a self-contained `main.py`).

### Submit to Kaggle
```bash
./kaggle_cli.sh competitions submit -c kaggriculture -f submissions/trace_purearch.tar.gz -m "msg"
./kaggle_cli.sh competitions list -c kaggriculture   # check leaderboard
python check_submissions.py                          # your submission status/ELO
```

### Push to GitHub (token via Windows Credential Manager)
```powershell
powershell -ExecutionPolicy Bypass -File push_gh.ps1
```

---

## 🧠 Research findings (13+ sessions of hard-won facts)

1. **Animals are ~3× the labor ROI of crops** — 1 COW = +$19k marginal, SHEEP +$17k, GOOSE +$11k. The 14th animal hurts via tile pressure, not labor.
2. **Hands are re-hired every day** (engine resets at day boundary). 8 hands ≈ 54g/day; 12 ≈ 376g/day. 8 is the sweet spot.
3. **Aggressive selling IS the production engine.** Any sell overlay/cap/gate/price-floor on the trace destroys value. purearch's sell schedule is optimal (confirmed by CEM/LNS search).
4. **Land is net loss for every greedy coordinator** (reactive AND dispatcher) — they can't maintain distant crops. Only precomputed traces (purearch, c27) scale 75 tiles.
5. **purearch is a tight local optimum** — regret analysis over all 79 critical orders found zero wasteful decisions.
6. **The top agent's edge is its coherent production schedule** (10 COW + 4 SHEEP + 33 strawberry + land d6/d11 + mass feed-wheat buying), which is **unreplicable** as a trace (state-coupled) or via config mutation.
7. **Price dynamics**: fertilizer decays ($100→$9, sell ASAP), milk peaks d13 then crashes, wool dips then recovers (hold late), strawberry crashes after d21, melon crashes after d10, wheat rises late.

---

## 🗂️ Project structure

```
kaggriculture-ai-agent/
├── main.py                       # submission entrypoint → src/kaggriculture_real.agent (reactive)
├── benchmark.py                  # vs-starter harness
├── h2h_bench.py                  # head-to-head between any two agents over N seeds
├── dispatcher_agent.py           # learned dispatcher v1 (0.0 — economy broken, kept for reference)
├── dispatcher_v2.py              # learned dispatcher v2 (~32k — crop lifecycle overrides)
├── cronograma_agent.py           # zone-based scaling agent (25-29k crop-only)
├── kaggle_cli.sh                 # kaggle CLI wrapper (kaggle.exe broken on Py3.14)
├── push_gh.ps1                   # push via Windows Credential Manager token
├── check_submissions.py          # ladder status checker
├── src/
│   ├── kaggriculture_real.py     # FarmBrain reactive agent (85k ceiling)
│   ├── agent.py / utils.py / train.py / submit.py / jules_helper.py
├── reference/
│   └── opponents/
│       ├── purearch_opponent.py  # ⭐ BEST agent (self-contained 181k trace)
│       └── trace_agent.py        # generic trace loader + robustness layer
├── data/kawasagi/                # ⚠️ gitignored — replays, traces, model, analysis scripts
│   ├── trace_purearch.json       # best trace (build submissions from this)
│   ├── dispatcher_model.joblib   # 323MB RandomForest (dispatcher runtime)
│   └── *.py                      # build_trace, fork_trace, hand_alloc, etc.
├── tests/test_agent.py           # 28 unit tests
└── README.md
```

> **Note on `data/`**: gitignored (replays are 29MB each, model is 323MB). The dispatcher runtime needs `data/kawasagi/dispatcher_model.joblib` + `dispatch_extract.py` from a previous session — not reproducible from a fresh clone.

---

## 🔬 Research scripts (in `data/kawasagi/`, gitignored)

- `build_trace.py` / `decode_purearch.py` — trace extraction
- `fork_trace.py` — counterfactual regret forks
- `hand_alloc.py` — Stage-1 hand allocation analysis
- `microbench_animal.py` — animal ROI benchmark
- `mutate_*.py` — animal/sell-mix/trace mutation sweeps
- `dispatch_extract.py` — dispatcher feature extraction + training data builder
- `pure_daily.py` / `reactive_daily.py` / `trace_econ.py` — per-day economy probes

---

## 📝 License

MIT — see [LICENSE](LICENSE).

---
*Built for Kaggriculture — the field moves fast; fixed traces depreciate; adapt or lose ELO.*
