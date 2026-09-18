"""Load pylon-track camera_config.json without pypylon."""

import json

import pytest

from basler.camera import AceCamera
from basler.config import configure_camera
from basler.load import camera_settings_from_dict, load_camera_config
from basler.optics import ACE_MODEL, GSD_MM_PX, WARMUP_FRAMES
from basler.pylon_api import StubPylonCamera
from basler.settings import CameraSettings
from simulation.config import load_sim_config


def test_load_camera_config_is_full_frame_ace() -> None:
	# Why: pylon-track camera_config.json is 1920×1200 @ 3000 µs, not the .h crop.
	s = load_camera_config()
	assert s.pixel_format == "Mono8"
	assert s.width == 1920
	assert s.height == 1200
	assert s.offset_x == 0
	assert s.offset_y == 0
	assert s.exposure_time_us == 3000.0
	assert s.frame_rate_fps == 200.0
	assert s.gain_db == 6.0
	assert s.trigger_mode == "Off"


def test_ace_camera_defaults_to_json() -> None:
	cam = AceCamera()
	cam.open()
	cam.configure()
	cam.start_grabbing()
	frame = cam.retrieve_frame()
	cam.close()
	assert frame is not None
	assert frame.width_px == 1920
	assert frame.height_px == 1200


def test_hunt_sim_uses_ace_aoi() -> None:
	cfg = load_sim_config()
	assert cfg.camera.width_px == 1920
	assert cfg.camera.height_px == 1200
	assert cfg.camera.exposure_us == 3000.0
	assert cfg.camera.frame_rate_fps == 200.0
	assert cfg.camera.model == ACE_MODEL
	assert cfg.camera.gsd_mm_per_px == GSD_MM_PX


def test_fpga_alias_is_region1() -> None:
	cam = StubPylonCamera()
	configure_camera(
		cam, CameraSettings(binning_horizontal=2, binning_vertical=2, binning_selector="FPGA")
	)
	assert cam.nodes["BinningSelector"] == "Region1"


def test_common_exposure_alias_is_standard() -> None:
	cam = StubPylonCamera()
	configure_camera(cam, CameraSettings(exposure_time_mode="Common"))
	assert cam.nodes["BslExposureTimeMode"] == "Standard"


def test_env_overrides_camera_config(monkeypatch, tmp_path) -> None:
	# Why: PYLON_CAMERA_CONFIG is the same env pylon-track resolve_camera_config_path uses.
	path = tmp_path / "camera_config.json"
	base = load_camera_config()
	raw = {
		"pixel_format": base.pixel_format,
		"width": 640,
		"height": 480,
		"offset_x": 0,
		"offset_y": 0,
		"exposure_auto": False,
		"exposure_time_us": 1000.0,
		"gain_auto": False,
		"gain_db": 6.0,
		"frame_rate_enable": True,
		"frame_rate_fps": 50.0,
		"trigger_mode": "Off",
		"device_link_throughput_limit": "Off",
	}
	path.write_text(json.dumps(raw), encoding="utf-8")
	monkeypatch.setenv("PYLON_CAMERA_CONFIG", str(path))
	s = load_camera_config()
	assert s.width == 640
	assert s.height == 480
	assert s.exposure_time_us == 1000.0


def test_missing_required_field() -> None:
	with pytest.raises(ValueError, match="missing"):
		camera_settings_from_dict({"pixel_format": "Mono8"})


def test_warmup_frames_match_pylon_track() -> None:
	assert WARMUP_FRAMES == 6000
