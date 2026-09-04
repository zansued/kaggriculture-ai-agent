"""Clock correction for Kaggriculture local harness.

The stock kaggle-environments (1.32.7) injects ``obs["step"]`` ONLY on seat 0
(core.py writes it to ``new_state[0].observation``). Seat 1 receives no ``step``
key, while ``day`` and ``hour`` ARE synchronised to both seats every turn
(engine interpreter lines ~951-956).

Step-indexed agents (Moon and its hybrids) read ``obs.get("step", 0)`` and index
a precomputed 719-element tape with it -> on seat 1 they would always execute
``actions[0]``. This corrupts every local 2-seat h2h/league result that is not
clock-safe.

Fix: canonical clock is ``logical_step = day * turns_per_day + hour``
(turns_per_day == 24 in the default config). Always rebuild ``step`` from
day/hour and inject it before the agent reads it.
"""
from __future__ import annotations

import inspect

TURNS_PER_DAY = 24  # kaggriculture.json default (min 1, but the real env uses 24)


def logical_step(obs) -> int:
    """Reconstruct the global step from the synced day/hour fields.

    Valid for BOTH seats on the stock 1.32.7 local env (and equal to obs['step']
    on seat 0, where the framework injects it).
    """
    day = int(obs.get("day", 0) or 0)
    hour = int(obs.get("hour", 0) or 0)
    return day * TURNS_PER_DAY + hour


def inject_step(obs) -> dict:
    """Return obs with obs['step'] set to the canonical logical step.

    Mutates and returns the same dict (the engine gives each seat its own obs
    object per turn, so this is safe).
    """
    obs["step"] = logical_step(obs)
    return obs


def clock_safe(fn):
    """Wrap an agent so it always sees a consistent obs['step'] on both seats.

    Handles 1-arg and 2-arg agents (like league_game._wrap). The obs dict is
    mutated in place before delegating to the real agent.
    """
    try:
        n = len(
            [
                p
                for p in inspect.signature(fn).parameters.values()
                if p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)
            ]
        )
    except Exception:
        n = 2

    if n >= 2:
        def _wrapped(obs, cfg=None):
            inject_step(obs)
            return fn(obs, cfg)
    else:
        def _wrapped(obs, cfg=None):
            inject_step(obs)
            return fn(obs)
    _wrapped.__name__ = getattr(fn, "__name__", "clock_safe_agent")
    return _wrapped
