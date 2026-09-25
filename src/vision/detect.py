"""Ferret blob in Ace pixels. Why: chase uses the animal, not the toy carriage."""

from __future__ import annotations

from basler.types import CameraFrame
from vision.associator import Blob, ObjectAssociator, VisionPriors
from vision.tracking_frame import AceBlob


class AnimalDetector:
	"""Foreground ferret centroid, ignoring a disc around the encoder prey."""

	def __init__(
		self,
		gsd_mm_per_px: float = 1.035,
		min_area: float = 200.0,
		# Why: carriage + nearby shadow; 80 mm missed the lab toy blob.
		exclude_mm: float = 150.0,
		warmup_frames: int = 30,
		associator: ObjectAssociator | None = None,
	) -> None:
		self._gsd = gsd_mm_per_px
		self._min_area = min_area
		self._exclude_px = exclude_mm / max(gsd_mm_per_px, 1e-6)
		self._warmup = warmup_frames
		self._n = 0
		self._bg: object | None = None
		# Why: pylon-track associator needs the last ferret px as a prior.
		self._prior_px: tuple[float, float] | None = None
		self._associator = associator or ObjectAssociator(
			VisionPriors(ferret_area_px_min=min_area)
		)
		# Why: HUD overlays every Ace blob, including the dropped toy.
		self.last_blobs: list[AceBlob] = []

	def update(
		self,
		frame: CameraFrame,
		prey_xy_mm: tuple[float, float] | None = None,
		prey_px: tuple[float, float] | None = None,
	) -> tuple[float, float] | None:
		# Why: sim already stamps ferret_x_px; live Ace only has Mono8 bytes.
		# prey_xy_mm is arena/FOV millimetres unless prey_px is already Ace pixels.
		if frame.pixels is None or not frame.grab_ok:
			return None
		self._n += 1
		img = _mono8(frame)
		if self._n <= self._warmup:
			self.last_blobs = []
			self._learn(frame, img, 0.01)
			return None
		if prey_px is None and prey_xy_mm is not None:
			prey_px = (prey_xy_mm[0] / self._gsd, prey_xy_mm[1] / self._gsd)
		hit = self._centroid(frame, img, prey_px)
		# Why: pylon-track MOG2 keeps learning after warmup (lr 0.002).
		self._learn(frame, img, 0.002)
		self._prior_px = hit
		return hit

	def _learn(self, frame: CameraFrame, img, lr: float) -> None:
		if img is not None:
			self._bg = _blend_bg(self._bg, img, lr)
			return
		if self._bg is None:
			self._bg = bytes(frame.pixels)

	def _centroid(
		self, frame: CameraFrame, img, prey_px: tuple[float, float] | None
	) -> tuple[float, float] | None:
		if img is not None:
			hit, ids = _numpy_ferret(
				img, self._bg, prey_px, self._exclude_px, self._min_area,
				self._associator, self._prior_px,
			)
			self.last_blobs = ids
			return hit
		hit = _bytes_centroid(
			bytes(frame.pixels),
			frame.width_px,
			frame.height_px,
			self._bg if isinstance(self._bg, (bytes, bytearray)) else None,
			prey_px,
			self._exclude_px,
			int(self._min_area),
		)
		self.last_blobs = _id_hit(hit, prey_px)
		return hit


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


def _blend_bg(bg, img, lr: float):
	import numpy as np

	cur = img.astype(np.float32) if hasattr(img, "astype") else np.asarray(img, np.float32)
	if bg is None or not hasattr(bg, "dtype"):
		return cur
	# Why: pylon-track MOG2 apply(lr) — 0.01 warmup / 0.002 live.
	return (1.0 - lr) * bg + lr * cur


