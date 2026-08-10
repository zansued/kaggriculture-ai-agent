"""Kaggriculture agent, now aligned with the real protocol.

This module keeps the public entrypoint compatible with the existing project
while delegating the actual turn logic to the real-protocol FarmBrain.
"""

from __future__ import annotations

from src.kaggriculture_real import agent as real_agent


class KaggricultureAgent:
    """Thin compatibility wrapper around the real-protocol policy."""

    def reset(self) -> None:
        return None

    def choose_action(self, observation, configuration=None):
        return real_agent(observation, configuration)


_agent = KaggricultureAgent()


def kaggriculture_agent(observation, configuration=None):
    try:
        return _agent.choose_action(observation, configuration)
    except Exception:
        return {"farmer": ["PASS"], "hands": [], "market": []}