"""Soft keep-away policy. Stub: do not lift simulation/chase_policy.py yet."""

from __future__ import annotations

from chase.decision import ChaseDecision
from vision.tracking_frame import TrackingFrame, TrialPhase


def compute_chase_decision(
	scene: TrackingFrame,
	cfg: object,
	width_mm: float,
	height_mm: float,
) -> ChaseDecision:
	# Why: TrackingFrame → velocity command; idle unless TrialPhase.running.
	del cfg, width_mm, height_mm
	out = ChaseDecision(decision_time_ns=scene.host_time_ns)
	if scene.trial_phase != TrialPhase.running:
		out.reason = "trial_not_running"
		return out
	if not scene.both_valid():
		out.reason = "tracks_invalid"
		return out
	# Why: keep-away math stays in simulation until we lift it behind this API.
	out.reason = "stub_idle"
	return out
