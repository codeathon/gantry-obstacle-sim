"""Real Zaber Motion Library wrapper. Stub: no zaber_motion import yet."""

from __future__ import annotations


class ZaberGantry:
	"""Later: Connection.open_serial_port + detect_devices + lockstep X if XXY."""

	def connect(self) -> None:
		# Why: open USB CDC to X-MCC here, not in experiment.
		raise NotImplementedError("zaber_motion connect")

	def close(self) -> None:
		# Why: release the serial port so another process can claim the gantry.
		raise NotImplementedError("zaber_motion close")

	def home(self) -> None:
		# Why: absolute moves need a homed reference on each axis.
		raise NotImplementedError("axis.home")

	def get_xy(self) -> tuple[float, float]:
		# Why: prey XY must come from encoder, not from the camera track.
		raise NotImplementedError("axis.get_position Units.LENGTH_MILLIMETRES")

	def get_velocity(self) -> tuple[float, float]:
		# Why: HUD and stale-stop use encoder speed, not commanded speed.
		raise NotImplementedError("axis.get_velocity")

	def move_absolute(
		self,
		x_mm: float,
		y_mm: float,
		speed_mm_s: float = 0.0,
		accel_mm_s2: float = 0.0,
		wait_until_idle: bool = False,
	) -> None:
		# Why: wait_until_idle=False lets chase preempt, like pylon-track NI moves.
		raise NotImplementedError("axis.move_absolute Units.LENGTH_MILLIMETRES")

	def move_velocity(self, vx_mm_s: float, vy_mm_s: float) -> None:
		# Why: live hunt is continuous velocity, not discrete flee points.
		raise NotImplementedError("axis.move_velocity on X and Y together")

	def stop(self) -> None:
		# Why: trial end and stale frames must decelerate both axes.
		raise NotImplementedError("axis.stop")
