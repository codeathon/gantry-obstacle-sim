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
