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

	def set_led(self, r: int, g: int, b: int) -> None:
		# Why: Edu API takes Color, not r,g,b — a TypeError used to abort the roll check.
		fn = getattr(self._api, "set_main_led", None)
		if not callable(fn):
			return
		try:
			fn(_led_color(r, g, b))
		except Exception:
			return

	def roll(self, speed: float, heading_deg: float, duration: float = 1.0) -> None:
		# Why: lab spherov2 requires duration; heading, speed, seconds.
		self._api.roll(
			int(heading_deg) % 360,
			int(max(0.0, min(255.0, speed))),
			float(duration),
		)

	def stop(self) -> None:
		# Why: after a timed roll the GATT link often dies; teardown must not fail the check.
		fn = getattr(self._api, "stop_roll", None) or getattr(self._api, "stop", None)
		_ble_ignore(fn)

	def close(self) -> None:
		_ble_ignore(lambda: self._api.__exit__(None, None, None))


def _ble_ignore(fn) -> None:
	if not callable(fn):
		return
	try:
		fn()
	except Exception:
		return


def _led_color(r: int, g: int, b: int):
	try:
		from spherov2.types import Color

		return Color(r=int(r), g=int(g), b=int(b))
	except ImportError:
		return type("Color", (), {"r": int(r), "g": int(g), "b": int(b)})()


def connect_ble() -> BleSphero:
	from spherov2 import scanner
	from spherov2.sphero_edu import SpheroEduAPI

	name = os.environ.get("SPHERO_NAME", "").strip() or None
	toy = scanner.find_toy(toy_name=name) if name else scanner.find_toy()
	api = SpheroEduAPI(toy)
	api.__enter__()
	return BleSphero(api)
