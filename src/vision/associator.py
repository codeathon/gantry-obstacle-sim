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
	# Why: Mini is ~1–4k px; the old mid-band score preferred the XXY carriage.
	prefer_compact: bool = False
	ferret_area_px_pref: float = 1600.0


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
			score = _score_blob(blob, self._p, prior_px)
			if score > best_score:
				best_score = score
				best = blob
		if best is not None:
			return best
		# Why: a gantry beam/shadow leftover must not become the ferret.
		return None


def _score_blob(blob: Blob, p: VisionPriors, prior_px) -> float:
	prox = _proximity(blob.x_px, blob.y_px, prior_px, p.proximity_px)
	if p.prefer_compact:
		return 0.65 * _compact(blob.area_px, p) + 0.35 * prox
	return 0.6 * _area_fit(
		blob.area_px, p.ferret_area_px_min, p.ferret_area_px_max
	) + 0.4 * prox


def _compact(area: float, p: VisionPriors) -> float:
	span = max(
		abs(p.ferret_area_px_max - p.ferret_area_px_pref),
		abs(p.ferret_area_px_pref - p.ferret_area_px_min),
		1.0,
	)
	return max(0.0, 1.0 - abs(area - p.ferret_area_px_pref) / span)


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
