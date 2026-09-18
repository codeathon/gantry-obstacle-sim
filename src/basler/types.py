"""CameraFrame. Why: no chase fields — vision owns TrackingFrame."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class CameraFrame:
	"""Later: numpy Mono8 view plus camera and host timestamps."""

	frame_index: int = 0
	camera_ts_ns: int = 0
	host_time_ns: int = 0
	width_px: int = 0
	height_px: int = 0
	# Why: pixels stay optional so stubs need no numpy yet.
	pixels: object | None = None
	# Why: blob centroid in camera pixels — pipeline maps px→mm like pylon-track.
	ferret_x_px: float | None = None
	ferret_y_px: float | None = None
	grab_ok: bool = False


@dataclass(frozen=True)
class CameraFov:
	"""Live AOI × GSD. Why: hunt millimetres must match the Ace, not a stale crop."""

	width_px: int
	height_px: int
	offset_x: int = 0
	offset_y: int = 0
	gsd_mm_per_px: float = 1.035
	model: str = "a2A1920-160umPRO"

	@property
	def width_mm(self) -> float:
		return self.width_px * self.gsd_mm_per_px

	@property
	def height_mm(self) -> float:
		return self.height_px * self.gsd_mm_per_px
