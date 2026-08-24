"""Híbrido: Moon V56 como base + contribuições validadas do mix_agent.

Moon V56 (research/public/moon_agent_main.py) é a base mais forte (esmaga o
mix 8-0). Este híbrido adiciona os overlays do mix que provaram valor:
  - _mature_opp_front_run: vende shed premium quando a PRODUÇÃO do oponente
    está quase madura (dump iminente), independente de clone — o Moon só
    preempta clones (clone_distance<=6).
  - _sell_first: order-slot — premium sells processam antes das do oponente.

Usage: python h2h_bench.py hybrid_moon_mix.py h2h_moon_opp.py --seeds 1-8
"""
import importlib.util
import os

_HERE = os.path.dirname(os.path.abspath(__file__))

# Carrega mix_agent (para reusar os overlays). Ele também expõe agent().
_mix_spec = importlib.util.spec_from_file_location("mix_agent", os.path.join(_HERE, "mix_agent.py"))
mix_agent = importlib.util.module_from_spec(_mix_spec)
_mix_spec.loader.exec_module(mix_agent)

# Carrega o Moon via o wrapper existente.
from h2h_moon_opp import agent as _moon_agent  # noqa: E402

_ENABLE_MATURITY = os.environ.get("MOON_MIX_MAT", "1") == "1"
_ENABLE_SELL_FIRST = os.environ.get("MOON_MIX_SELL", "1") == "1"


def agent(obs, config=None):
    step = int(obs.get("step", 0) or 0)
    action = _moon_agent(obs, config)
    if _ENABLE_MATURITY:
        mix_agent._mature_opp_front_run(action, obs, step)
    if _ENABLE_SELL_FIRST:
        action = mix_agent._sell_first(action, obs, step)
    return action
