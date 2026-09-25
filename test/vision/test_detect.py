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


def test_lone_blob_in_frame_with_encoder_is_toy() -> None:
	# Why: empty arena except the carriage — do not invent a ferret.
	det = _tiny_detector()
	bg = bytearray(32 * 32)
	det.update(_frame(32, 32, bg, idx=1))
	img = bytearray(32 * 32)
	_paint(img, 32, 4, 14, 9, 19)
	assert det.update(_frame(32, 32, img, idx=2), prey_xy_mm=(20.0, 16.0)) is None


def test_two_blobs_labeled_ferret_and_toy() -> None:
	# Why: HUD overlay needs Ace IDs, not only the chase ferret centroid.
	det = _tiny_detector()
	bg = bytearray(32 * 32)
	det.update(_frame(32, 32, bg, idx=1))
	img = bytearray(32 * 32)
	_paint(img, 32, 4, 14, 9, 19)
	_paint(img, 32, 18, 14, 23, 19)
	xy = det.update(_frame(32, 32, img, idx=2), prey_xy_mm=(20.0, 16.0))
	assert xy is not None
	labels = sorted(b.label for b in det.last_blobs)
	assert labels == ["ferret", "toy"]


def test_lone_encoder_blob_labeled_toy() -> None:
	det = _tiny_detector()
	bg = bytearray(32 * 32)
	det.update(_frame(32, 32, bg, idx=1))
	img = bytearray(32 * 32)
	_paint(img, 32, 4, 14, 9, 19)
	assert det.update(_frame(32, 32, img, idx=2), prey_xy_mm=(20.0, 16.0)) is None
	assert [b.label for b in det.last_blobs] == ["toy"]


def test_overlay_omits_third_leftover_blob() -> None:
	# Why: a beam leftover must not draw a third Ace ferret on the HUD.
	from vision.associator import Blob
	from vision.detect import _id_blobs

	ferret = Blob(10.0, 10.0, area_px=40.0)
	toy = Blob(40.0, 10.0, area_px=40.0)
	beam = Blob(80.0, 80.0, area_px=400.0)
	ids = _id_blobs([ferret, toy, beam], ferret, (40.0, 10.0), 8.0)
	assert sorted(b.label for b in ids) == ["ferret", "toy"]


def test_same_size_numpy_encoder_keeps_mini() -> None:
	# Why: Mini and carriage match in area; encoder-nearest must stay the toy.
	import numpy as np
	from vision.associator import ObjectAssociator, VisionPriors
	from vision.detect import _numpy_ferret

	assoc = ObjectAssociator(
		VisionPriors(
			ferret_area_px_min=4.0,
			ferret_area_px_max=200.0,
			prefer_compact=True,
			ferret_area_px_pref=25.0,
		)
	)
	bg = np.zeros((32, 32), dtype=np.float32)
	img = np.zeros((32, 32), dtype=np.uint8)
	img[14:19, 4:9] = 255
	img[14:19, 20:25] = 255
	hit, ids = _numpy_ferret(img, bg, (22.0, 16.0), 8.0, 4.0, assoc, (22.0, 16.0))
	assert hit is not None
	assert abs(hit[0] - 6.0) < 2.0
	ferret = next(b for b in ids if b.label == "ferret")
	assert abs(ferret.x_px - 6.0) < 2.0


def test_overlay_same_size_gold_on_mini() -> None:
	# Why: gold Ace ferret must sit on the Mini, not the same-area carriage.
	from vision.associator import Blob, ObjectAssociator, VisionPriors
	from vision.detect import _id_blobs

	priors = VisionPriors(
		ferret_area_px_min=80.0,
		ferret_area_px_max=8000.0,
		prefer_compact=True,
		ferret_area_px_pref=1600.0,
	)
	mini = Blob(20.0, 40.0, area_px=1600.0)
	gantry = Blob(400.0, 40.0, area_px=1600.0)
	prey = (400.0, 40.0)
	picked = ObjectAssociator(priors).pick_ferret(
		[mini, gantry], prior_px=(400.0, 40.0), prey_px=prey
	)
	ids = _id_blobs([mini, gantry], picked, prey, 20.0)
	by_label = {b.label: b for b in ids}
	assert set(by_label) == {"ferret", "toy"}
	assert abs(by_label["ferret"].x_px - 20.0) < 0.1
	assert abs(by_label["toy"].x_px - 400.0) < 0.1


def test_ferret_far_from_encoder_is_kept() -> None:
	det = _tiny_detector()
	bg = bytearray(32 * 32)
	det.update(_frame(32, 32, bg, idx=1))
	img = bytearray(32 * 32)
	_paint(img, 32, 4, 14, 9, 19)
	_paint(img, 32, 18, 14, 23, 19)
	xy = det.update(_frame(32, 32, img, idx=2), prey_xy_mm=(20.0, 16.0))
	assert xy is not None
	assert abs(xy[0] - 6.0) < 1.0


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
	assert scene.ace_blobs
	assert scene.ace_blobs[0].label == "ferret"
	assert abs(scene.ace_blobs[0].x_mm - scene.ferret.x_mm) < 1e-6


def test_good_empty_frame_does_not_coast_a_ghost() -> None:
	# Why: toy-only Ace frames are valid grabs; coasting would keep a fake ferret.
	pipe = TrackingPipeline(
		gsd_mm_per_px=1.0,
		detector=AnimalDetector(1.0, min_area=4.0, exclude_mm=8.0, warmup_frames=1),
	)
	bg = bytearray(32 * 32)
	pipe.process(_frame(32, 32, bg, idx=1), TrialPhase.running)
	img = bytearray(32 * 32)
	_paint(img, 32, 4, 14, 9, 19)
	hit = pipe.process(_frame(32, 32, img, idx=2), TrialPhase.running)
	assert hit.ferret.valid
	empty = pipe.process(
		_frame(32, 32, bg, idx=3), TrialPhase.running, prey_xy_mm=(20.0, 16.0)
	)
	assert not empty.ferret.valid


def test_long_span_beam_is_not_a_ferret() -> None:
	# Why: the moving XXY crossbar is a long foreground streak, not an animal.
	from vision.detect import _numpy_blobs

	import numpy as np

	mask = np.zeros((16, 16), dtype=bool)
	mask[7, :] = True
	assert _numpy_blobs(mask, min_area=4.0, max_span_px=8.0) == []


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
