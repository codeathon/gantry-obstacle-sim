"""Which animal the Ace blob is. Why: Sphero stays in the tree for a real ferret."""

from __future__ import annotations

import os


def animal_name() -> str:
	raw = os.environ.get("PREY_ANIMAL", "ferret").strip().lower()
	if raw in ("sphero", "mini"):
		return "sphero"
	return "ferret"


def want_sphero() -> bool:
	# Why: default ferret must not open BLE or start the seek thread.
	return animal_name() == "sphero"
