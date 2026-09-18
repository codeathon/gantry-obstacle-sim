"""TrackingPipeline stub: timestamps only, no MOG2."""

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
