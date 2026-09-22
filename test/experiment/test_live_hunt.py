"""Live hunt: Ace blob → mm → keep-away → Zaber move_velocity."""

from __future__ import annotations

import time

from basler.types import CameraFrame
from chase.config import ChasePolicyConfig
from experiment.orchestrator import Experiment
from vision.detect import AnimalDetector
from vision.pipeline import TrackingPipeline
from zaber.client import ZaberGantry


class _ScriptedGrabber:
	"""Tiny Mono8 source. Why: tests must not open pypylon or USB."""

	def __init__(self, frames: list[CameraFrame]) -> None:
		self._frames = frames
		self._i = 0
		self._on = False

	def open(self) -> None:
		return

	def configure(self) -> None:
		return

	def start_grabbing(self) -> None:
		self._on = True

	def stop_grabbing(self) -> None:
		self._on = False

	def retrieve_frame(self) -> CameraFrame | None:
		if not self._on or not self._frames:
			return None
		frame = self._frames[min(self._i, len(self._frames) - 1)]
		self._i += 1
		# Why: chase stale check is wall-clock vs host_time_ns.
		frame.host_time_ns = time.time_ns()
		return frame

	def close(self) -> None:
		self._on = False


def _paint(buf: bytearray, w: int, x0: int, y0: int, x1: int, y1: int) -> None:
	for y in range(y0, y1):
		for x in range(x0, x1):
			buf[y * w + x] = 255


def _mouse_frames() -> list[CameraFrame]:
	w = h = 32
	bg = CameraFrame(
		frame_index=1,
		width_px=w,
		height_px=h,
		pixels=bytes(w * h),
		grab_ok=True,
		host_time_ns=time.time_ns(),
	)
	img = bytearray(w * h)
	# Mouse left of the toy at (20, 16) mm / px with GSD 1.
	_paint(img, w, 4, 14, 9, 19)
	# Why: a lone in-frame blob is now the toy; chase needs both objects.
	_paint(img, w, 18, 14, 23, 19)
	hit = CameraFrame(
		frame_index=2,
		width_px=w,
		height_px=h,
		pixels=bytes(img),
		grab_ok=True,
		host_time_ns=time.time_ns(),
	)
	return [bg, hit]


def _keepaway() -> ChasePolicyConfig:
	# Why: wall terms would drown a 32 mm FOV; isolate radial keep-away.
	return ChasePolicyConfig(
		preferred_gap_mm=20.0,
		min_gap_mm=4.0,
		max_pull_mm=20.0,
		away_gain=2.2,
		toward_gain=1.1,
		lateral_gain=0.0,
		wall_margin_mm=2.0,
		wall_gain=0.0,
		corner_gain=0.0,
		velocity_gain_s=0.55,
		max_engage_speed_mm_s=480.0,
		cone_half_angle_deg=45.0,
		threat_distance_mm=20.0,
		creep_distance_mm=40.0,
	)


def test_mouse_blob_drives_gantry_velocity() -> None:
	gantry = ZaberGantry()
	grabber = _ScriptedGrabber(_mouse_frames())
	pipe = TrackingPipeline(
		gsd_mm_per_px=1.0,
		detector=AnimalDetector(1.0, min_area=4.0, exclude_mm=8.0, warmup_frames=1),
	)
	exp = Experiment(
		gantry,
		grabber,
		cfg=_keepaway(),
		width_mm=32.0,
		height_mm=32.0,
		period_ms=0,
		pipeline=pipe,
	)
	exp.start()
	# Why: home is (0,0); put the toy right of the mouse so keep-away is +x.
	gantry.move_absolute(20.0, 16.0)
	exp.on_operator_key("s")
	exp.chase_feed_loop()
	scene = exp.chase_feed_loop()
	exp.shutdown()
	assert scene is not None
	assert scene.ferret.valid
	assert abs(scene.ferret.x_mm - 6.0) < 0.5
	assert scene.prey.x_mm == 20.0
	assert scene.prey.valid
	assert "move_velocity" in gantry.calls
	assert exp.chase.last_decision.enable_motion
	assert exp.chase.last_decision.target_vx_mm_s > 0


