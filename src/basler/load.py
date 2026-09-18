"""Load pylon-track camera_config.json. Why: Ace AOI lives in one file, not two."""

from __future__ import annotations

import json
import os
from pathlib import Path

from basler.settings import CameraSettings

_REQUIRED = (
	"pixel_format",
	"width",
	"height",
	"offset_x",
	"offset_y",
	"exposure_auto",
	"exposure_time_us",
	"gain_auto",
	"gain_db",
	"frame_rate_enable",
	"frame_rate_fps",
	"trigger_mode",
	"device_link_throughput_limit",
)


def default_camera_config_path() -> Path:
	here = Path(__file__).resolve()
	return here.parents[2] / "config" / "camera_config.json"


def resolve_camera_config_path(path: str | Path | None = None) -> Path:
	# Why: same order as camera_config.cpp — CLI, then PYLON_CAMERA_CONFIG.
	if path:
		return Path(path)
	env = os.environ.get("PYLON_CAMERA_CONFIG") or os.environ.get("PREY_CAMERA_CONFIG")
	if env:
		return Path(env)
	return default_camera_config_path()


def load_camera_config(path: str | Path | None = None) -> CameraSettings:
	cfg_path = resolve_camera_config_path(path)
	raw = json.loads(cfg_path.read_text(encoding="utf-8"))
	return camera_settings_from_dict(raw)


def camera_settings_from_dict(raw: dict) -> CameraSettings:
	# Why: require the same keys camera_config.cpp require_field()s.
	missing = [k for k in _REQUIRED if k not in raw]
	if missing:
		raise ValueError(f"camera_config missing {missing}")
	return CameraSettings(
		pixel_format=str(raw["pixel_format"]),
		width=int(raw["width"]),
		height=int(raw["height"]),
		offset_x=int(raw["offset_x"]),
		offset_y=int(raw["offset_y"]),
		exposure_auto=bool(raw["exposure_auto"]),
		exposure_time_us=float(raw["exposure_time_us"]),
		exposure_time_mode=_exposure_mode(str(raw.get("exposure_time_mode", "Standard"))),
		gain_auto=bool(raw["gain_auto"]),
		gain_db=float(raw["gain_db"]),
		frame_rate_enable=bool(raw["frame_rate_enable"]),
		frame_rate_fps=float(raw["frame_rate_fps"]),
		trigger_mode=str(raw["trigger_mode"]),
		device_link_throughput_limit=str(raw["device_link_throughput_limit"]),
		device_link_throughput_mbps=float(raw.get("device_link_throughput_mbps", 0.0)),
		black_level=int(raw.get("black_level", 0)),
		gamma=float(raw.get("gamma", 1.0)),
		binning_horizontal=int(raw.get("binning_horizontal", 1)),
		binning_vertical=int(raw.get("binning_vertical", 1)),
		binning_selector=_binning_selector(str(raw.get("binning_selector", "Sensor"))),
		scaling_horizontal=float(raw.get("scaling_horizontal", 1.0)),
		reverse_x=bool(raw.get("reverse_x", False)),
		reverse_y=bool(raw.get("reverse_y", False)),
	)


def _exposure_mode(mode: str) -> str:
	# Why: JSON alias Common is BslExposureTimeMode_Standard on ace 2.
	if mode in ("Common", "Standard"):
		return "Standard"
	if mode == "UltraShort":
		return "UltraShort"
	raise ValueError(f"unsupported exposure_time_mode: {mode}")


def _binning_selector(name: str) -> str:
	# Why: camera_config.cpp maps FPGA to GenICam Region1.
	if name in ("FPGA", "Region1"):
		return "Region1"
	if name == "Sensor":
		return "Sensor"
	raise ValueError(f"unsupported binning_selector: {name}")
