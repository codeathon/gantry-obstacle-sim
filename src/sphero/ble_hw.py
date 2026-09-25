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
	# Why: uvicorn already runs an event loop; Bleak's asyncio.run() needs a bare thread.
	# Stay on this thread when there is no loop (demo_roll / sphero-seek).
	import asyncio

	try:
		asyncio.get_running_loop()
	except RuntimeError:
		return _connect_ble_locked()
	return _call_in_fresh_thread(_connect_ble_locked)


def _connect_ble_locked() -> BleSphero:
	from spherov2 import scanner
	from spherov2.sphero_edu import SpheroEduAPI

	name = os.environ.get("SPHERO_NAME", "").strip() or None
	toy = _scan_toy(scanner, name)
	api = SpheroEduAPI(toy)
	api.__enter__()
	print(f"Sphero BLE connected {name or toy}", flush=True)
	return BleSphero(api)


def _scan_toy(scanner, name: str | None):
	# Why: Mini stops advertising after a long hunt or a dead battery.
	import time

	last: BaseException | None = None
	for _ in range(3):
		try:
			toy = scanner.find_toy(toy_name=name) if name else scanner.find_toy()
			if toy is not None:
				return toy
			last = RuntimeError(f"no Sphero advertising as {name or 'any Mini'}")
		except Exception as exc:
			last = exc
		time.sleep(1.5)
	raise last or RuntimeError("Sphero BLE scan failed")


def _call_in_fresh_thread(fn):
	import threading

	box: dict = {}

	def run() -> None:
		try:
			box["ok"] = fn()
		except BaseException as exc:
			box["err"] = exc

	th = threading.Thread(target=run, name="sphero-ble-open", daemon=True)
	th.start()
	th.join(timeout=30.0)
	if "err" in box:
		raise box["err"]
	if "ok" not in box:
		raise TimeoutError("Sphero BLE open timed out")
	return box["ok"]
