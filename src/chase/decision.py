"""ChaseDecision. Why: pure policy output — no hardware I/O in this struct."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ChaseDecision:
	decision_time_ns: int = 0
	target_vx_mm_s: float = 0.0
	target_vy_mm_s: float = 0.0
	enable_motion: bool = False
	reason: str = "stub"
	gap_error_mm: float = 0.0
	wall_push: float = 0.0
	threat: float = 0.0
