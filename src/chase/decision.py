"""ChaseDecision. Why: pure policy output — no hardware I/O in this struct."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ChaseDecision:
	decision_time_ns: int = 0
	target_vx_mm_s: float = 0.0
	target_vy_mm_s: float = 0.0
	flee_direction_deg: float = 0.0
	threat: float = 0.0
	dist_threat: float = 0.0
	cone_threat: float = 0.0
	approach_threat: float = 0.0
	enable_motion: bool = False
	use_planned_flee: bool = False
	flee_x_mm: float = 0.0
	flee_y_mm: float = 0.0
	flee_mm: float = 0.0
	flee_speed_mm_s: float = 0.0
	gap_error_mm: float = 0.0
	wall_push: float = 0.0
	reason: str = "idle"
