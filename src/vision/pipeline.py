"""Tracking pipeline. Why: MOG2/associator stay here, not in basler grab."""

from __future__ import annotations

import math

from basler.types import CameraFrame
from vision.detect import AnimalDetector
from vision.ground_calib import GroundCam, px_to_arena
from vision.tracking_frame import TrackingFrame, TrackingQuality, TrackState, TrialPhase


class TrackingPipeline:
	def __init__(
		self,
		gsd_mm_per_px: float = 1.035,
		fps: float = 200.0,
		detector: AnimalDetector | None = None,
		ground: GroundCam | None = None,
	) -> None:
		# Why: pylon-track pos_mm = pos_px * GSD unless Charuco ground is loaded.
		self._gsd = gsd_mm_per_px
		self._ground = ground
		self._fps = fps
		self._prev_px: tuple[float, float] | None = None
		self._prev_ns = 0
		# Why: pylon-track kMaxCoastFrames (~0.15 s at 200 fps).
		self._miss = 0
		self._max_coast = 30
		# Why: tests shrink warmup/exclude; live Ace uses AnimalDetector defaults.
		self._detector = detector or AnimalDetector(gsd_mm_per_px=gsd_mm_per_px)

	def process(
		self,
		camera_frame: CameraFrame,
		trial: TrialPhase,
		prey_xy_mm: tuple[float, float] | None = None,
	) -> TrackingFrame:
		# Why: CameraFrame in, TrackingFrame out — no Pylon or Zaber types.
		# prey_xy_mm must be arena/FOV mm so detector px = mm / GSD.
		ferret = self._ferret_from_camera(camera_frame, prey_xy_mm)
		quality = TrackingQuality()
		if ferret.valid:
			# Why: pylon-track halves confidence while coasting a missed blob.
			quality.ferret_confidence = 1.0 if self._miss == 0 else 0.5
		return TrackingFrame(
			frame_index=camera_frame.frame_index,
			camera_ts_ticks=camera_frame.camera_ts_ns,
			host_time_ns=camera_frame.host_time_ns,
			ferret=ferret,
			quality=quality,
			trial_phase=trial,
		)

	def _ferret_from_camera(
		self, frame: CameraFrame, prey_xy_mm: tuple[float, float] | None
	) -> TrackState:
		x_px, y_px = frame.ferret_x_px, frame.ferret_y_px
		if x_px is None or y_px is None:
			# Why: live Ace has Mono8 only; ignore the toy blob via encoder XY.
			hit = self._detector.update(frame, prey_xy_mm)
			if hit is None:
				return self._coast_ferret()
			x_px, y_px = hit
		self._miss = 0
		return self._track_px(x_px, y_px, frame.host_time_ns)

	def _coast_ferret(self) -> TrackState:
		# Why: pylon-track coasts Kalman; hold last Ace px so chase does not drop.
		self._miss += 1
		if self._prev_px is None or self._miss > self._max_coast:
			self._prev_px = None
			return TrackState()
		x_px, y_px = self._prev_px
		x_mm, y_mm = self._px_to_mm(x_px, y_px)
		return TrackState(x_mm=x_mm, y_mm=y_mm, valid=True, x_px=x_px, y_px=y_px)

	def _track_px(self, x_px: float, y_px: float, host_ns: int) -> TrackState:
		speed, direction = self._motion_from_px(x_px, y_px, host_ns)
		self._prev_px = (x_px, y_px)
		self._prev_ns = host_ns
		x_mm, y_mm = self._px_to_mm(x_px, y_px)
		return TrackState(
			x_mm=x_mm,
			y_mm=y_mm,
			speed_mm_s=speed,
			direction_deg=direction,
			valid=True,
			x_px=x_px,
			y_px=y_px,
		)

	def _px_to_mm(self, x_px: float, y_px: float) -> tuple[float, float]:
		if self._ground is None:
			return x_px * self._gsd, y_px * self._gsd
		return px_to_arena(self._ground, x_px, y_px)

	def _motion_from_px(self, x_px: float, y_px: float, host_ns: int) -> tuple[float, float]:
		# Why: speed is arena mm (plane hit or GSD), not raw px when Charuco is on.
		if self._prev_px is None:
			return 0.0, 0.0
		dt_s = (host_ns - self._prev_ns) * 1e-9
		if dt_s < 1e-6:
			dt_s = 1.0 / max(self._fps, 1.0)
		x0, y0 = self._px_to_mm(*self._prev_px)
		x1, y1 = self._px_to_mm(x_px, y_px)
		speed = math.hypot(x1 - x0, y1 - y0) / dt_s
		direction = 0.0
		if speed > 5.0:
			direction = math.degrees(math.atan2(-(y1 - y0), x1 - x0))
		return speed, direction
