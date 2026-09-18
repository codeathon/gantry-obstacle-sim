"""Apply CameraSettings to a pypylon InstantCamera. Order matches camera_config.cpp."""

from __future__ import annotations

from basler.load import _binning_selector, _exposure_mode
from basler.settings import CameraSettings


def configure_instant_camera(cam: object, s: CameraSettings) -> None:
	# Why: same GenICam nodes as the stub path, but SetValue on live firmware.
	if s.pixel_format != "Mono8":
		raise ValueError("only Mono8")
	_set(cam, "PixelFormat", "Mono8", required=True)
	_apply_geometry(cam, s)
	_apply_exposure_gain(cam, s)
	_set(cam, "AcquisitionFrameRateEnable", s.frame_rate_enable, required=True)
	if s.frame_rate_enable:
		_set(cam, "AcquisitionFrameRate", s.frame_rate_fps, required=True)
	if s.trigger_mode != "Off":
		raise ValueError("only TriggerMode Off")
	_set(cam, "TriggerMode", "Off", required=True)
	_apply_throughput(cam, s)


def _apply_geometry(cam: object, s: CameraSettings) -> None:
	if s.binning_horizontal > 1 or s.binning_vertical > 1:
		_set(cam, "BinningSelector", _binning_selector(s.binning_selector))
		_set(cam, "BinningHorizontal", s.binning_horizontal, required=True)
		_set(cam, "BinningVertical", s.binning_vertical, required=True)
	elif 0.0 < s.scaling_horizontal < 1.0 - 1e-6:
		_set(cam, "ScalingHorizontal", s.scaling_horizontal, required=True)
	_set(cam, "Width", s.width, required=True)
	_set(cam, "Height", s.height, required=True)
	_set(cam, "OffsetX", s.offset_x, required=True)
	_set(cam, "OffsetY", s.offset_y, required=True)
	if s.reverse_x:
		_set(cam, "ReverseX", True)
	if s.reverse_y:
		_set(cam, "ReverseY", True)
	if s.black_level != 0:
		_set(cam, "BlackLevel", s.black_level)
	if abs(s.gamma - 1.0) > 1e-6:
		_set(cam, "Gamma", s.gamma)


def _apply_exposure_gain(cam: object, s: CameraSettings) -> None:
	_set(cam, "BslExposureTimeMode", _exposure_mode(s.exposure_time_mode), required=True)
	_set(cam, "ExposureAuto", "Continuous" if s.exposure_auto else "Off", required=True)
	if not s.exposure_auto:
		_set(cam, "ExposureTime", s.exposure_time_us, required=True)
	_set(cam, "GainAuto", "Continuous" if s.gain_auto else "Off", required=True)
	if not s.gain_auto:
		_set(cam, "Gain", s.gain_db, required=True)


def _apply_throughput(cam: object, s: CameraSettings) -> None:
	_set(cam, "DeviceLinkThroughputLimitMode", s.device_link_throughput_limit, required=True)
	if s.device_link_throughput_limit == "On":
		_set(
			cam,
			"DeviceLinkThroughputLimit",
			int(s.device_link_throughput_mbps * 1e6 / 8.0),
			required=True,
		)


def _set(cam: object, name: str, value: object, required: bool = False) -> None:
	# Why: optional GenICam nodes vary by ace 2 firmware; never hard-fail those.
	try:
		node = getattr(cam, name)
		writable = getattr(node, "IsWritable", None)
		if callable(writable) and not writable():
			if required:
				raise RuntimeError(f"{name} is not writable")
			return
		setter = getattr(node, "SetValue", None)
		if callable(setter):
			setter(value)
			return
		setattr(cam, name, value)
	except Exception:
		if required:
			raise
