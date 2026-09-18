"""Gantry factory. Why: experiment never constructs Connection itself."""

from __future__ import annotations

import os
import sys

from zaber.client import ZaberGantry
from zaber.motion import settings_from_sim, want_hardware
from zaber.protocol import Gantry


def open_gantry(cfg: object = None) -> Gantry:
	# Why: hardware X-MCC when requested; SimulatedGantry if unplugged.
	if cfg is None and not want_hardware(None):
		gantry = ZaberGantry()
		gantry.connect()
		return gantry
	if cfg is None:
		from simulation.config import load_sim_config

		cfg = load_sim_config()
	if want_hardware(cfg):
		return _open_hardware_or_fallback(cfg)
	return _open_simulated_gantry(cfg)


def _open_hardware_or_fallback(cfg: object) -> Gantry:
	try:
		gantry = ZaberGantry(settings_from_sim(cfg), use_serial=True)
		gantry.connect()
		return gantry
	except Exception as exc:
		if os.environ.get("PREY_ZABER_REQUIRE", "").strip().lower() in (
			"1", "true", "yes",
		):
			raise
		# Why: ferret sim should still run when the toy stage is missing.
		print(f"Zaber hardware unavailable ({exc}); using SimulatedGantry", file=sys.stderr)
		return _open_simulated_gantry(cfg)


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
