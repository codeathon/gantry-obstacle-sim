"""50 Hz chase loop. Why: motor thread is not the Pylon grab callback."""

from __future__ import annotations

from chase.decision import ChaseDecision
from chase.policy import compute_chase_decision
from vision.tracking_frame import TrackingFrame
from zaber.protocol import Gantry


class ChaseController:
	def __init__(self, gantry: Gantry, cfg: object = None) -> None:
		self._gantry = gantry
		self._cfg = cfg
		# Why: arena mm from sim.json; stub policy never uses them for motion.
		self._w = 1987.0
		self._h = 1242.0
		self._period_s = 0.02
		self._stale_s = 0.08
		self._next_s = 0.0
		self._latest: TrackingFrame | None = None
		self.last_decision = ChaseDecision()
		self.stale_stops = 0

	def submit_frame(self, frame: TrackingFrame) -> None:
		# Why: camera thread copies latest frame under a lock, like pylon-track.
		self._latest = frame

	def poll(self, t_s: float) -> None:
		# Why: 50 Hz; stale frame → gantry.stop(); else move_velocity only.
		if t_s < self._next_s:
			return
		self._next_s = t_s + self._period_s
		frame = self._latest
		if frame is None:
			return
		age_s = t_s - frame.host_time_ns * 1e-9
		if age_s > self._stale_s:
			self._gantry.stop()
			self.stale_stops += 1
			self.last_decision = ChaseDecision(reason="stale_frame")
			return
		self._apply(frame)

	def _apply(self, frame: TrackingFrame) -> None:
		decision = compute_chase_decision(frame, self._cfg, self._w, self._h)
		self.last_decision = decision
		if not decision.enable_motion:
			self._gantry.stop()
			return
		self._gantry.move_velocity(decision.target_vx_mm_s, decision.target_vy_mm_s)
