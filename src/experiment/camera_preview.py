"""Camera-only entry. Why: pylon-track ferret_tracker analogue — no motor."""

from __future__ import annotations

from basler.camera import AceCamera
from vision.pipeline import TrackingPipeline
from vision.tracking_frame import TrackingFrame, TrialPhase


def main() -> TrackingFrame | None:
	# Why: open Ace, grab, print TrackingFrame; never construct Gantry.
	cam = AceCamera()
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
