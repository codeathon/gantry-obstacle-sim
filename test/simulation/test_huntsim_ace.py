"""Web HuntSim: live Ace blob drives ferret; pointer only if no camera."""

from __future__ import annotations

import time

from basler.types import CameraFov, CameraFrame
from simulation.engine import HuntSim
from simulation.pylon_sim import SimulatedPylonCamera
from vision.tracking_frame import TrialPhase
from zaber.client import ZaberGantry
from zaber.motion import HardwareSettings


class _LiveGrabber:
	"""Mono8 stand-in with backend=pylon so HuntSim takes the Ace path."""

	def __init__(self, frames: list[CameraFrame], gsd: float = 1.035) -> None:
		self.backend = "pylon"
		self.timeout_ms = 20
		self.model = "a2A1920-160umPRO"
		self.GrabStrategy = "LatestImageOnly"
		self.PixelFormat = "Mono8"
		self.delivered = 0
		self.dropped = 0
		self.last_grab_to_frame_ms = 0.0
		self._frames = frames
		self._i = 0
		self._on = False
		self._gsd = gsd
		# Why: chase workspace is the Ace FOV, not the tiny test raster.
		self._fov = CameraFov(width_px=1920, height_px=1200, gsd_mm_per_px=gsd)

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
		frame.host_time_ns = time.time_ns()
		self.delivered += 1
		return frame

	def close(self) -> None:
		self._on = False

	def fov(self) -> CameraFov:
		return self._fov


def _paint(buf: bytearray, w: int, x0: int, y0: int, x1: int, y1: int) -> None:
	for y in range(y0, y1):
		for x in range(x0, x1):
			buf[y * w + x] = 255


def _ace_frames() -> list[CameraFrame]:
	# Why: default AnimalDetector warmup is 30 frames; blob must exceed min_area 200.
	w = h = 32
	blank = bytes(w * h)
	img = bytearray(w * h)
	_paint(img, w, 0, 0, 16, 16)
	frames = [
		CameraFrame(frame_index=i, width_px=w, height_px=h, pixels=blank, grab_ok=True)
		for i in range(1, 31)
	]
	frames.append(
		CameraFrame(
			frame_index=31,
			width_px=w,
			height_px=h,
			pixels=bytes(img),
			grab_ok=True,
		)
	)
	return frames


class _HwAxis:
	# Why: inject hardware backend without opening /dev/ttyUSB.
	def __init__(self, pos: float = 50.0) -> None:
		self.pos = pos
		self.vel = 0.0
		self.homed = True

	def get_position(self, unit=None):
		return self.pos

	def home(self) -> None:
		self.pos = 0.0

	def is_homed(self) -> bool:
		return self.homed

	def move_absolute(self, position, unit=None, **kwargs) -> None:
		self.pos = float(position)

	def move_velocity(self, velocity, unit=None, **kwargs) -> None:
		self.vel = float(velocity)

	def stop(self, wait_until_idle: bool = True) -> None:
		del wait_until_idle
		self.vel = 0.0


def test_huntsim_uses_pointer_camera_without_ace() -> None:
	sim = HuntSim()
	assert not sim._live_ace
	assert isinstance(sim.camera, SimulatedPylonCamera)
	assert sim.snapshot()["ferret_source"] == "pointer"


def test_huntsim_falls_back_to_pointer_if_ace_missing(monkeypatch) -> None:
	# Why: web hunt must still run when PREY_ACE is set but USB is empty.
	monkeypatch.setenv("PREY_ACE", "1")
	sim = HuntSim()
	assert not sim._live_ace
	assert isinstance(sim.camera, SimulatedPylonCamera)


def test_live_ace_blob_drives_ferret_not_pointer() -> None:
	sim = HuntSim(grabber=_LiveGrabber(_ace_frames()))
	assert sim._live_ace
	sim.controller._period_s = 0.0
	sim.trial = TrialPhase.running
	sim.set_pointer(400.0, 400.0)
	for _ in range(40):
		sim.step(0.001)
	seen = sim.controller._latest.ferret
	gsd = sim.cfg.camera.gsd_mm_per_px
	assert seen.valid
	assert abs(seen.x_px - 7.5) < 0.2
	assert abs(seen.x_mm - 7.5 * gsd) < 0.3
	assert abs(seen.x_mm - 400.0) > 50.0
	assert sim.snapshot()["ferret_source"] == "ace"
	assert any(c.name == "move_velocity" for c in sim.gantry.calls)


def test_hardware_pointer_skips_ace_delay() -> None:
	# Why: X-MCC + mouse must not wait SimulatedPylon grab_to_track (~5.7 ms).
	g = ZaberGantry(
		HardwareSettings(
			home_x_mm=50.0,
			home_y_mm=50.0,
			x_max=2000.0,
			y_max=2000.0,
			poll_min_s=0.0,
		),
		x_axis=_HwAxis(),
		y_axis=_HwAxis(),
	)
	sim = HuntSim(gantry=g)
	assert sim._direct_pointer_chase
	sim.controller._period_s = 0.0
	sim.trial = TrialPhase.running
	sim.set_pointer(120.0, 80.0)
	sim.step(0.020)
	seen = sim.controller._latest.ferret
	assert abs(seen.x_mm - 120.0) < 1e-6
	assert abs(seen.y_mm - 80.0) < 1e-6


def test_set_pointer_marks_hud_dirty() -> None:
	sim = HuntSim()
	sim._hud_dirty = False
	sim.set_pointer(10.0, 20.0)
	assert sim._hud_dirty
	assert abs(sim.true_ferret.x_mm - 10.0) < 1e-6
