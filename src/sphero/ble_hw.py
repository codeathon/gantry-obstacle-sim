"""spherov2 + Bleak Mini. Why: lazy import so ferret hunts do not need the wheel."""

from __future__ import annotations

import os


class BleSphero:
	backend = "ble"

	def __init__(self, api: object) -> None:
		self._api = api

	def connect(self) -> None:
		return

	def aim(self) -> None:
		# Why: Mini heading is aim-relative, not Charuco arena 0°.
		reset = getattr(self._api, "reset_aim", None)
		if callable(reset):
			reset()
			return
		set_h = getattr(self._api, "set_heading", None)
		if callable(set_h):
			set_h(0)

	def roll(self, speed: float, heading_deg: float) -> None:
		# Why: Edu API is roll(heading, speed); we store speed-first in the protocol.
		self._api.roll(int(heading_deg) % 360, int(max(0.0, min(255.0, speed))))

	def stop(self) -> None:
		fn = getattr(self._api, "stop_roll", None) or getattr(self._api, "stop", None)
		if callable(fn):
			fn()

	def close(self) -> None:
		exit_fn = getattr(self._api, "__exit__", None)
		if callable(exit_fn):
			exit_fn(None, None, None)


def connect_ble() -> BleSphero:
	from spherov2 import scanner
	from spherov2.sphero_edu import SpheroEduAPI

	name = os.environ.get("SPHERO_NAME", "").strip() or None
	toy = scanner.find_toy(toy_name=name) if name else scanner.find_toy()
	api = SpheroEduAPI(toy)
	api.__enter__()
	return BleSphero(api)
