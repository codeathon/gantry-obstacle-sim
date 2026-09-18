"""Ace grab contract. Why: SimulatedPylonCamera can implement this without pypylon."""

from __future__ import annotations

from typing import Protocol

from basler.types import CameraFrame


class AceGrabber(Protocol):
	"""Grab cadence only. Tracking belongs in src/vision."""

	def open(self) -> None: ...

	def configure(self) -> None: ...

	def start_grabbing(self) -> None: ...

	def stop_grabbing(self) -> None: ...

	def retrieve_frame(self) -> CameraFrame | None: ...

	def close(self) -> None: ...
