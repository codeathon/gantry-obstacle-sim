"""Tracking pipeline. Why: MOG2/associator stay here, not in basler grab."""

from __future__ import annotations

import math

from basler.types import CameraFrame
from vision.tracking_frame import TrackingFrame, TrackingQuality, TrackState, TrialPhase


class TrackingPipeline:
	def __init__(self, gsd_mm_per_px: float = 1.035, fps: float = 200.0) -> None:
		# Why: pylon-track pos_mm = pos_px * GSD; speed from px delta * fps * GSD.
		self._gsd = gsd_mm_per_px
		self._fps = fps
		self._prev_px: tuple[float, float] | None = None
		self._prev_ns = 0

	def process(self, camera_frame: CameraFrame, trial: TrialPhase) -> TrackingFrame:
		# Why: CameraFrame in, TrackingFrame out — no Pylon or Zaber types.
		ferret = self._ferret_from_camera(camera_frame)
		quality = TrackingQuality()
		if ferret.valid:
			quality.ferret_confidence = 1.0
		return TrackingFrame(
			frame_index=camera_frame.frame_index,
			camera_ts_ticks=camera_frame.camera_ts_ns,
			host_time_ns=camera_frame.host_time_ns,
			ferret=ferret,
			quality=quality,
			trial_phase=trial,
		)

	def _ferret_from_camera(self, frame: CameraFrame) -> TrackState:
		if frame.ferret_x_px is None or frame.ferret_y_px is None:
			# Why: no blob → camera did not see the ferret this grab.
			self._prev_px = None
			return TrackState()
		return self._track_px(frame.ferret_x_px, frame.ferret_y_px, frame.host_time_ns)

	def _track_px(self, x_px: float, y_px: float, host_ns: int) -> TrackState:
		speed, direction = self._motion_from_px(x_px, y_px, host_ns)
		self._prev_px = (x_px, y_px)
		self._prev_ns = host_ns
		return TrackState(
			x_mm=x_px * self._gsd,
			y_mm=y_px * self._gsd,
			speed_mm_s=speed,
			direction_deg=direction,
			valid=True,
			x_px=x_px,
			y_px=y_px,
		)

	def _motion_from_px(self, x_px: float, y_px: float, host_ns: int) -> tuple[float, float]:
		# Why: mimic tracker velocity from successive detections, not world truth.
		if self._prev_px is None:
			return 0.0, 0.0
		dt_s = (host_ns - self._prev_ns) * 1e-9
		if dt_s < 1e-6:
			dt_s = 1.0 / max(self._fps, 1.0)
		dx_px = x_px - self._prev_px[0]
		dy_px = y_px - self._prev_px[1]
		speed = math.hypot(dx_px, dy_px) / dt_s * self._gsd
		direction = 0.0
		if speed > 5.0:
			direction = math.degrees(math.atan2(-dy_px, dx_px))
		return speed, direction
