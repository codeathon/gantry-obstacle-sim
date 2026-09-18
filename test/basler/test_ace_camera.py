"""AceCamera dry grab cycle using stub InstantCamera."""

from basler.camera import AceCamera
from basler.settings import CameraSettings


def test_ace_camera_grab_cycle() -> None:
	cam = AceCamera(CameraSettings(width=1920, height=960))
	cam.open()
	cam.configure()
	cam.start_grabbing()
	frame = cam.retrieve_frame()
	cam.close()
	assert frame is not None
	assert frame.width_px == 1920
	assert frame.height_px == 960
	assert frame.pixels is None
	assert frame.frame_index == 1
	assert cam._cam is None


def test_retrieve_before_grabbing_is_none() -> None:
	cam = AceCamera()
	cam.open()
	assert cam.retrieve_frame() is None
	cam.close()


def test_register_handler_notes_pylon_callback() -> None:
	cam = AceCamera()
	cam.open()
	handler = object()
	cam.register_handler(handler)
	assert cam._cam is not None
	assert cam._cam.handler is handler
	assert "RegisterImageEventHandler" in cam._cam.calls
	cam.close()