def _numpy_ferret(img, bg, prey_px, exclude_px: float, min_area: float, associator, prior_px):
	import numpy as np

	if bg is None:
		return None, []
	bg_f = bg if getattr(bg, "dtype", None) is not None else np.asarray(bg, dtype=np.float32)
	mask = np.abs(img.astype(np.float32) - bg_f) > 20.0
	raw = _numpy_blobs(mask, min_area)
	# Why: one FOV blob with the encoder in-frame is the toy, not a ferret.
	kept = _drop_toy(raw, prey_px, img.shape[1], img.shape[0], exclude_px)
	picked = associator.pick_ferret(kept, prior_px)
	ids = _id_blobs(raw, picked, prey_px, exclude_px)
	if picked is None:
		return None, ids
	return (picked.x_px, picked.y_px), ids


def _drop_toy(
	blobs: list[Blob],
	prey_px: tuple[float, float] | None,
	width: int,
	height: int,
	exclude_px: float,
) -> list[Blob]:
	if prey_px is None or not blobs:
		return blobs
	# Why: Charuco tilt can park the encoder a few px outside the raster.
	pad = max(exclude_px, 80.0)
	in_frame = -pad <= prey_px[0] < width + pad and -pad <= prey_px[1] < height + pad
	if in_frame and len(blobs) == 1:
		return []
	r2 = exclude_px * exclude_px
	return [
		b for b in blobs
		if (b.x_px - prey_px[0]) ** 2 + (b.y_px - prey_px[1]) ** 2 > r2
	]


def _id_blobs(
	raw: list[Blob],
	picked: Blob | None,
	prey_px: tuple[float, float] | None,
	exclude_px: float,
) -> list[AceBlob]:
	# Why: overlay must show the dropped toy as well as the chase ferret.
	r2 = exclude_px * exclude_px
	out: list[AceBlob] = []
	for b in raw:
		near = (
			prey_px is not None
			and (b.x_px - prey_px[0]) ** 2 + (b.y_px - prey_px[1]) ** 2 <= r2
		)
		if picked is not None and b is picked:
			label = "ferret"
		elif near or (picked is None and prey_px is not None):
			label = "toy"
		else:
			label = "other"
		out.append(AceBlob(label, b.x_px, b.y_px, area_px=b.area_px))
	return out


def _id_hit(
	hit: tuple[float, float] | None, prey_px: tuple[float, float] | None
) -> list[AceBlob]:
	if hit is None:
		return []
	del prey_px
	return [AceBlob("ferret", hit[0], hit[1])]


def _numpy_blobs(mask, min_area: float, max_span_px: float = 600.0) -> list[Blob]:
	import numpy as np

	# Why: 4× downsample keeps CC cheap at 1920×1200 without OpenCV.
	step = 4 if mask.shape[0] * mask.shape[1] > 64 * 64 else 1
	small = mask[::step, ::step]
	h, w = small.shape
	seen = np.zeros((h, w), dtype=np.uint8)
	blobs: list[Blob] = []
	for y in range(h):
		for x in range(w):
			if not small[y, x] or seen[y, x]:
				continue
			blob, span = _flood(small, seen, y, x, step)
			# Why: the moving XXY crossbar is longer than a ferret.
			if blob.area_px >= min_area and span <= max_span_px:
				blobs.append(blob)
	return blobs


def _flood(small, seen, y0: int, x0: int, step: int) -> tuple[Blob, float]:
	h, w = small.shape
	stack = [(y0, x0)]
	seen[y0, x0] = 1
	sx = sy = n = 0
	xmin = xmax = x0
	ymin = ymax = y0
	while stack:
		cy, cx = stack.pop()
		sx += cx
		sy += cy
		n += 1
		xmin, xmax = min(xmin, cx), max(xmax, cx)
		ymin, ymax = min(ymin, cy), max(ymax, cy)
		for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1)):
			ny, nx = cy + dy, cx + dx
			if 0 <= ny < h and 0 <= nx < w and small[ny, nx] and not seen[ny, nx]:
				seen[ny, nx] = 1
				stack.append((ny, nx))
	span = max(xmax - xmin, ymax - ymin) * step
	return Blob((sx / n) * step, (sy / n) * step, float(n * step * step)), span


def _away_from_prey(shape, prey_px, exclude_px: float):
	import numpy as np

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
