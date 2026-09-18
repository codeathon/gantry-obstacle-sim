"""pypylon grab path with injected InstantCamera — no USB, no wheel."""

from __future__ import annotations

from pathlib import Path

import pytest

from basler.camera import AceCamera
from basler.factory import open_grabber
from basler.fov import save_mono8_pgm
from basler.pylon import want_ace
from basler.pylon_camera import PylonAceCamera
from basler.settings import CameraSettings
from experiment.grab_frames import main as grab_main


class FakeNode:
	def __init__(self, value: object = 0) -> None:
		self._v = value

	def IsWritable(self) -> bool:
		return True

	def SetValue(self, value: object) -> None:
		self._v = value

	def GetValue(self) -> object:
		return self._v


class FakeArray:
	def __init__(self, data: bytes) -> None:
		self._data = data

	def tobytes(self) -> bytes:
		return self._data


class FakeGrab:
	def __init__(self, width: int, height: int, pixels: bytes, ok: bool = True) -> None:
		self.GrabSucceeded = ok
		self.Width = width
		self.Height = height
		self.TimeStamp = 42
		self.Array = FakeArray(pixels)
		self.released = False

	def Release(self) -> None:
		self.released = True


class FakeInstantCamera:
	def __init__(self) -> None:
		self.opened = False
		self.grabbing = False
		self.strategy = None
		self.grab: FakeGrab | None = None
		self.PixelFormat = FakeNode("")
		self.Width = FakeNode(0)
		self.Height = FakeNode(0)
		self.OffsetX = FakeNode(0)
		self.OffsetY = FakeNode(0)
		self.BslExposureTimeMode = FakeNode("")
		self.ExposureAuto = FakeNode("")
		self.ExposureTime = FakeNode(0.0)
		self.GainAuto = FakeNode("")
		self.Gain = FakeNode(0.0)
		self.AcquisitionFrameRateEnable = FakeNode(False)
		self.AcquisitionFrameRate = FakeNode(0.0)
		self.TriggerMode = FakeNode("")
		self.DeviceLinkThroughputLimitMode = FakeNode("")
		self.model = "a2A1920-160umPRO"

	def Open(self) -> None:
		self.opened = True

	def Close(self) -> None:
		self.opened = False

	def StartGrabbing(self, strategy: object) -> None:
		self.grabbing = True
		self.strategy = strategy

	def StopGrabbing(self) -> None:
		self.grabbing = False

	def RetrieveResult(self, timeout_ms: int, handling: object = None):
		del timeout_ms, handling
		return self.grab


class FakePylon:
	GrabStrategy_LatestImageOnly = "LatestImageOnly"
	TimeoutHandling_Return = "Return"


def _tiny_settings() -> CameraSettings:
	return CameraSettings(width=8, height=4, offset_x=0, offset_y=0, exposure_time_us=3000.0)


def test_stub_fov_is_json_aoi() -> None:
	cam = AceCamera()
	cam.open()
	cam.configure()
	fov = cam.fov()
	cam.close()
	assert cam.backend == "stub"
	assert fov.width_px == 1920
	assert fov.height_px == 1200
	assert abs(fov.width_mm - 1920 * 1.035) < 1e-6
	assert abs(fov.height_mm - 1200 * 1.035) < 1e-6


def test_injected_pylon_configure_and_frame() -> None:
	inst = FakeInstantCamera()
	pixels = bytes(range(32))
	inst.grab = FakeGrab(8, 4, pixels)
	cam = PylonAceCamera(_tiny_settings(), camera=inst, pylon_mod=FakePylon())
	cam.open()
	cam.configure()
	cam.start_grabbing()
	frame = cam.retrieve_frame()
	cam.close()
	assert cam.backend == "pylon"
	assert inst.PixelFormat.GetValue() == "Mono8"
	assert inst.Width.GetValue() == 8
	assert inst.Height.GetValue() == 4
	assert inst.strategy == "LatestImageOnly"
	assert frame is not None
	assert frame.grab_ok
	assert frame.pixels == pixels
	assert frame.width_px == 8
	assert cam.fov().width_mm == pytest.approx(8 * 1.035)
	assert inst.grab.released


def test_failed_grab_returns_none() -> None:
	inst = FakeInstantCamera()
	inst.grab = FakeGrab(8, 4, b"", ok=False)
	cam = PylonAceCamera(_tiny_settings(), camera=inst, pylon_mod=FakePylon())
	cam.open()
	cam.configure()
	cam.start_grabbing()
	assert cam.retrieve_frame() is None
	cam.close()


def test_open_grabber_falls_back_without_sdk(monkeypatch) -> None:
	monkeypatch.setenv("PREY_ACE", "1")
	g = open_grabber()
	assert isinstance(g, AceCamera)
	assert "pypylon" not in __import__("sys").modules
	g.close()


def test_open_grabber_require_raises(monkeypatch) -> None:
	monkeypatch.setenv("PREY_ACE", "1")
	monkeypatch.setenv("PREY_ACE_REQUIRE", "1")
	with pytest.raises(RuntimeError):
		open_grabber()


def test_want_ace_env(monkeypatch) -> None:
	monkeypatch.delenv("PREY_ACE", raising=False)
	monkeypatch.delenv("PYLON_SERIAL", raising=False)
	monkeypatch.delenv("PYLON_CAMERA", raising=False)
	assert not want_ace()
	monkeypatch.setenv("PREY_ACE", "1")
	assert want_ace()


def test_grab_frames_runs_live_hunt() -> None:
	# Why: grab_frames is the pylon-track loop, not a PGM dump.
	exp = grab_main(["--duration", "0.05"])
	assert exp.last_scene is not None
	assert exp.last_scene.prey.valid


def test_save_pgm_black_when_no_pixels(tmp_path: Path) -> None:
	from basler.types import CameraFrame

	path = tmp_path / "blank.pgm"
	save_mono8_pgm(path, CameraFrame(width_px=2, height_px=2, pixels=None))
	body = path.read_bytes()
	assert body.endswith(b"\x00\x00\x00\x00")
