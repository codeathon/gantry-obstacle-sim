"""Tracking pipeline. Why: MOG2/associator stay here, not in basler grab."""

from __future__ import annotations

from basler.types import CameraFrame
from vision.tracking_frame import TrackingFrame, TrialPhase


class TrackingPipeline:
	def process(self, camera_frame: CameraFrame, trial: TrialPhase) -> TrackingFrame:
		# Why: CameraFrame in, TrackingFrame out — no Pylon or Zaber types.
		# Stub copies timestamps only; ferret/prey stay invalid until real MOG2.
		return TrackingFrame(
			frame_index=camera_frame.frame_index,
			camera_ts_ticks=camera_frame.camera_ts_ns,
			host_time_ns=camera_frame.host_time_ns,
			trial_phase=trial,
		)
