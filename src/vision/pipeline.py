"""Tracking pipeline. Why: MOG2/associator stay here, not in basler grab."""

from __future__ import annotations

from basler.types import CameraFrame
from vision.tracking_frame import TrackingFrame, TrialPhase


class TrackingPipeline:
	def process(self, camera_frame: CameraFrame, trial: TrialPhase) -> TrackingFrame:
		# Why: CameraFrame in, TrackingFrame out — no Pylon or Zaber types.
		raise NotImplementedError("MOG2 + associator → TrackingFrame")
