"""AnimalDetector: ferret blob in Mono8, toy discarded via encoder XY."""

from __future__ import annotations

import time

from basler.types import CameraFrame
from vision.detect import AnimalDetector, _bytes_centroid
from vision.pipeline import TrackingPipeline
from vision.tracking_frame import TrialPhase


def _frame(w: int, h: int, pixels: bytes | bytearray, idx: int = 1) -> CameraFrame:
	return CameraFrame(
		frame_index=idx,
		host_time_ns=time.time_ns(),
		width_px=w,
		height_px=h,
		pixels=bytes(pixels),
		grab_ok=True,
	)


def _paint(buf: bytearray, w: int, x0: int, y0: int, x1: int, y1: int, v: int = 255) -> None:
	for y in range(y0, y1):
		for x in range(x0, x1):
			buf[y * w + x] = v


def _tiny_detector() -> AnimalDetector:
	# Why: 32×32 tests need a tiny exclude disc and one warmup frame.
	return AnimalDetector(gsd_mm_per_px=1.0, min_area=4.0, exclude_mm=8.0, warmup_frames=1)


def test_warmup_returns_none() -> None:
	det = _tiny_detector()
	bg = bytearray(32 * 32)
	assert det.update(_frame(32, 32, bg)) is None


def test_blob_centroid_after_warmup() -> None:
	det = _tiny_detector()
	bg = bytearray(32 * 32)
	det.update(_frame(32, 32, bg, idx=1))
	img = bytearray(32 * 32)
	_paint(img, 32, 4, 14, 9, 19)
	xy = det.update(_frame(32, 32, img, idx=2))
	assert xy is not None
	assert abs(xy[0] - 6.0) < 0.1
	assert abs(xy[1] - 16.0) < 0.1


def test_toy_blob_near_encoder_is_ignored() -> None:
	# Why: ferret and toy can both be in the Ace FOV; chase wants the animal.
	det = _tiny_detector()
	bg = bytearray(32 * 32)
	det.update(_frame(32, 32, bg, idx=1))
	img = bytearray(32 * 32)
	_paint(img, 32, 18, 14, 23, 19)
	assert det.update(_frame(32, 32, img, idx=2), prey_xy_mm=(20.0, 16.0)) is None


def test_ferret_far_from_encoder_is_kept() -> None:
	det = _tiny_detector()
	bg = bytearray(32 * 32)
	det.update(_frame(32, 32, bg, idx=1))
	img = bytearray(32 * 32)
	_paint(img, 32, 4, 14, 9, 19)
	xy = det.update(_frame(32, 32, img, idx=2), prey_xy_mm=(20.0, 16.0))
	assert xy is not None
	assert abs(xy[0] - 6.0) < 0.1


def test_pipeline_maps_blob_px_times_gsd() -> None:
	# Why: live Ace has Mono8 only; ferret_x_px is the sim pointer path.
	gsd = 1.035
	pipe = TrackingPipeline(
		gsd_mm_per_px=gsd,
		detector=AnimalDetector(gsd, min_area=4.0, exclude_mm=8.0, warmup_frames=1),
	)
	bg = bytearray(32 * 32)
	pipe.process(_frame(32, 32, bg, idx=1), TrialPhase.running)
	img = bytearray(32 * 32)
	_paint(img, 32, 4, 14, 9, 19)
	scene = pipe.process(_frame(32, 32, img, idx=2), TrialPhase.running)
	assert scene.ferret.valid
	assert abs(scene.ferret.x_px - 6.0) < 0.1
	assert abs(scene.ferret.x_mm - 6.0 * gsd) < 1e-6


def test_bytes_centroid_fallback() -> None:
	# Why: CI can stay numpy-free; live 1920×1200 uses the numpy path.
	w, h = 8, 8
	bg = bytes(w * h)
	img = bytearray(w * h)
	_paint(img, w, 2, 2, 5, 5)
	xy = _bytes_centroid(bytes(img), w, h, bg, None, 1.0, 4)
	assert xy is not None
	assert abs(xy[0] - 3.0) < 0.1
	assert abs(xy[1] - 3.0) < 0.1
