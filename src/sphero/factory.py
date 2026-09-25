"""Open a Sphero toy. Why: experiment never constructs Bleak itself."""

from __future__ import annotations

import os
import sys

from sphero.client import SpheroStub


def open_sphero() -> object:
	# Why: PREY_ANIMAL=sphero should try the Mini; tests inject a stub instead.
	if os.environ.get("SPHERO_STUB", "").strip().lower() in ("1", "true", "yes"):
		toy = SpheroStub()
		toy.connect()
		return toy
	return _open_ble_or_fallback()


def _open_ble_or_fallback() -> object:
	try:
		from sphero.ble_hw import connect_ble

		return connect_ble()
	except Exception as exc:
		if os.environ.get("PREY_SPHERO_REQUIRE", "").strip().lower() in (
			"1", "true", "yes",
		):
			raise
		# Why: ToyNotFoundError str() is empty, so "unavailable ()" hid the cause.
		print(f"Sphero BLE unavailable ({_exc_text(exc)}); using SpheroStub", file=sys.stderr)
		print(
			"Wake the Mini (double-tap / charger) then SPHERO_NAME=SM-6399 "
			"python -m sphero.demo_roll, or PREY_SPHERO_REQUIRE=1 to fail instead.",
			file=sys.stderr,
		)
		toy = SpheroStub()
		toy.connect()
		return toy


def _exc_text(exc: BaseException) -> str:
	msg = str(exc).strip()
	name = type(exc).__name__
	return f"{name}: {msg}" if msg else name
