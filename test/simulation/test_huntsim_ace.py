"""Web HuntSim: live Ace blob drives ferret; pointer only if no camera."""

from __future__ import annotations

import time

from basler.types import CameraFov, CameraFrame
from simulation.engine import HuntSim
from simulation.pylon_sim import SimulatedPylonCamera
from vision.tracking_frame import TrialPhase


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
