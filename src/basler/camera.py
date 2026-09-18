"""pypylon Ace wrapper. Stub: no pypylon import yet."""

from __future__ import annotations

from basler.types import CameraFrame


def open_ace(serial_or_index: str | int | None = None) -> object:
	# Why: InstantCamera.Open by serial so we do not grab the wrong Ace.
	raise NotImplementedError("pypylon InstantCamera.Open")


def configure_ace(cam: object, settings: object) -> None:
	# Why: Mono8, exposure µs, fps, LatestImageOnly — pylon-track camera_config.
	raise NotImplementedError("Ace PixelFormat/ExposureTime/AcquisitionFrameRate")


def make_camera_frame(grab: object, frame_index: int, host_time_ns: int) -> CameraFrame:
	# Why: convert grab result to CameraFrame without tracking or motor types.
	raise NotImplementedError("numpy view + camera_ts + host_time_ns")


class AceCamera:
	"""Later: owns InstantCamera; start/stop grabbing on Pylon's thread."""

	def open(self) -> None:
		# Why: experiment calls this, then never touches pypylon.
		raise NotImplementedError("open_ace")

	def configure(self) -> None:
		# Why: apply JSON camera settings once before grabbing.
		raise NotImplementedError("configure_ace")

	def start_grabbing(self) -> None:
		# Why: StartGrabbing(LatestImageOnly) so late frames drop.
		raise NotImplementedError("StartGrabbing")

	def stop_grabbing(self) -> None:
		# Why: shutdown must stop the grab loop before joining threads.
		raise NotImplementedError("StopGrabbing")

	def retrieve_frame(self) -> CameraFrame | None:
		# Why: poll or callback path yields CameraFrame, never TrackingFrame.
		raise NotImplementedError("RetrieveResult → make_camera_frame")
