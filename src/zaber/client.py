"""Zaber Motion Library wrapper. In-memory unless serial axes are attached."""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass

from zaber.motion import HardwareSettings, load_zml, serial_candidates
from zaber.workspace import clip_xy


@dataclass
class ApiCall:
	t_s: float
	name: str
	detail: str
	rtt_ms: float


class ZaberGantry:
	"""Connection.open_serial_port + detect_devices + lockstep X if XXY.

	Without axes this is the in-memory stub used by unit tests.
	"""

	def __init__(
		self,
		settings: HardwareSettings | None = None,
		*,
		x_axis: object | None = None,
		y_axis: object | None = None,
		use_serial: bool = False,
	) -> None:
		self.settings = settings or HardwareSettings()
		self.calls: list[str] = []
		self.connected = False
		self.homed = False
		self.last_rtt_ms = 4.0
		self._x = 0.0
		self._y = 0.0
		self._vx = 0.0
		self._vy = 0.0
		self._x_axis = x_axis
		self._y_axis = y_axis
		self._conn = None
		self._units = None
		self._last_poll_s = 0.0
		self._prev_poll_s = 0.0
		self._cmd_vx = 0.0
		self._cmd_vy = 0.0
		self._log: deque[ApiCall] = deque(maxlen=12)
		# Why: only factory hardware path scans USB; stubs must not open /dev/ttyUSB.
		self._use_serial = use_serial

	def connect(self) -> None:
		# Why: open USB CDC to X-MCC here, not in experiment.
		self._note("connect", self.settings.port or "stub")
		if self._x_axis is not None:
			self.connected = True
			self._refresh(force=True)
			return
		if self._use_serial:
			self._open_serial()
			return
		self.connected = True

	def close(self) -> None:
		# Why: release the serial port so another process can claim the gantry.
		self._note("close", "")
		if self._conn is not None:
			_stop(self._x_axis)
			_stop(self._y_axis)
			self._conn.close()
			self._conn = None
		self.connected = False

	def home(self) -> None:
		# Why: absolute moves need a homed reference on each axis.
		self._note("home", f"arena=({self.settings.home_x_mm:.1f},{self.settings.home_y_mm:.1f})")
		if self._x_axis is None:
			self.homed = True
			self._x = self._y = 0.0
			self._vx = self._vy = 0.0
			return
		self._home_hardware()

	def get_xy(self) -> tuple[float, float]:
		# Why: prey XY must come from encoder, not from the camera track.
		self._refresh()
		return self._x, self._y

	def get_velocity(self) -> tuple[float, float]:
		# Why: HUD and stale-stop use encoder speed, not commanded speed.
		self._refresh()
		return self._vx, self._vy

	def is_busy(self) -> bool:
		# Why: HUD/chase must not add two is_busy serial RTTs on every snapshot.
		return (self._vx * self._vx + self._vy * self._vy) ** 0.5 > 1.0

	def step(self, dt_s: float = 0.0, t_s: float = 0.0) -> None:
		# Why: firmware integrates motion; SimulatedGantry is the one that steps.
		del dt_s, t_s

	def move_absolute(
		self,
		x_mm: float,
		y_mm: float,
		speed_mm_s: float = 0.0,
		accel_mm_s2: float = 0.0,
		wait_until_idle: bool = False,
	) -> None:
		# Why: wait_until_idle=False lets chase preempt, like pylon-track NI moves.
		x_mm, y_mm = self._clip(x_mm, y_mm)
		self._note("move_absolute", f"p=({x_mm:.1f},{y_mm:.1f}) wait={wait_until_idle}")
		if self._x_axis is None:
			self._x, self._y = x_mm, y_mm
			if wait_until_idle:
				self._vx = self._vy = 0.0
			return
		self._move_abs_hw(x_mm, y_mm, speed_mm_s, accel_mm_s2, wait_until_idle)

	def move_velocity(self, vx_mm_s: float, vy_mm_s: float) -> None:
		# Why: live hunt is continuous velocity, not discrete flee points.
		vx_mm_s, vy_mm_s = self._cap_vel(vx_mm_s, vy_mm_s)
		if self._same_vel_cmd(vx_mm_s, vy_mm_s):
			return
		self._cmd_vx, self._cmd_vy = vx_mm_s, vy_mm_s
		self._note("move_velocity", f"v=({vx_mm_s:.0f},{vy_mm_s:.0f})")
		if self._x_axis is None:
			self._vx, self._vy = vx_mm_s, vy_mm_s
			return
		self._move_vel_hw(vx_mm_s, vy_mm_s)

	def stop(self) -> None:
		# Why: trial end and stale frames must decelerate both axes.
		self._note("stop", "")
		self._cmd_vx = self._cmd_vy = 0.0
		if self._x_axis is None:
			self._vx = self._vy = 0.0
			return
		_stop(self._x_axis)
		_stop(self._y_axis)

	def api_log(self) -> list[ApiCall]:
		return list(self._log)[:8]

	@property
	def backend(self) -> str:
		# Why: HUD must show firmware vs the in-memory stub used by unit tests.
		return "hardware" if self._x_axis is not None else "stub"

	def _note(self, name: str, detail: str) -> None:
		self.calls.append(name)
		self._log.appendleft(ApiCall(0.0, name, detail, self.last_rtt_ms))

	def _clip(self, x_mm: float, y_mm: float) -> tuple[float, float]:
		s = self.settings
		return clip_xy(x_mm, y_mm, s.x_min, s.x_max, s.y_min, s.y_max)

	def _same_vel_cmd(self, vx: float, vy: float) -> bool:
		# Why: identical 50 Hz repeats still take two serial RTTs on X-MCC.
		return abs(vx - self._cmd_vx) < 0.5 and abs(vy - self._cmd_vy) < 0.5

	def _cap_vel(self, vx: float, vy: float) -> tuple[float, float]:
		s = self.settings
		cap = s.max_speed_mm_s
		spd = (vx * vx + vy * vy) ** 0.5
		if spd > cap and spd > 1e-6:
			k = cap / spd
			vx, vy = vx * k, vy * k
		if self._x_axis is None:
			return vx, vy
		x_mm, y_mm = self.get_xy()
		if x_mm <= s.x_min and vx < 0:
			vx = 0.0
		if x_mm >= s.x_max and vx > 0:
			vx = 0.0
		if y_mm <= s.y_min and vy < 0:
			vy = 0.0
		if y_mm >= s.y_max and vy > 0:
			vy = 0.0
		return vx, vy

	def _open_serial(self) -> None:
		Connection, Units = load_zml()
		self._units = Units
		ports = serial_candidates(self.settings.port)
		if not ports:
			raise RuntimeError("no serial port for Zaber (set ZABER_PORT)")
		last_err: Exception | None = None
		for port in ports:
			try:
				self._connect_port(Connection, port)
				return
			except Exception as exc:
				last_err = exc
		raise RuntimeError(f"Zaber detect failed: {last_err}") from last_err

	def _connect_port(self, Connection, port: str) -> None:
		conn = Connection.open_serial_port(port)
		devices = conn.detect_devices()
		if not devices:
			conn.close()
			raise RuntimeError(f"no Zaber devices on {port}")
		idx = min(self.settings.device_index, len(devices) - 1)
		device = devices[idx]
		self._conn = conn
		self._x_axis, self._y_axis = _bind_axes(device, self.settings)
		self.settings.port = port
		self.connected = True
		self._refresh(force=True)

	def _home_hardware(self) -> None:
		if not _is_homed(self._x_axis):
			self._x_axis.home()
		if not _is_homed(self._y_axis):
			self._y_axis.home()
		self.homed = True
		self.move_absolute(
			self.settings.home_x_mm,
			self.settings.home_y_mm,
			wait_until_idle=True,
		)

	def _move_abs_hw(
		self, x_mm: float, y_mm: float, speed: float, accel: float, wait: bool
	) -> None:
		units = self._units
		kw = {"wait_until_idle": False}
		if units is not None:
			kw["velocity"] = speed if speed > 0 else self.settings.max_speed_mm_s
			kw["velocity_unit"] = units.VELOCITY_MILLIMETRES_PER_SECOND
			kw["acceleration"] = accel if accel > 0 else self.settings.max_accel_mm_s2
			kw["acceleration_unit"] = units.ACCELERATION_MILLIMETRES_PER_SECOND_SQUARED
			self._x_axis.move_absolute(x_mm, units.LENGTH_MILLIMETRES, **kw)
			self._y_axis.move_absolute(y_mm, units.LENGTH_MILLIMETRES, **kw)
		else:
			self._x_axis.move_absolute(x_mm, **kw)
			self._y_axis.move_absolute(y_mm, **kw)
		if wait:
			_wait(self._x_axis)
			_wait(self._y_axis)
			self._vx = self._vy = 0.0
		self._refresh(force=True)

	def _move_vel_hw(self, vx: float, vy: float) -> None:
		units = self._units
		if units is not None:
			acc = self.settings.max_accel_mm_s2
			self._x_axis.move_velocity(
				vx, units.VELOCITY_MILLIMETRES_PER_SECOND,
				acceleration=acc,
				acceleration_unit=units.ACCELERATION_MILLIMETRES_PER_SECOND_SQUARED,
			)
			self._y_axis.move_velocity(
				vy, units.VELOCITY_MILLIMETRES_PER_SECOND,
				acceleration=acc,
				acceleration_unit=units.ACCELERATION_MILLIMETRES_PER_SECOND_SQUARED,
			)
		else:
			self._x_axis.move_velocity(vx)
			self._y_axis.move_velocity(vy)

	def _refresh(self, force: bool = False) -> None:
		if self._x_axis is None:
			return
		now = time.monotonic()
		if not force and (now - self._last_poll_s) < self.settings.poll_min_s:
			return
		t0 = time.perf_counter()
		x_mm = _position(self._x_axis, self._units)
		y_mm = _position(self._y_axis, self._units)
		self.last_rtt_ms = (time.perf_counter() - t0) * 1e3
		if self._prev_poll_s > 0:
			dt = now - self._prev_poll_s
			if dt > 1e-4:
				self._vx = (x_mm - self._x) / dt
				self._vy = (y_mm - self._y) / dt
		self._x, self._y = x_mm, y_mm
		self._last_poll_s = now
		self._prev_poll_s = now


def _bind_axes(device, settings: HardwareSettings) -> tuple[object, object]:
	if settings.lockstep_group > 0:
		x_ax = device.get_lockstep(settings.lockstep_group)
	else:
		x_ax = device.get_axis(settings.x_axis)
	y_ax = device.get_axis(settings.y_axis)
	return x_ax, y_ax


def _position(axis, units) -> float:
	if units is None:
		return float(axis.get_position())
	return float(axis.get_position(units.LENGTH_MILLIMETRES))


def _is_homed(axis) -> bool:
	fn = getattr(axis, "is_homed", None)
	return bool(fn()) if callable(fn) else False


def _busy(axis) -> bool:
	fn = getattr(axis, "is_busy", None)
	return bool(fn()) if callable(fn) else False


def _stop(axis) -> None:
	if axis is None:
		return
	try:
		axis.stop(wait_until_idle=False)
	except TypeError:
		axis.stop()


def _wait(axis) -> None:
	fn = getattr(axis, "wait_until_idle", None)
	if callable(fn):
		fn()
