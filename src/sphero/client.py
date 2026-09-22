"""In-memory Sphero. Why: tests and PREY_ANIMAL=sphero without BLE."""

from __future__ import annotations

import threading


class SpheroStub:
	backend = "stub"

	def __init__(self) -> None:
		self.connected = False
		self.speed = 0.0
		self.heading_deg = 0.0
		self.calls: list[str] = []
		self.roll_thread: str = ""

	def connect(self) -> None:
		self.calls.append("connect")
		self.connected = True

	def aim(self) -> None:
		self.calls.append("aim")
		self.heading_deg = 0.0

	def roll(self, speed: float, heading_deg: float) -> None:
		# Why: Mini roll expires; the runner re-issues this on its own thread.
		self.speed = float(speed)
		self.heading_deg = float(heading_deg) % 360.0
		self.roll_thread = threading.current_thread().name
		self.calls.append("roll")

	def stop(self) -> None:
		self.calls.append("stop")
		self.speed = 0.0

	def close(self) -> None:
		self.calls.append("close")
		self.connected = False
