"""Animal blob in Ace pixels. Why: chase uses the mouse, not the toy carriage."""

from __future__ import annotations

from basler.types import CameraFrame


class AnimalDetector:
	"""Foreground centroid, ignoring a disc around the encoder prey."""

	def __init__(
		self,
		gsd_mm_per_px: float = 1.035,
		min_area: float = 200.0,
		exclude_mm: float = 80.0,
		warmup_frames: int = 30,
	) -> None:
		self._gsd = gsd_mm_per_px
		self._min_area = min_area
		self._exclude_px = exclude_mm / max(gsd_mm_per_px, 1e-6)
		self._warmup = warmup_frames
		self._n = 0
		self._bg: object | None = None

	def update(
		self, frame: CameraFrame, prey_xy_mm: tuple[float, float] | None = None
	) -> tuple[float, float] | None:
		# Why: sim already stamps ferret_x_px; live Ace only has Mono8 bytes.
		if frame.pixels is None or not frame.grab_ok:
			return None
		self._n += 1
		if self._n <= self._warmup:
			self._learn(frame)
			return None
		prey_px = None
		if prey_xy_mm is not None:
			prey_px = (prey_xy_mm[0] / self._gsd, prey_xy_mm[1] / self._gsd)
		return self._centroid(frame, prey_px)

	def _learn(self, frame: CameraFrame) -> None:
		img = _mono8(frame)
		if img is None:
			self._bg = bytes(frame.pixels)
			return
		self._bg = img.astype("float32") if hasattr(img, "astype") else img

	def _centroid(
		self, frame: CameraFrame, prey_px: tuple[float, float] | None
	) -> tuple[float, float] | None:
		img = _mono8(frame)
		if img is not None:
			return _numpy_centroid(img, self._bg, prey_px, self._exclude_px, self._min_area)
		return _bytes_centroid(
			bytes(frame.pixels),
			frame.width_px,
			frame.height_px,
			self._bg if isinstance(self._bg, (bytes, bytearray)) else None,
			prey_px,
			self._exclude_px,
			int(self._min_area),
		)


def _mono8(frame: CameraFrame):
	try:
		import numpy as np
	except ImportError:
		return None
	buf = frame.pixels
	if buf is None:
		return None
	try:
		# Why: nested Python loops cannot keep 1920×1200 at Ace fps.
		return np.frombuffer(buf, dtype=np.uint8).reshape(frame.height_px, frame.width_px)
	except ValueError:
		return None


def _numpy_centroid(img, bg, prey_px, exclude_px: float, min_area: float):
	import numpy as np

	if bg is None:
		return None
	bg_f = bg if getattr(bg, "dtype", None) is not None else np.asarray(bg, dtype=np.float32)
	mask = np.abs(img.astype(np.float32) - bg_f) > 20.0
	if prey_px is not None:
		mask &= _away_from_prey(img.shape, prey_px, exclude_px)
	ys, xs = np.nonzero(mask)
	if xs.size < min_area:
		return None
	return float(xs.mean()), float(ys.mean())


def _away_from_prey(shape, prey_px, exclude_px: float):
	import numpy as np

	# Why: encoder disc drops the toy so the mouse centroid is not the carriage.
	yy, xx = np.ogrid[: shape[0], : shape[1]]
	r2 = exclude_px * exclude_px
	return (xx - prey_px[0]) ** 2 + (yy - prey_px[1]) ** 2 > r2


def _bytes_centroid(
	pixels: bytes,
	width: int,
	height: int,
	bg: bytes | None,
	prey_px: tuple[float, float] | None,
	exclude_px: float,
	min_area: int,
) -> tuple[float, float] | None:
	# Why: unit tests stay numpy-free; live 1920×1200 uses numpy above.
	if bg is None or len(bg) != len(pixels):
		return None
	sx = sy = n = 0
	r2 = exclude_px * exclude_px
	for y in range(height):
		row = y * width
		for x in range(width):
			i = row + x
			if abs(pixels[i] - bg[i]) <= 20:
				continue
			if prey_px is not None:
				dx = x - prey_px[0]
				dy = y - prey_px[1]
				if dx * dx + dy * dy <= r2:
					continue
			sx += x
			sy += y
			n += 1
	if n < min_area:
		return None
	return sx / n, sy / n
