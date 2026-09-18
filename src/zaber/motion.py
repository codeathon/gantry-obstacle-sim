"""Serial / lockstep helpers. Why: zaber_motion import stays here, not in chase."""

from __future__ import annotations

import glob
import os
from dataclasses import dataclass


@dataclass
class HardwareSettings:
	"""X-MCC connection and software workspace, in millimetres."""

	port: str = ""
	device_index: int = 0
	x_axis: int = 1
	y_axis: int = 2
	lockstep_group: int = 0
	home_x_mm: float = 0.0
	home_y_mm: float = 0.0
	max_speed_mm_s: float = 1400.0
	max_accel_mm_s2: float = 2500.0
	x_min: float = 0.0
	x_max: float = 1987.0
	y_min: float = 0.0
	y_max: float = 1242.0
	poll_min_s: float = 0.02


def load_zml():
	# Why: import only when connecting so tests/web do not need the wheel.
	try:
		from zaber_motion import Units
		from zaber_motion.ascii import Connection
	except ImportError as exc:
		raise RuntimeError(
			"zaber-motion is not installed; pip install 'prey-gantry[zaber]'"
		) from exc
	return Connection, Units


def serial_candidates(port: str = "") -> list[str]:
	# Why: ZABER_PORT wins; otherwise typical Linux CDC names for X-MCC.
	override = port or os.environ.get("ZABER_PORT") or os.environ.get("PREY_ZABER_PORT")
	if override:
		return [override]
	return sorted(glob.glob("/dev/ttyUSB*") + glob.glob("/dev/ttyACM*"))


def want_hardware(cfg: object | None) -> bool:
	flag = os.environ.get("PREY_ZABER", "").strip().lower()
	if flag in ("1", "true", "yes", "on"):
		return True
	if os.environ.get("ZABER_PORT") or os.environ.get("PREY_ZABER_PORT"):
		return True
	zb = getattr(cfg, "zaber", cfg)
	return bool(getattr(zb, "use_hardware", False))


def settings_from_sim(cfg: object) -> HardwareSettings:
	zb = cfg.zaber
	cam = cfg.camera
	return HardwareSettings(
		port=str(getattr(zb, "port", "") or ""),
		device_index=int(getattr(zb, "device_index", 0)),
		x_axis=int(getattr(zb, "x_axis", 1)),
		y_axis=int(getattr(zb, "y_axis", 2)),
		lockstep_group=int(getattr(zb, "lockstep_group", 0)),
		home_x_mm=float(zb.home_x_mm),
		home_y_mm=float(zb.home_y_mm),
		max_speed_mm_s=float(zb.max_speed_mm_s),
		max_accel_mm_s2=float(zb.max_accel_mm_s2),
		x_min=0.0,
		x_max=float(cam.width_mm),
		y_min=0.0,
		y_max=float(cam.height_mm),
		poll_min_s=float(getattr(zb, "poll_min_ms", 20.0)) * 1e-3,
	)
