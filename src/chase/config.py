"""Chase policy config. Why: chase must not import simulation to stay hardware-safe."""

from __future__ import annotations

from dataclasses import dataclass

# Why: Ace merges Mini and carriage inside ~150 mm; hold a wider ring.
ACE_SEP_MM = 250.0


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
	# Why: Mini BLE rolls ~0.5 s; 0 disables lure (real ferret stays snappy).
	lure_speed_mm_s: float = 0.0
	# Why: 0 leaves real-ferret gaps alone; Mini hunts floor the Ace split.
	ace_sep_mm: float = 0.0
