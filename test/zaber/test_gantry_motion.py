"""Hardware-path ZaberGantry tests: FakeAxis injection, no USB, no SDK."""

from __future__ import annotations

import sys

import pytest

from zaber.client import ZaberGantry, _bind_axes
from zaber.factory import open_gantry
from zaber.motion import (
	HardwareSettings,
	serial_candidates,
	settings_from_sim,
	want_hardware,
)


class FakeAxis:
	def __init__(self, pos: float = 0.0) -> None:
		self.pos = pos
		self.vel = 0.0
		self.homed = False
		self.busy = False
		self.calls: list[str] = []
		self.last_kw: dict = {}

	def get_position(self, unit=None):
		self.calls.append("get_position")
		return self.pos

	def home(self) -> None:
		self.calls.append("home")
		self.pos = 0.0
		self.vel = 0.0
		self.homed = True

	def is_homed(self) -> bool:
		return self.homed

	def is_busy(self) -> bool:
		return self.busy

	def move_absolute(self, position, unit=None, **kwargs) -> None:
		self.calls.append("move_absolute")
		self.pos = float(position)
		self.last_kw = kwargs
		if kwargs.get("wait_until_idle", True):
			self.vel = 0.0

	def move_velocity(self, velocity, unit=None, **kwargs) -> None:
		self.calls.append("move_velocity")
		self.vel = float(velocity)
		self.last_kw = kwargs

	def stop(self, wait_until_idle: bool = True) -> None:
		del wait_until_idle
		self.calls.append("stop")
		self.vel = 0.0

	def wait_until_idle(self) -> None:
		self.calls.append("wait_until_idle")
		self.busy = False


class FakeConn:
	def __init__(self) -> None:
		self.closed = False

	def close(self) -> None:
		self.closed = True


class FakeDevice:
	def __init__(self) -> None:
		self.lockstep = FakeAxis()
		self.axes = {1: FakeAxis(), 2: FakeAxis()}

	def get_lockstep(self, group: int):
		del group
		return self.lockstep

	def get_axis(self, index: int):
		return self.axes[index]


class _FakeUnits:
	LENGTH_MILLIMETRES = "mm"
	VELOCITY_MILLIMETRES_PER_SECOND = "mm/s"
	ACCELERATION_MILLIMETRES_PER_SECOND_SQUARED = "mm/s2"


def _gantry(x: FakeAxis, y: FakeAxis, **kw) -> ZaberGantry:
	g = ZaberGantry(HardwareSettings(**kw), x_axis=x, y_axis=y)
	g.connect()
	return g


def test_stub_backend_and_api_log() -> None:
	g = ZaberGantry()
	g.connect()
	assert g.backend == "stub"
	assert g.api_log()[0].name == "connect"
	g.close()


def test_stub_connect_does_not_scan_usb(monkeypatch) -> None:
	# Why: unit tests must not glob /dev/ttyUSB* on a CI box.
	def boom(port: str = "") -> list[str]:
		raise AssertionError(f"stub must not scan USB ({port})")

	monkeypatch.setattr("zaber.client.serial_candidates", boom)
	g = ZaberGantry()
	g.connect()
	assert g.connected


def test_injected_axes_home_then_encoder() -> None:
	x, y = FakeAxis(), FakeAxis()
	g = _gantry(x, y, home_x_mm=10.0, home_y_mm=20.0, poll_min_s=0.0)
	assert g.backend == "hardware"
	g.home()
	assert g.get_xy() == (10.0, 20.0)
	assert "home" in x.calls
	assert "move_absolute" in x.calls


def test_injected_move_velocity_and_stop() -> None:
	x, y = FakeAxis(50.0), FakeAxis(50.0)
	g = _gantry(x, y, x_min=0, x_max=200, y_min=0, y_max=200, max_speed_mm_s=1000)
	g.move_velocity(12.0, -3.0)
	assert x.vel == 12.0
	assert y.vel == -3.0
	g.stop()
	assert x.vel == y.vel == 0.0


def test_hardware_wall_clips_outward_velocity() -> None:
	x, y = FakeAxis(0.0), FakeAxis(0.0)
	g = _gantry(x, y, x_min=0, y_min=0, x_max=100, y_max=100, max_speed_mm_s=1000)
	g.move_velocity(-40.0, 8.0)
	assert x.vel == 0.0
	assert y.vel == 8.0


def test_hardware_caps_speed() -> None:
	x, y = FakeAxis(50.0), FakeAxis(50.0)
	g = _gantry(x, y, max_speed_mm_s=100.0, x_min=0, x_max=200, y_min=0, y_max=200)
	g.move_velocity(300.0, 0.0)
	assert x.vel == pytest.approx(100.0)
	assert y.vel == pytest.approx(0.0)


def test_hardware_clips_absolute() -> None:
	x, y = FakeAxis(), FakeAxis()
	g = _gantry(x, y, x_min=0, x_max=100, y_min=0, y_max=80)
	g.move_absolute(-10.0, 500.0)
	assert x.pos == 0.0
	assert y.pos == 80.0


def test_encoder_poll_is_cached() -> None:
	x, y = FakeAxis(1.0), FakeAxis(2.0)
	g = _gantry(x, y, poll_min_s=10.0)
	n = x.calls.count("get_position")
	g.get_xy()
	g.get_velocity()
	assert x.calls.count("get_position") == n


