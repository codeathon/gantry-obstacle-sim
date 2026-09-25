"""Live Mini roll. Skipped in CI unless SPHERO_LIVE=1 and a toy is awake."""

from __future__ import annotations

import os

import pytest

from sphero.demo_roll import run

_LIVE = os.environ.get("SPHERO_LIVE", "").strip().lower() in ("1", "true", "yes")


@pytest.mark.skipif(not _LIVE, reason="set SPHERO_LIVE=1 with an awake Mini")
def test_mini_rolls_four_headings() -> None:
	# Why: same path as python -m sphero.demo_roll; no Ace or Zaber.
	run(seconds=1.0, speed=70.0)
