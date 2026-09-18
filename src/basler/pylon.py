"""Lazy pypylon import. Why: tests/web must not load the Basler wheel."""

from __future__ import annotations

import os


def load_pylon():
	try:
		from pypylon import pylon
	except ImportError as exc:
		raise RuntimeError(
			"pypylon is not installed; pip install 'prey-gantry[pylon]'"
		) from exc
	return pylon


def want_ace() -> bool:
	flag = os.environ.get("PREY_ACE", "").strip().lower()
	if flag in ("1", "true", "yes", "on"):
		return True
	return bool(os.environ.get("PYLON_SERIAL") or os.environ.get("PYLON_CAMERA"))
