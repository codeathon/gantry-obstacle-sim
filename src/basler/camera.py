"""Ace InstantCamera wrapper using stub Pylon APIs (no pypylon)."""

from __future__ import annotations

import time

from basler.config import configure_camera
from basler.pylon_api import (
	StubPylonCamera,
	instant_camera_close,
	instant_camera_open,
	pylon_initialize,
	pylon_terminate,
	register_image_event_handler,
	retrieve_grab_result,
	start_grabbing_latest_image_only,
	stop_grabbing,
)
from basler.settings import CameraSettings
from basler.types import CameraFrame


def open_ace(serial_or_index: str | int | None = None) -> StubPylonCamera:
	# Why: InstantCamera.Open by serial so we do not grab the wrong Ace.
	pylon_initialize()
	cam = StubPylonCamera()
	cam.note("DeviceSerial", serial_or_index)
	instant_camera_open(cam)
	return cam


def configure_ace(cam: StubPylonCamera, settings: CameraSettings | None = None) -> None:
	# Why: Mono8, AOI, exposure, fps, LatestImageOnly — pylon-track camera_config.
	configure_camera(cam, settings or CameraSettings())


def make_camera_frame(grab: dict, frame_index: int, host_time_ns: int) -> CameraFrame:
	# Why: convert grab result to CameraFrame without tracking or motor types.
	return CameraFrame(
		frame_index=frame_index,
		camera_ts_ns=host_time_ns,
		host_time_ns=host_time_ns,
		width_px=int(grab.get("width") or 0),
		height_px=int(grab.get("height") or 0),
		pixels=None,
	)


class AceCamera:
	"""Owns stub InstantCamera; experiment never touches Pylon nodes."""

	def __init__(self, settings: CameraSettings | None = None) -> None:
		self.settings = settings or CameraSettings()
		self._cam: StubPylonCamera | None = None

	def open(self) -> None:
		self._cam = open_ace()

	def configure(self) -> None:
		configure_ace(self._require(), self.settings)

	def start_grabbing(self) -> None:
		# Why: StartGrabbing(LatestImageOnly) so late frames drop.
		start_grabbing_latest_image_only(self._require())

	def stop_grabbing(self) -> None:
		stop_grabbing(self._require())

	def retrieve_frame(self) -> CameraFrame | None:
		cam = self._require()
		if not cam.grabbing:
			return None
		grab = retrieve_grab_result(cam)
		return make_camera_frame(grab, cam.grab_index, time.time_ns())

	def close(self) -> None:
		if self._cam is None:
			return
		if self._cam.grabbing:
			self.stop_grabbing()
		instant_camera_close(self._cam)
		# Why: PylonTerminate after Close so a later AceCamera can Initialize.
		pylon_terminate()
		self._cam = None

	def register_handler(self, handler: object) -> None:
		register_image_event_handler(self._require(), handler)

	def _require(self) -> StubPylonCamera:
		if self._cam is None:
			raise RuntimeError("AceCamera.open first")
		return self._cam
