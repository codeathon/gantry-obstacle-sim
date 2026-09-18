"""Camera-only entry. Why: pylon-track ferret_tracker analogue — no motor."""

from __future__ import annotations

from basler.factory import open_grabber
from vision.pipeline import TrackingPipeline
from vision.tracking_frame import TrackingFrame, TrialPhase


def main() -> TrackingFrame | None:
	# Why: open Ace (pypylon or stub), grab, never construct Gantry.
	cam = open_grabber()
	cam.open()
	cam.configure()
	cam.start_grabbing()
	try:
		grabbed = cam.retrieve_frame()
		if grabbed is None:
			return None
		return TrackingPipeline().process(grabbed, TrialPhase.warmup)
	finally:
		cam.close()


if __name__ == "__main__":
	main()
