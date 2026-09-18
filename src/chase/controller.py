"""50 Hz chase loop. Why: motor thread is not the Pylon grab callback."""

from __future__ import annotations

import math
import time

from chase.decision import ChaseDecision
from chase.policy import compute_chase_decision
from vision.tracking_frame import TrackingFrame
from zaber.protocol import Gantry


class ChaseController:
	def __init__(
		self,
		gantry: Gantry,
		cfg: object = None,
		width_mm: float = 1987.0,
		height_mm: float = 1242.0,
		period_ms: int = 20,
		stale_ms: float = 80.0,
	) -> None:
		self._gantry = gantry
		self._cfg = cfg
		self._w = width_mm
		self._h = height_mm
		self._period_s = period_ms * 1e-3
		self._stale_s = stale_ms * 1e-3
		self._next_s = 0.0
		self._latest: TrackingFrame | None = None
		self.last_decision = ChaseDecision()
		self.last_decision_ms = 0.0
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
			self.last_decision = ChaseDecision(
				reason="stale_frame", decision_time_ns=frame.host_time_ns
			)
			return
		self._apply(frame)

	def _apply(self, frame: TrackingFrame) -> None:
		t0 = time.perf_counter()
		decision = compute_chase_decision(frame, self._cfg, self._w, self._h)
		self.last_decision_ms = (time.perf_counter() - t0) * 1e3
		self.last_decision = decision
		if not decision.enable_motion:
			self._stop_if_moving()
			return
		# Why: soft keep-away is always velocity — no move_absolute flees.
		self._gantry.move_velocity(decision.target_vx_mm_s, decision.target_vy_mm_s)

	def _stop_if_moving(self) -> None:
		# Why: skip stop when idle so the sim HUD is not flooded with no-op stops.
		busy = getattr(self._gantry, "is_busy", None)
		if callable(busy) and busy():
			self._gantry.stop()
			return
		if math.hypot(*self._gantry.get_velocity()) > 1.0:
			self._gantry.stop()
