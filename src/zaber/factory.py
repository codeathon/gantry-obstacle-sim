"""Gantry factory. Why: experiment never constructs Connection itself."""

from __future__ import annotations

from zaber.client import ZaberGantry
from zaber.protocol import Gantry


def open_gantry(cfg: object = None) -> Gantry:
	# Why: later cfg.fake → SimulatedGantry; stub always returns in-memory XY.
	del cfg
	gantry = ZaberGantry()
	gantry.connect()
	return gantry
