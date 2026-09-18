"""Gantry factory. Why: experiment never constructs Connection itself."""

from __future__ import annotations

from zaber.client import ZaberGantry
from zaber.protocol import Gantry


def open_gantry(cfg: object = None) -> Gantry:
	# Why: cfg.fake → SimulatedGantry; else in-memory ZaberGantry (no serial yet).
	if getattr(cfg, "fake", False):
		return _open_simulated_gantry(cfg)
	gantry = ZaberGantry()
	gantry.connect()
	return gantry


def _open_simulated_gantry(cfg: object) -> Gantry:
	# Lazy import: hardware factory must not load sim physics at module import.
	from simulation.config import load_sim_config
	from simulation.zaber_sim import SimulatedGantry

	sim = cfg if hasattr(cfg, "zaber") and hasattr(cfg, "camera") else load_sim_config()
	zb = sim.zaber
	cam = sim.camera
	gantry = SimulatedGantry(
		zb.home_x_mm,
		zb.home_y_mm,
		zb.max_speed_mm_s,
		zb.max_accel_mm_s2,
		zb.command_rtt_ms,
		cam.width_mm,
		cam.height_mm,
	)
	gantry.connect()
	return gantry
