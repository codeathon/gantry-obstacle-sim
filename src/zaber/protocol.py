"""Gantry contract. Why: sim and hardware share this so chase never sees serial."""

from __future__ import annotations

from typing import Protocol


class Gantry(Protocol):
	"""Domain units are millimetres and mm/s, not native microsteps."""

	def connect(self) -> None: ...

	def close(self) -> None: ...

	def home(self) -> None: ...

	def get_xy(self) -> tuple[float, float]: ...

	def get_velocity(self) -> tuple[float, float]: ...

	def move_absolute(
		self,
		x_mm: float,
		y_mm: float,
		speed_mm_s: float = 0.0,
		accel_mm_s2: float = 0.0,
		wait_until_idle: bool = False,
	) -> None: ...

	def move_velocity(self, vx_mm_s: float, vy_mm_s: float) -> None: ...

	def stop(self) -> None: ...
