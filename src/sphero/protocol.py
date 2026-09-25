"""Sphero contract. Why: chase never imports spherov2 / Bleak."""

from __future__ import annotations

from typing import Protocol


class SpheroToy(Protocol):
	"""Speed 0–255, heading 0–359° after aim. Pose comes from Ace, not the IMU."""

	backend: str

	def connect(self) -> None: ...

	def aim(self) -> None: ...

	def roll(self, speed: float, heading_deg: float, duration: float = 1.0) -> None: ...

	def stop(self) -> None: ...

	def close(self) -> None: ...
