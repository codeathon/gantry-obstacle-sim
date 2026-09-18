"""50 Hz chase loop. Why: motor thread is not the Pylon grab callback."""

from __future__ import annotations

from vision.tracking_frame import TrackingFrame
from zaber.protocol import Gantry


class ChaseController:
	def __init__(self, gantry: Gantry, cfg: object) -> None:
		self._gantry = gantry
		self._cfg = cfg

	def submit_frame(self, frame: TrackingFrame) -> None:
		# Why: camera thread copies latest frame under a lock, like pylon-track.
		raise NotImplementedError("store latest TrackingFrame")

	def poll(self, t_s: float) -> None:
		# Why: 50 Hz; stale frame → gantry.stop(); else move_velocity only.
		raise NotImplementedError("50 Hz compute_chase_decision + move_velocity")
