"""Submission entry point: the shell-wrapped policy.

The bundle's top-level ``main.py`` imports ``agent`` from here. Keep module
import time trivial — the import-time budget test enforces it (the 60 s
overage bank is for thinking, not imports; runner-facts decision, issue #15).
"""

from __future__ import annotations

from agent.policy import make_policy
from agent.shell import wrap

agent = wrap(make_policy())
