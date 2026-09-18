"""Grabber factory. Why: experiment never constructs InstantCamera itself."""

from __future__ import annotations

import os
import sys

from basler.camera import AceCamera
from basler.pylon import want_ace
from basler.protocol import AceGrabber
from basler.settings import CameraSettings


def open_grabber(settings: CameraSettings | None = None) -> AceGrabber:
	# Why: real Ace when PREY_ACE / PYLON_SERIAL; stub so tests stay SDK-free.
	if not want_ace():
		return AceCamera(settings)
	return _open_pylon_or_stub(settings)


def _open_pylon_or_stub(settings: CameraSettings | None) -> AceGrabber:
	from basler.pylon_camera import PylonAceCamera

	cam = PylonAceCamera(settings)
	try:
		cam.open()
		return cam
	except Exception as exc:
		if os.environ.get("PREY_ACE_REQUIRE", "").strip().lower() in (
			"1", "true", "yes",
		):
			raise
		print(f"Basler Ace unavailable ({exc}); using stub AceCamera", file=sys.stderr)
		return AceCamera(settings)
