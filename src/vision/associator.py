"""pylon-track ObjectAssociator: pick the ferret blob by area + continuity."""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class Blob:
	x_px: float
	y_px: float
	area_px: float


@dataclass(frozen=True)
class VisionPriors:
	# Why: pylon-track VisionConfig; 200 px is this repo's live Ace floor.
	ferret_area_px_min: float = 200.0
	ferret_area_px_max: float = 60000.0
	proximity_px: float = 120.0


class ObjectAssociator:
	def __init__(self, priors: VisionPriors | None = None) -> None:
		self._p = priors or VisionPriors()

	def pick_ferret(
		self, blobs: list[Blob], prior_px: tuple[float, float] | None = None
	) -> Blob | None:
		# Why: area prior rejects chain/pulley leftovers; proximity keeps ID.
		best: Blob | None = None
		best_score = -1.0
		for blob in blobs:
			if not _area_ok(blob.area_px, self._p.ferret_area_px_min, self._p.ferret_area_px_max):
				continue
			score = 0.6 * _area_fit(
				blob.area_px, self._p.ferret_area_px_min, self._p.ferret_area_px_max
			) + 0.4 * _proximity(blob.x_px, blob.y_px, prior_px, self._p.proximity_px)
			if score > best_score:
				best_score = score
				best = blob
		if best is not None:
			return best
		# Why: 32×32 tests and small AOIs sit below the live ferret area band.
		return max(blobs, key=lambda b: b.area_px) if blobs else None


def _area_ok(area: float, lo: float, hi: float) -> bool:
	return lo <= area <= hi


def _area_fit(area: float, lo: float, hi: float) -> float:
	mid = 0.5 * (lo + hi)
	half = 0.5 * (hi - lo)
	if half < 1e-3:
		return 1.0
	return max(0.0, 1.0 - abs(area - mid) / half)


def _proximity(
	x_px: float, y_px: float, prior_px: tuple[float, float] | None, scale: float
) -> float:
	if prior_px is None:
		return 0.5
	dist = math.hypot(x_px - prior_px[0], y_px - prior_px[1])
	return math.exp(-dist / max(scale, 1e-6))