class _Rail:
	# Why: inject X-MCC travel without opening /dev/ttyUSB.
	def __init__(self, pos: float = 0.0) -> None:
		self.pos = pos
		self.vel = 0.0
		self.homed = True

	def get_position(self, unit=None):
		return self.pos

	def home(self) -> None:
		self.pos = 0.0

	def is_homed(self) -> bool:
		return True

	def move_absolute(self, position, unit=None, **kwargs) -> None:
		self.pos = float(position)

	def move_velocity(self, velocity, unit=None, **kwargs) -> None:
		self.vel = float(velocity)

	def stop(self, wait_until_idle: bool = True) -> None:
		del wait_until_idle
		self.vel = 0.0


def _rail_gantry():
	from zaber.motion import HardwareSettings

	# Why: 16 mm rails vs 32 mm FOV — raw encoder mm/GSD misses the toy disc.
	return ZaberGantry(
		HardwareSettings(x_max=16.0, y_max=16.0, home_x_mm=8.0, home_y_mm=8.0),
		x_axis=_Rail(),
		y_axis=_Rail(),
	)


def _tiny_pipe() -> TrackingPipeline:
	return TrackingPipeline(
		gsd_mm_per_px=1.0,
		detector=AnimalDetector(1.0, min_area=4.0, exclude_mm=8.0, warmup_frames=1),
	)


def test_toy_blob_ignored_after_travel_maps_to_ace() -> None:
	# encoder (8,8) on 16 mm rails → arena (16,16) on a 32 mm FOV.
	w = h = 32
	bg = CameraFrame(frame_index=1, width_px=w, height_px=h, pixels=bytes(w * h), grab_ok=True)
	img = bytearray(w * h)
	_paint(img, w, 14, 14, 19, 19)
	hit = CameraFrame(frame_index=2, width_px=w, height_px=h, pixels=bytes(img), grab_ok=True)
	gantry = _rail_gantry()
	exp = Experiment(
		gantry, _ScriptedGrabber([bg, hit]), width_mm=32.0, height_mm=32.0,
		period_ms=0, pipeline=_tiny_pipe(),
	)
	exp.start()
	gantry.move_absolute(8.0, 8.0)
	exp.on_operator_key("s")
	exp.chase_feed_loop()
	scene = exp.chase_feed_loop()
	exp.shutdown()
	assert scene is not None
	assert not scene.ferret.valid
	assert abs(scene.prey.x_mm - 16.0) < 1e-6
	assert abs(scene.prey.y_mm - 16.0) < 1e-6


def test_ferret_kept_when_toy_maps_elsewhere() -> None:
	w = h = 32
	bg = CameraFrame(frame_index=1, width_px=w, height_px=h, pixels=bytes(w * h), grab_ok=True)
	img = bytearray(w * h)
	_paint(img, w, 4, 14, 9, 19)
	# Why: encoder maps to arena (16,16); without a toy blob the mouse is dropped.
	_paint(img, w, 14, 14, 19, 19)
	hit = CameraFrame(frame_index=2, width_px=w, height_px=h, pixels=bytes(img), grab_ok=True)
	gantry = _rail_gantry()
	exp = Experiment(
		gantry, _ScriptedGrabber([bg, hit]), width_mm=32.0, height_mm=32.0,
		period_ms=0, pipeline=_tiny_pipe(),
	)
	exp.start()
	gantry.move_absolute(8.0, 8.0)
	exp.on_operator_key("s")
	exp.chase_feed_loop()
	scene = exp.chase_feed_loop()
	exp.shutdown()
	assert scene is not None
	assert scene.ferret.valid
	assert abs(scene.ferret.x_mm - 6.0) < 1.0
	assert abs(scene.prey.x_mm - 16.0) < 1e-6
