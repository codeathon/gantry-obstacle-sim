"""Basler pylon–shaped grab pipeline with pylon-track camera timings.

Why: InstantCamera.OnImageGrabbed is not instantaneous — exposure, USB3
transfer, then MOG2/associator. LatestImageOnly drops frames if we fall behind.
The grab only records camera pixels; vision maps those to mm.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass

from basler.types import CameraFrame
from simulation.config import CameraTiming
from vision.pipeline import TrackingPipeline
from vision.tracking_frame import TrackingFrame, TrackState, TrialPhase


@dataclass
class _PendingGrab:
	ready_s: float
	sample_s: float
	frame_index: int
	ferret_x_px: float | None
	ferret_y_px: float | None


class SimulatedPylonCamera:
	"""CBaslerUniversalInstantCamera stand-in: 200 fps Mono8, LatestImageOnly."""

	def __init__(self, timing: CameraTiming) -> None:
		self.timing = timing
		self.ExposureTime = timing.exposure_us
		self.AcquisitionFrameRate = timing.frame_rate_fps
		self.PixelFormat = "Mono8"
		self.Width = timing.width_px
		self.Height = timing.height_px
		self.GrabStrategy = "LatestImageOnly"
		# Why: HuntSim treats backend=="pylon" as a live Ace; this is the delay model.
		self.backend = "sim"
		self._next_t0 = 0.0
		self._index = 0
		self._pending: deque[_PendingGrab] = deque()
		self.last_grab_to_frame_ms = 0.0
		self.dropped = 0
		self.delivered = 0
		self._t_s = 0.0
		self._grabbing = False
		self._track = TrackingPipeline(timing.gsd_mm_per_px, timing.frame_rate_fps)

	def open(self) -> None:
		return

	def configure(self) -> None:
		# Why: AceGrabber.configure; timings already applied in __init__.
		return

	def start_grabbing(self) -> None:
		self._next_t0 = 0.0
		self._index = 0
		self._pending.clear()
		self._grabbing = True

	def stop_grabbing(self) -> None:
		self._grabbing = False
		self._pending.clear()

	def close(self) -> None:
		self.stop_grabbing()

	def tick(self, t_s: float, ferret: TrackState) -> None:
		# Why: sample ferret into camera pixels at mid-exposure; chase never sees mm here.
		self._t_s = t_s
		if self._grabbing:
			self._maybe_expose(t_s, ferret)

	def retrieve_frame(self) -> CameraFrame | None:
		if not self._grabbing:
			return None
		latest = self._pop_ready(self._t_s)
		if latest is None:
			return None
		self.delivered += 1
		t0 = latest.sample_s - self.timing.exposure_s * 0.5
		self.last_grab_to_frame_ms = (latest.ready_s - t0) * 1e3
		return CameraFrame(
			frame_index=latest.frame_index,
			camera_ts_ns=int(latest.sample_s * 1e9),
			host_time_ns=int(latest.ready_s * 1e9),
			width_px=self.Width,
			height_px=self.Height,
			ferret_x_px=latest.ferret_x_px,
			ferret_y_px=latest.ferret_y_px,
		)

	def poll(
		self,
		t_s: float,
		ferret: TrackState,
		prey: TrackState,
		trial: TrialPhase,
	) -> TrackingFrame | None:
		del prey
		self.tick(t_s, ferret)
		cam = self.retrieve_frame()
		if cam is None:
			return None
		return self._track.process(cam, trial)

	def world_to_px(self, x_mm: float, y_mm: float) -> tuple[float, float] | None:
		# Why: Ace sees the arena as pixels; outside the AOI there is no blob.
		x_px = x_mm / self.timing.gsd_mm_per_px
		y_px = y_mm / self.timing.gsd_mm_per_px
		if 0.0 <= x_px < self.Width and 0.0 <= y_px < self.Height:
			return x_px, y_px
		return None

	def _maybe_expose(self, t_s: float, ferret: TrackState) -> None:
		period = self.timing.frame_period_s
		while self._next_t0 <= t_s:
			t0 = self._next_t0
			self._next_t0 += period
			px = self.world_to_px(ferret.x_mm, ferret.y_mm) if ferret.valid else None
			# Why: sample at mid-exposure — global shutter still integrates over 3 ms.
			self._pending.append(
				_PendingGrab(
					ready_s=t0 + self.timing.grab_to_track_s,
					sample_s=t0 + self.timing.exposure_s * 0.5,
					frame_index=self._index,
					ferret_x_px=None if px is None else px[0],
					ferret_y_px=None if px is None else px[1],
				)
			)
			self._index += 1
			# LatestImageOnly: keep one in-flight burst, drop the oldest extra.
			while len(self._pending) > 4:
				self._pending.popleft()
				self.dropped += 1

	def _pop_ready(self, t_s: float) -> _PendingGrab | None:
		latest: _PendingGrab | None = None
		while self._pending and self._pending[0].ready_s <= t_s:
			latest = self._pending.popleft()
			if self._pending and self._pending[0].ready_s <= t_s:
				self.dropped += 1
		return latest
