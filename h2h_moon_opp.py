"""Wrapper para usar o Moon V56 extraído (research/public/moon_agent_main.py)
como oponente no h2h_bench. O Moon expõe `agent(obs)` (1 arg); o runner do
kaggle_environments chama com (obs, config). Este wrapper ajusta a assinatura.

Usage: python h2h_bench.py mix_agent.py h2h_moon_opp.py --seeds 1-8
"""
import importlib.util
import os

_HERE = os.path.dirname(os.path.abspath(__file__))
_MOON_PATH = os.path.join(_HERE, "research", "public", "moon_agent_main.py")

_spec = importlib.util.spec_from_file_location("moon_agent_main", _MOON_PATH)
_moon = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_moon)


def agent(obs, config=None):
    return _moon.agent(obs)