def test_close_stops_only_when_serial_conn() -> None:
	x, y = FakeAxis(), FakeAxis()
	g = _gantry(x, y)
	g.close()
	assert "stop" not in x.calls
	conn = FakeConn()
	g._x_axis, g._y_axis, g._conn = x, y, conn
	g.close()
	assert "stop" in x.calls
	assert conn.closed
	assert g._conn is None


def test_lockstep_binds_x() -> None:
	dev = FakeDevice()
	x_ax, y_ax = _bind_axes(dev, HardwareSettings(lockstep_group=1, y_axis=2))
	assert x_ax is dev.lockstep
	assert y_ax is dev.axes[2]


def test_is_busy_uses_encoder_speed() -> None:
	# Why: axis is_busy is a serial RTT; HUD uses cached encoder delta instead.
	x, y = FakeAxis(50.0), FakeAxis(50.0)
	g = _gantry(x, y, x_min=0, x_max=200, y_min=0, y_max=200, max_speed_mm_s=1000)
	assert not g.is_busy()
	g._vx, g._vy = 12.0, 0.0
	assert g.is_busy()


def test_duplicate_move_velocity_skips_serial() -> None:
	x, y = FakeAxis(50.0), FakeAxis(50.0)
	g = _gantry(x, y, x_min=0, x_max=200, y_min=0, y_max=200, max_speed_mm_s=1000)
	g.move_velocity(12.0, -3.0)
	n = x.calls.count("move_velocity")
	g.move_velocity(12.0, -3.0)
	assert x.calls.count("move_velocity") == n
	g.move_velocity(20.0, -3.0)
	assert x.calls.count("move_velocity") == n + 1


def test_units_kwargs_on_injected_axis() -> None:
	x, y = FakeAxis(50.0), FakeAxis(50.0)
	g = _gantry(x, y, max_speed_mm_s=50, max_accel_mm_s2=100, x_min=0, x_max=200, y_min=0, y_max=200)
	g._units = _FakeUnits()
	g.move_absolute(3.0, 4.0, speed_mm_s=20, accel_mm_s2=30)
	assert x.pos == 3.0
	assert x.last_kw["velocity"] == 20
	g.move_velocity(1.0, 2.0)
	assert x.vel == 1.0
	assert y.vel == 2.0


def test_want_hardware_env(monkeypatch) -> None:
	monkeypatch.delenv("PREY_ZABER", raising=False)
	monkeypatch.delenv("ZABER_PORT", raising=False)
	monkeypatch.delenv("PREY_ZABER_PORT", raising=False)
	assert not want_hardware(None)
	monkeypatch.setenv("PREY_ZABER", "1")
	assert want_hardware(None)


def test_serial_candidates_override(monkeypatch) -> None:
	monkeypatch.setenv("ZABER_PORT", "/dev/ttyUSB99")
	assert serial_candidates() == ["/dev/ttyUSB99"]
	assert serial_candidates("/dev/ttyACM0") == ["/dev/ttyACM0"]


def test_settings_from_sim() -> None:
	from simulation.config import load_sim_config

	cfg = load_sim_config()
	s = settings_from_sim(cfg)
	assert s.home_x_mm == cfg.zaber.home_x_mm
	assert s.x_max == cfg.camera.width_mm
	assert s.poll_min_s == pytest.approx(cfg.zaber.poll_min_ms * 1e-3)


def test_open_gantry_falls_back_without_sdk(monkeypatch) -> None:
	monkeypatch.setenv("PREY_ZABER", "1")
	from simulation.config import load_sim_config

	g = open_gantry(load_sim_config())
	assert g.backend == "sim"
	assert "zaber_motion" not in sys.modules
	g.close()


def test_open_gantry_require_raises(monkeypatch) -> None:
	monkeypatch.setenv("PREY_ZABER", "1")
	monkeypatch.setenv("PREY_ZABER_REQUIRE", "1")
	from simulation.config import load_sim_config

	with pytest.raises(RuntimeError):
		open_gantry(load_sim_config())


def test_open_serial_binds_lockstep(monkeypatch) -> None:
	dev = FakeDevice()

	class Conn:
		@classmethod
		def open_serial_port(cls, port: str):
			c = cls()
			c.port = port
			return c

		def detect_devices(self):
			return [dev]

		def close(self) -> None:
			return None

	monkeypatch.setattr("zaber.client.load_zml", lambda: (Conn, _FakeUnits))
	monkeypatch.setattr("zaber.client.serial_candidates", lambda port="": ["/dev/ttyUSB0"])
	s = HardwareSettings(lockstep_group=1, y_axis=2, home_x_mm=5, home_y_mm=6, poll_min_s=0)
	g = ZaberGantry(s, use_serial=True)
	g.connect()
	assert g.backend == "hardware"
	assert g._x_axis is dev.lockstep
	assert g.settings.port == "/dev/ttyUSB0"
	g.home()
	assert g.get_xy() == (5.0, 6.0)
	g.close()


def test_open_serial_no_devices_closes(monkeypatch) -> None:
	closed: list[bool] = []

	class Conn:
		@classmethod
		def open_serial_port(cls, port: str):
			del port
			return cls()

		def detect_devices(self):
			return []

		def close(self) -> None:
			closed.append(True)

	monkeypatch.setattr("zaber.client.load_zml", lambda: (Conn, object()))
	monkeypatch.setattr("zaber.client.serial_candidates", lambda port="": ["/dev/ttyUSB0"])
	g = ZaberGantry(use_serial=True)
	with pytest.raises(RuntimeError, match="detect failed"):
		g.connect()
	assert closed
