"""Load sim.json. Why: keep pylon-track numbers in one file, not scattered literals."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from chase.config import ChasePolicyConfig


def _default_config_path() -> Path:
	here = Path(__file__).resolve()
	return here.parents[2] / "config" / "sim.json"


@dataclass(frozen=True)
class CameraTiming:
	model: str
	width_px: int
	height_px: int
	gsd_mm_per_px: float
	exposure_us: float
	frame_rate_fps: float
	usb_transfer_ms: float
	tracking_pipeline_ms: float
	mount_height_mm: float
	lens_mm: float

	@property
	def width_mm(self) -> float:
		return self.width_px * self.gsd_mm_per_px

	@property
	def height_mm(self) -> float:
		return self.height_px * self.gsd_mm_per_px

	@property
	def frame_period_s(self) -> float:
		return 1.0 / self.frame_rate_fps

	@property
	def exposure_s(self) -> float:
		return self.exposure_us * 1e-6

	@property
	def grab_to_host_s(self) -> float:
		# Why: global-shutter exposure then USB3 transfer of Mono8 1920x1200.
		return self.exposure_s + self.usb_transfer_ms * 1e-3

	@property
	def grab_to_track_s(self) -> float:
		return self.grab_to_host_s + self.tracking_pipeline_ms * 1e-3


@dataclass(frozen=True)
class ZaberConfig:
	command_rtt_ms: float
	max_speed_mm_s: float
	max_accel_mm_s2: float
	home_x_mm: float
	home_y_mm: float
	comm: str
	# Why: JSON opt-in; PREY_ZABER / ZABER_PORT still win in want_hardware().
	use_hardware: bool = False
	port: str = ""
	device_index: int = 0
	x_axis: int = 1
	y_axis: int = 2
	lockstep_group: int = 0
	poll_min_ms: float = 20.0


@dataclass(frozen=True)
class SimConfig:
	camera: CameraTiming
	chase: ChasePolicyConfig
	zaber: ZaberConfig
	control_period_ms: int
	stale_frame_ms: float
	trial_timeout_s: float
	# Why: open_gantry(cfg) can build SimulatedGantry without a serial port.
	fake: bool = True


def load_sim_config(path: Path | None = None) -> SimConfig:
	# Why split: keep this loader under 45 lines without hiding JSON keys.
	cfg_path = path or _default_config_path()
	raw = json.loads(cfg_path.read_text(encoding="utf-8"))
	ch = raw["chase_policy"]
	return SimConfig(
		camera=_camera_timing(raw["camera"]),
		chase=_chase_policy(ch),
		zaber=_zaber_config(raw["zaber"]),
		control_period_ms=int(raw["control"]["period_ms"]),
		stale_frame_ms=float(raw["control"]["stale_frame_ms"]),
		trial_timeout_s=float(raw["trial"]["timeout_s"]),
	)


def _camera_timing(cam: dict) -> CameraTiming:
	# Why: Ace AOI/exposure/fps come from pylon-track JSON so the two files cannot drift.
	from basler.load import load_camera_config
	from basler.optics import ACE_MODEL, GSD_MM_PX, LENS_MM, MOUNT_HEIGHT_MM

	ace = load_camera_config()
	return CameraTiming(
		model=str(cam.get("model") or ACE_MODEL),
		width_px=ace.width,
		height_px=ace.height,
		gsd_mm_per_px=float(cam.get("gsd_mm_per_px", GSD_MM_PX)),
		exposure_us=float(ace.exposure_time_us),
		frame_rate_fps=float(ace.frame_rate_fps),
		usb_transfer_ms=float(cam["usb_transfer_ms"]),
		tracking_pipeline_ms=float(cam["tracking_pipeline_ms"]),
		mount_height_mm=float(cam.get("mount_height_mm", MOUNT_HEIGHT_MM)),
		lens_mm=float(cam.get("lens_mm", LENS_MM)),
	)


def _chase_policy(ch: dict) -> ChasePolicyConfig:
	pref = float(ch["preferred_gap_mm"])
	return ChasePolicyConfig(
		preferred_gap_mm=pref,
		min_gap_mm=float(ch["min_gap_mm"]),
		max_pull_mm=float(ch["max_pull_mm"]),
		away_gain=float(ch["away_gain"]),
		toward_gain=float(ch["toward_gain"]),
		lateral_gain=float(ch["lateral_gain"]),
		wall_margin_mm=float(ch["wall_margin_mm"]),
		wall_gain=float(ch["wall_gain"]),
		corner_gain=float(ch["corner_gain"]),
		velocity_gain_s=float(ch["velocity_gain_s"]),
		max_engage_speed_mm_s=float(ch["max_engage_speed_mm_s"]),
		cone_half_angle_deg=float(ch.get("cone_half_angle_deg", 45.0)),
		threat_distance_mm=float(ch.get("threat_distance_mm", pref)),
		creep_distance_mm=float(ch.get("creep_distance_mm", pref * 2)),
	)


def _zaber_config(zb: dict) -> ZaberConfig:
	return ZaberConfig(
		command_rtt_ms=float(zb["command_rtt_ms"]),
		max_speed_mm_s=float(zb["max_speed_mm_s"]),
		max_accel_mm_s2=float(zb["max_accel_mm_s2"]),
		home_x_mm=float(zb["home_x_mm"]),
		home_y_mm=float(zb["home_y_mm"]),
		comm=str(zb["comm"]),
		use_hardware=bool(zb.get("use_hardware", False)),
		port=str(zb.get("port", "")),
		device_index=int(zb.get("device_index", 0)),
		x_axis=int(zb.get("x_axis", 1)),
		y_axis=int(zb.get("y_axis", 2)),
		lockstep_group=int(zb.get("lockstep_group", 0)),
		poll_min_ms=float(zb.get("poll_min_ms", 20.0)),
	)
