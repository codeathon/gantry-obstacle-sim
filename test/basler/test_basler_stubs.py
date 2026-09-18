"""Import-only: basler stubs must load without pypylon."""

from basler.camera import AceCamera, configure_ace, make_camera_frame, open_ace
from basler.protocol import AceGrabber
from basler.types import CameraFrame


def test_ace_stubs_are_importable() -> None:
	assert AceGrabber is not None
	assert AceCamera is not None
	assert open_ace is not None
	assert configure_ace is not None
	assert make_camera_frame is not None
	assert CameraFrame().frame_index == 0
