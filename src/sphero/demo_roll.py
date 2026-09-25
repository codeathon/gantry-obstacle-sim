"""Live Mini smoke: connect over BLE and roll four headings.

Why: lab check that SM-6399 moves via the API, with no Ace or gantry.
"""

from __future__ import annotations

import os
import sys
import time

# 0=forward after aim, then right, back, left — a small square.
_HEADINGS = (0, 90, 180, 270)


def run(seconds: float = 1.5, speed: float = 80.0) -> None:
	os.environ.setdefault("PREY_SPHERO_REQUIRE", "1")
	from sphero.ble_hw import connect_ble

	toy = connect_ble()
	try:
		_drive_square(toy, seconds, speed)
	finally:
		toy.stop()
		toy.close()


def _drive_square(toy: object, seconds: float, speed: float) -> None:
	led = getattr(toy, "set_led", None)
	if callable(led):
		led(0, 180, 80)
	aim = getattr(toy, "aim", None)
	if callable(aim):
		aim()
	print("connected; rolling 0 / 90 / 180 / 270 deg", flush=True)
	for heading in _HEADINGS:
		print(f"roll speed={speed:.0f} heading={heading} for {seconds:.1f}s", flush=True)
		# Why: Edu roll() blocks for duration; do not sleep the same interval twice.
		toy.roll(speed, heading, duration=seconds)
		toy.stop()
		# Why: Mini needs a short settle between back-to-back rolls.
		time.sleep(0.4)
	print("ok: Mini accepted roll commands", flush=True)


def main(argv: list[str] | None = None) -> int:
	del argv
	name = os.environ.get("SPHERO_NAME", "").strip() or "(first Mini found)"
	print(f"looking for {name}", flush=True)
	run()
	return 0


if __name__ == "__main__":
	sys.exit(main())
