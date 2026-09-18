"""CameraSettings matching pylon-track camera_settings.h. No pypylon."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class CameraSettings:
	# Why: dataclass defaults match camera_settings.h; AceCamera loads camera_config.json.
	pixel_format: str = "Mono8"
	width: int = 1920
	height: int = 960
	offset_x: int = 0
	offset_y: int = 120
	exposure_auto: bool = False
	exposure_time_us: float = 5000.0
	exposure_time_mode: str = "Standard"
	gain_auto: bool = False
	gain_db: float = 6.0
	frame_rate_enable: bool = True
	frame_rate_fps: float = 200.0
	trigger_mode: str = "Off"
	device_link_throughput_limit: str = "Off"
	device_link_throughput_mbps: float = 0.0
	black_level: int = 0
	gamma: float = 1.0
	binning_horizontal: int = 1
	binning_vertical: int = 1
	binning_selector: str = "Sensor"
	scaling_horizontal: float = 1.0
	reverse_x: bool = False
	reverse_y: bool = False
