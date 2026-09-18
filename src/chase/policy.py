"""Soft keep-away policy. Stub: do not lift simulation/chase_policy.py yet."""

from __future__ import annotations

from chase.decision import ChaseDecision
from vision.tracking_frame import TrackingFrame


def compute_chase_decision(
	scene: TrackingFrame,
	cfg: object,
	width_mm: float,
	height_mm: float,
) -> ChaseDecision:
	# Why: TrackingFrame → velocity command; idle unless TrialPhase.running.
	raise NotImplementedError("pure chase policy")
