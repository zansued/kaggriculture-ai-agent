"""Kaggle submission entrypoint: `agent(obs)`.

Kaggle calls a top-level `agent(obs)` (some envs also pass a second `config`
argument — we accept and ignore it). This module keeps a single FarmBrain and
delegates to it.

For a Kaggle notebook submission you typically need ONE self-contained file. To
produce that, inline `protocol.py` + `brain.py` above this function — both are
pure stdlib with no cross-package imports, so it is a copy-paste with no edits.
"""

from __future__ import annotations

from .brain import FarmBrain

_BRAIN = FarmBrain()


def agent(obs: dict, config: object = None) -> dict:
    return _BRAIN.decide(obs)
