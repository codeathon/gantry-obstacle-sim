"""Prey keep-away walls. Why: X-MCC travel is the toy arena, not Ace FOV."""

from __future__ import annotations

from dataclasses import dataclass, replace

from chase.config import ChasePolicyConfig


@dataclass
class ArenaBounds:
	x_min: float = 0.0
	x_max: float = 1987.0
	y_min: float = 0.0
	y_max: float = 1242.0

	@property
	def width_mm(self) -> float:
		return max(self.x_max - self.x_min, 1.0)

	@property
	def height_mm(self) -> float:
		return max(self.y_max - self.y_min, 1.0)

	@property
	def cx(self) -> float:
		return (self.x_min + self.x_max) * 0.5

	@property
	def cy(self) -> float:
		return (self.y_min + self.y_max) * 0.5


def bounds_from_size(width_mm: float, height_mm: float) -> ArenaBounds:
	return ArenaBounds(0.0, width_mm, 0.0, height_mm)


def fit_chase_policy(cfg: ChasePolicyConfig, box: ArenaBounds) -> ChasePolicyConfig:
	# Why: FOV gaps (420 mm) pin a short X-MCC axis against one firmware wall.
	span = min(box.width_mm, box.height_mm)
	pref = min(cfg.preferred_gap_mm, span * 0.35)
	min_gap = min(cfg.min_gap_mm, span * 0.15)
	if cfg.ace_sep_mm > 0.0:
		# Why: shrinking min_gap lets lure park the toy on the Mini; Ace merges.
		sep = min(cfg.ace_sep_mm, span * 0.45)
		min_gap = max(min_gap, sep)
		pref = max(pref, min(cfg.preferred_gap_mm, sep + 80.0))
	return replace(
		cfg,
		preferred_gap_mm=pref,
		min_gap_mm=min_gap,
		max_pull_mm=min(cfg.max_pull_mm, span * 0.30),
		wall_margin_mm=min(cfg.wall_margin_mm, span * 0.18),
		threat_distance_mm=min(cfg.threat_distance_mm, pref),
		creep_distance_mm=min(cfg.creep_distance_mm, pref * 2.0),
	)
