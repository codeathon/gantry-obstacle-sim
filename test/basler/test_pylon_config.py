"""Pylon-track GenICam node stubs: record SetValue names, no USB."""

import pytest

from basler.config import configure_camera
from basler.pylon_api import StubPylonCamera, instant_camera_open
from basler.settings import CameraSettings


def test_configure_records_pylon_track_nodes() -> None:
	# Why: camera_config.cpp required nodes must appear even without pypylon.
	cam = StubPylonCamera()
	instant_camera_open(cam)
	configure_camera(cam, CameraSettings())
	assert cam.nodes["PixelFormat"] == "Mono8"
	assert cam.nodes["Width"] == 1920
	assert cam.nodes["Height"] == 960
	assert cam.nodes["OffsetX"] == 0
	assert cam.nodes["OffsetY"] == 120
	assert cam.nodes["BslExposureTimeMode"] == "Standard"
	assert cam.nodes["ExposureAuto"] == "Off"
	assert cam.nodes["ExposureTime"] == 5000.0
	assert cam.nodes["Gain"] == 6.0
	assert cam.nodes["AcquisitionFrameRate"] == 200.0
	assert cam.nodes["TriggerMode"] == "Off"
	assert cam.opened


def test_configure_rejects_non_mono8() -> None:
	with pytest.raises(ValueError, match="Mono8"):
		configure_camera(StubPylonCamera(), CameraSettings(pixel_format="BayerRG8"))


def test_configure_rejects_triggered_mode() -> None:
	with pytest.raises(ValueError, match="TriggerMode"):
		configure_camera(StubPylonCamera(), CameraSettings(trigger_mode="On"))


def test_optional_geometry_nodes() -> None:
	cam = StubPylonCamera()
	configure_camera(
		cam,
		CameraSettings(
			binning_horizontal=2,
			binning_vertical=2,
			reverse_x=True,
			black_level=4,
			gamma=1.2,
			device_link_throughput_limit="On",
			device_link_throughput_mbps=800.0,
		),
	)
	assert cam.nodes["BinningSelector"] == "Sensor"
	assert cam.nodes["BinningHorizontal"] == 2
	assert cam.nodes["ReverseX"] is True
	assert cam.nodes["BlackLevel"] == 4
	assert cam.nodes["Gamma"] == 1.2
	assert cam.nodes["DeviceLinkThroughputLimit"] == int(800.0 * 1e6 / 8.0)


def test_scaling_when_not_binning() -> None:
	cam = StubPylonCamera()
	configure_camera(cam, CameraSettings(scaling_horizontal=0.5))
	assert cam.nodes["ScalingHorizontal"] == 0.5
	assert "BinningHorizontal" not in cam.nodes
