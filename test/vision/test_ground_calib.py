"""Charuco camera_calibration.toml: acA1300-200um onto the arena floor."""

from basler.types import CameraFrame
from vision.ground_calib import ground_cam_for_serial, load_ground_cams, px_to_arena, px_to_world
from vision.pipeline import TrackingPipeline
from vision.tracking_frame import TrialPhase


def test_loads_lab_serials() -> None:
	cams = load_ground_cams()
	assert set(cams) == {
		"24676894",
		"24908831",
		"24908832",
		"25000609",
		"25006505",
	}


def test_overhead_200um_gsd_is_not_ace2() -> None:
	# Why: a2A1920 1.035 mm/px is the missing hunt camera, not this Ace.
	cam = ground_cam_for_serial("24676894")
	assert cam is not None
	assert cam.width_px == 1280
	assert cam.height_px == 1024
	assert 0.80 < cam.gsd_mm_per_px < 0.95
	assert 1000.0 < cam.width_mm < 1300.0
	assert 800.0 < cam.height_mm < 1100.0


def test_optical_axis_hits_near_camera_nadir() -> None:
	cam = ground_cam_for_serial("24676894")
	assert cam is not None
	wx, wy = px_to_world(cam, cam.cx, cam.cy)
	# Optical axis at ~1.08 m; small tilt shifts the floor hit ~30 mm.
	assert abs(wx - 25.8) < 2.0
	assert abs(wy - 76.3) < 2.0


def test_image_corners_stay_inside_footprint() -> None:
	# Why: tilt means pixel (0,0) is not the AABB origin; it must still be in-box.
	cam = ground_cam_for_serial("24676894")
	assert cam is not None
	for u, v in ((0.0, 0.0), (cam.width_px - 1.0, 0.0), (0.0, cam.height_px - 1.0)):
		ax, ay = px_to_arena(cam, u, v)
		assert -1.0 <= ax <= cam.width_mm + 1.0
		assert -1.0 <= ay <= cam.height_mm + 1.0


def test_pipeline_uses_ground_not_ace2_gsd() -> None:
	cam = ground_cam_for_serial("24676894")
	assert cam is not None
	pipe = TrackingPipeline(gsd_mm_per_px=1.035, ground=cam)
	frame = CameraFrame(host_time_ns=1, ferret_x_px=cam.cx, ferret_y_px=cam.cy)
	scene = pipe.process(frame, TrialPhase.running)
	assert scene.ferret.valid
	# Principal point is inside the footprint, not 639.5 * 1.035 ≈ 662 mm.
	assert 400.0 < scene.ferret.x_mm < 800.0
	assert abs(scene.ferret.x_mm - cam.cx * 1.035) > 50.0
