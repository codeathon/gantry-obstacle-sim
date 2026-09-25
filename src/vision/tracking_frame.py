"""Scene packet matching pylon-track TrackingFrame (mm, host_time_ns).

Why here: chase and sim both import this so prey/ferret units stay one type.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class TrialPhase(str, Enum):
	warmup = "warmup"
	running = "running"
	ended = "ended"


@dataclass
class AceBlob:
	# Why: HUD overlay shows what Ace labeled, not only the chase ferret.
	label: str
	x_px: float
	y_px: float
	x_mm: float = 0.0
	y_mm: float = 0.0
	area_px: float = 0.0


@dataclass
class TrackState:
	x_mm: float = 0.0
	y_mm: float = 0.0
	speed_mm_s: float = 0.0
	direction_deg: float = 0.0
	valid: bool = False
	# Why: camera detections live in pixels; mm is GSD times this, as in pylon-track.
	x_px: float = 0.0
	y_px: float = 0.0


@dataclass
class TrackingQuality:
	ferret_confidence: float = 0.0
	prey_confidence: float = 0.0
	reject_reason: str | None = None


@dataclass
class TrackingFrame:
	frame_index: int = 0
	camera_ts_ticks: int = 0
	host_time_ns: int = 0
	ferret: TrackState = field(default_factory=TrackState)
	prey: TrackState = field(default_factory=TrackState)
	quality: TrackingQuality = field(default_factory=TrackingQuality)
	distance_mm: float = -1.0
	bearing_deg: float = 0.0
	closing_speed_mm_s: float = 0.0
	trial_phase: TrialPhase = TrialPhase.warmup
	ace_blobs: list[AceBlob] = field(default_factory=list)

	def both_valid(self) -> bool:
		return self.ferret.valid and self.prey.valid
