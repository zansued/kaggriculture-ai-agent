"""Kaggriculture submission entrypoint.

The competition expects a `main.py` at the root exposing `agent(obs, config)`.
The real logic lives in `src/kaggriculture_real.py` (self-contained stdlib).
"""
from __future__ import annotations

from src.kaggriculture_real import agent

__all__ = ["agent"]
