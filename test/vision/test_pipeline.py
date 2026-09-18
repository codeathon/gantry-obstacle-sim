"""TrackingPipeline: timestamps, and px→mm ferret when the camera sees a blob."""

from basler.types import CameraFrame
from vision.pipeline import TrackingPipeline
from vision.tracking_frame import TrialPhase


def test_process_copies_camera_timestamps() -> None:
	cam = CameraFrame(frame_index=7, camera_ts_ns=11, host_time_ns=22, width_px=8)
	scene = TrackingPipeline().process(cam, TrialPhase.running)
	assert scene.frame_index == 7
	assert scene.camera_ts_ticks == 11
	assert scene.host_time_ns == 22
	assert scene.trial_phase == TrialPhase.running
	assert not scene.ferret.valid
	assert not scene.prey.valid


def test_ferret_from_camera_pixels_times_gsd() -> None:
	gsd = 1.035
	pipe = TrackingPipeline(gsd_mm_per_px=gsd, fps=200.0)
	frame = CameraFrame(host_time_ns=1_000_000_000, ferret_x_px=100.0, ferret_y_px=50.0)
	scene = pipe.process(frame, TrialPhase.running)
	assert scene.ferret.valid
	assert abs(scene.ferret.x_mm - 100.0 * gsd) < 1e-9
	assert abs(scene.ferret.y_mm - 50.0 * gsd) < 1e-9
	assert scene.ferret.x_px == 100.0
	assert scene.ferret.speed_mm_s == 0.0


def test_ferret_speed_from_successive_detections() -> None:
	gsd = 1.0
	pipe = TrackingPipeline(gsd_mm_per_px=gsd, fps=200.0)
	t0 = 1_000_000_000
	pipe.process(CameraFrame(host_time_ns=t0, ferret_x_px=0.0, ferret_y_px=0.0), TrialPhase.running)
	# 10 px in 10 ms → 1000 px/s → 1000 mm/s at 1 mm/px.
	dt_ns = 10_000_000
	scene = pipe.process(
		CameraFrame(host_time_ns=t0 + dt_ns, ferret_x_px=10.0, ferret_y_px=0.0),
		TrialPhase.running,
	)
	assert abs(scene.ferret.speed_mm_s - 1000.0) < 1.0
	assert abs(scene.ferret.direction_deg) < 1.0
