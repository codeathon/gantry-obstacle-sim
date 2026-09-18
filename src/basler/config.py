"""Apply CameraSettings via stub Pylon nodes. Order matches camera_config.cpp."""

from __future__ import annotations

from basler.load import _binning_selector, _exposure_mode
from basler.pylon_api import (
	StubPylonCamera,
	set_aoi,
	set_binning,
	set_black_level_gamma,
	set_exposure,
	set_frame_rate,
	set_gain,
	set_pixel_format_mono8,
	set_reverse,
	set_scaling,
	set_throughput_limit,
	set_trigger_off,
)
from basler.settings import CameraSettings


def configure_camera(cam: StubPylonCamera, settings: CameraSettings) -> None:
	# Why: one place lists every GenICam node pylon-track would SetValue.
	if settings.pixel_format != "Mono8":
		raise ValueError("only Mono8")
	set_pixel_format_mono8(cam)
	_apply_geometry(cam, settings)
	_apply_exposure_gain(cam, settings)
	set_frame_rate(cam, settings.frame_rate_enable, settings.frame_rate_fps)
	if settings.trigger_mode != "Off":
		raise ValueError("only TriggerMode Off")
	set_trigger_off(cam)
	set_throughput_limit(
		cam, settings.device_link_throughput_limit, settings.device_link_throughput_mbps
	)


def _apply_geometry(cam: StubPylonCamera, s: CameraSettings) -> None:
	if s.binning_horizontal > 1 or s.binning_vertical > 1:
		set_binning(
			cam, s.binning_horizontal, s.binning_vertical, _binning_selector(s.binning_selector)
		)
	elif 0.0 < s.scaling_horizontal < 1.0 - 1e-6:
		# Why: pylon-track skips ScalingHorizontal unless it is a real downsample.
		set_scaling(cam, s.scaling_horizontal)
	set_aoi(cam, s.width, s.height, s.offset_x, s.offset_y)
	set_reverse(cam, s.reverse_x, s.reverse_y)
	set_black_level_gamma(cam, s.black_level, s.gamma)


def _apply_exposure_gain(cam: StubPylonCamera, s: CameraSettings) -> None:
	set_exposure(cam, s.exposure_auto, s.exposure_time_us, _exposure_mode(s.exposure_time_mode))
	set_gain(cam, s.gain_auto, s.gain_db)
