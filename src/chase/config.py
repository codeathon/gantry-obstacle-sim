"""Chase policy config. Why: chase must not import simulation to stay hardware-safe."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ChasePolicyConfig:
	"""Soft keep-away gains. Speeds stay low so the chase stays playable."""

	preferred_gap_mm: float
	min_gap_mm: float
	max_pull_mm: float
	away_gain: float
	toward_gain: float
	lateral_gain: float
	wall_margin_mm: float
	wall_gain: float
	corner_gain: float
	velocity_gain_s: float
	max_engage_speed_mm_s: float
	# Kept for HUD rings / older fields; not used for discrete flees anymore.
	cone_half_angle_deg: float
	threat_distance_mm: float
	creep_distance_mm: float
