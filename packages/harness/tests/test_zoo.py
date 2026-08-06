"""Zoo registry basics — anchors present, roster shape stable."""

from __future__ import annotations

from harness.zoo import BUILTIN_ANCHORS, gate_zoo


def test_anchors_always_in_gate_zoo() -> None:
    roster = gate_zoo()
    for name in BUILTIN_ANCHORS:
        assert roster[name] == name
