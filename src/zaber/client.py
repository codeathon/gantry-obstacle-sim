"""Real Zaber Motion Library wrapper. Stub: no zaber_motion import yet."""

from __future__ import annotations


class ZaberGantry:
	"""Later: Connection.open_serial_port + detect_devices + lockstep X if XXY.

	In-memory only: records the API names chase would call and holds last XY.
	"""

	def __init__(self) -> None:
		self.calls: list[str] = []
		self.connected = False
		self.homed = False
		self._x = 0.0
		self._y = 0.0
		self._vx = 0.0
		self._vy = 0.0

	def connect(self) -> None:
		# Why: open USB CDC to X-MCC here, not in experiment.
		self.calls.append("connect")
		self.connected = True

	def close(self) -> None:
		# Why: release the serial port so another process can claim the gantry.
		self.calls.append("close")
		self.connected = False

	def home(self) -> None:
		# Why: absolute moves need a homed reference on each axis.
		self.calls.append("home")
		self.homed = True
		self._x = self._y = 0.0
		self._vx = self._vy = 0.0

	def get_xy(self) -> tuple[float, float]:
		# Why: prey XY must come from encoder, not from the camera track.
		return self._x, self._y

	def get_velocity(self) -> tuple[float, float]:
		# Why: HUD and stale-stop use encoder speed, not commanded speed.
		return self._vx, self._vy

	def move_absolute(
		self,
		x_mm: float,
		y_mm: float,
		speed_mm_s: float = 0.0,
		accel_mm_s2: float = 0.0,
		wait_until_idle: bool = False,
	) -> None:
		# Why: wait_until_idle=False lets chase preempt, like pylon-track NI moves.
		del speed_mm_s, accel_mm_s2
		self.calls.append("move_absolute")
		self._x, self._y = x_mm, y_mm
		if wait_until_idle:
			self._vx = self._vy = 0.0

	def move_velocity(self, vx_mm_s: float, vy_mm_s: float) -> None:
		# Why: live hunt is continuous velocity, not discrete flee points.
		self.calls.append("move_velocity")
		self._vx, self._vy = vx_mm_s, vy_mm_s

	def stop(self) -> None:
		# Why: trial end and stale frames must decelerate both axes.
		self.calls.append("stop")
		self._vx = self._vy = 0.0
