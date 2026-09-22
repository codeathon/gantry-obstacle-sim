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
		print(f"Sphero BLE unavailable ({exc}); using SpheroStub", file=sys.stderr)
		toy = SpheroStub()
		toy.connect()
		return toy
