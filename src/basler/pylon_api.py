"""No-op Pylon node calls. Why: names match pylon-track camera_config.cpp.

Does not import pypylon. Records which GenICam nodes would be SetValue'd.
"""

from __future__ import annotations


class StubPylonCamera:
	"""Stand-in for Pylon.CBaslerUniversalInstantCamera."""

	def __init__(self) -> None:
		self.calls: list[str] = []
		self.nodes: dict[str, object] = {}
		self.opened = False
		self.grabbing = False
		self.handler = None
		self.grab_index = 0

	def note(self, api: str, value: object | None = None) -> None:
		self.calls.append(api)
		if value is not None:
			self.nodes[api] = value


def pylon_initialize() -> None:
	# Why: Pylon.PylonInitialize() before any InstantCamera.
	return


def pylon_terminate() -> None:
	# Why: Pylon.PylonTerminate() after last camera close.
	return


def instant_camera_open(cam: StubPylonCamera) -> None:
	# Why: cam.Open() at start of pylon-track configure_camera.
	cam.note("Open")
	cam.opened = True


def instant_camera_close(cam: StubPylonCamera) -> None:
	# Why: Close() on shutdown so USB can be reclaimed.
	cam.note("Close")
	cam.opened = False


def set_pixel_format_mono8(cam: StubPylonCamera) -> None:
	# Why: PixelFormat_Mono8 is required in configure_camera.
	cam.note("PixelFormat", "Mono8")


def set_binning(cam: StubPylonCamera, hx: int, vy: int, selector: str) -> None:
	# Why: BinningSelector Region1/Sensor then BinningHorizontal/Vertical.
	cam.note("BinningSelector", selector)
	cam.note("BinningHorizontal", hx)
	cam.note("BinningVertical", vy)


def set_aoi(cam: StubPylonCamera, width: int, height: int, ox: int, oy: int) -> None:
	# Why: Width/Height/OffsetX/OffsetY required AOI nodes.
	cam.note("Width", width)
	cam.note("Height", height)
	cam.note("OffsetX", ox)
	cam.note("OffsetY", oy)


def set_reverse(cam: StubPylonCamera, reverse_x: bool, reverse_y: bool) -> None:
	# Why: ReverseX/ReverseY optional flips in camera_config.json.
	if reverse_x:
		cam.note("ReverseX", True)
	if reverse_y:
		cam.note("ReverseY", True)


def set_black_level_gamma(cam: StubPylonCamera, black: int, gamma: float) -> None:
	# Why: BlackLevel/Gamma only applied when non-default in pylon-track.
	if black != 0:
		cam.note("BlackLevel", black)
	if abs(gamma - 1.0) > 1e-6:
		cam.note("Gamma", gamma)


def set_exposure(cam: StubPylonCamera, auto: bool, us: float, mode: str) -> None:
	# Why: BslExposureTimeMode + ExposureAuto + ExposureTime µs.
	cam.note("BslExposureTimeMode", mode)
	cam.note("ExposureAuto", "Continuous" if auto else "Off")
	if not auto:
		cam.note("ExposureTime", us)


def set_gain(cam: StubPylonCamera, auto: bool, db: float) -> None:
	# Why: GainAuto + Gain dB like configure_camera.
	cam.note("GainAuto", "Continuous" if auto else "Off")
	if not auto:
		cam.note("Gain", db)


def set_frame_rate(cam: StubPylonCamera, enable: bool, fps: float) -> None:
	# Why: AcquisitionFrameRateEnable + AcquisitionFrameRate.
	cam.note("AcquisitionFrameRateEnable", enable)
	if enable:
		cam.note("AcquisitionFrameRate", fps)


def set_trigger_off(cam: StubPylonCamera) -> None:
	# Why: TriggerMode_Off — pylon-track rejects any other mode.
	cam.note("TriggerMode", "Off")


def set_throughput_limit(cam: StubPylonCamera, mode: str, mbps: float) -> None:
	# Why: DeviceLinkThroughputLimitMode On/Off + bytes/s from Mbps.
	cam.note("DeviceLinkThroughputLimitMode", mode)
	if mode == "On":
		cam.note("DeviceLinkThroughputLimit", int(mbps * 1e6 / 8.0))


def start_grabbing_latest_image_only(cam: StubPylonCamera) -> None:
	# Why: StartGrabbing(GrabStrategy_LatestImageOnly) drops stale USB frames.
	cam.note("StartGrabbing", "LatestImageOnly")
	cam.grabbing = True


def stop_grabbing(cam: StubPylonCamera) -> None:
	# Why: StopGrabbing before Close on experiment shutdown.
	cam.note("StopGrabbing")
	cam.grabbing = False


def retrieve_grab_result(cam: StubPylonCamera) -> dict:
	# Why: RetrieveResult analogue — empty buffer, no USB transfer.
	cam.note("RetrieveResult")
	cam.grab_index += 1
	return {
		"index": cam.grab_index,
		"width": cam.nodes.get("Width", 0),
		"height": cam.nodes.get("Height", 0),
	}


def set_scaling(cam: StubPylonCamera, scale: float) -> None:
	# Why: ScalingHorizontal only when < 1 in pylon-track configure_camera.
	cam.note("ScalingHorizontal", scale)


def register_image_event_handler(cam: StubPylonCamera, handler: object) -> None:
	# Why: CameraTrackingService : CImageEventHandler in pylon-track.
	cam.note("RegisterImageEventHandler")
	cam.handler = handler
