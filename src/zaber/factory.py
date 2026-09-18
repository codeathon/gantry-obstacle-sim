"""Gantry factory. Why: experiment never constructs Connection itself."""

from __future__ import annotations

from zaber.protocol import Gantry


def open_gantry(cfg: object) -> Gantry:
	# Why: cfg.fake → SimulatedGantry later; else ZaberGantry serial.
	raise NotImplementedError("open fake vs serial gantry")
