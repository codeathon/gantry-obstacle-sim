"""pypylon InstantCamera grabber. Why: stub AceCamera stays for tests/web."""

from __future__ import annotations

import os
import time

from basler.fov import fov_from_camera, fov_from_settings
from basler.load import load_camera_config
from basler.optics import ACE_MODEL, GRAB_STRATEGY
from basler.pylon import load_pylon
from basler.pylon_hw import configure_instant_camera
from basler.settings import CameraSettings
from basler.types import CameraFov, CameraFrame


class PylonAceCamera:
	"""CBaslerUniversalInstantCamera via pypylon. LatestImageOnly."""

	def __init__(
		self,
		settings: CameraSettings | None = None,
		*,
		camera: object | None = None,
		pylon_mod: object | None = None,
		timeout_ms: int = 20,
	) -> None:
		self.settings = settings if settings is not None else load_camera_config()
		self.backend = "pylon"
		self.model = ACE_MODEL
		self.timeout_ms = timeout_ms
		self._injected = camera
		self._pylon = pylon_mod
		self._cam: object | None = None
		self._grabbing = False
		self._index = 0
		self._fov = fov_from_settings(self.settings)

	def open(self) -> None:
		# Why: PylonInitialize + CreateFirstDevice here, not in experiment.
		if self._cam is not None:
			return
		if self._injected is not None:
			self._cam = self._injected
			_call(self._cam, "Open")
			self.model = str(getattr(self._cam, "model", ACE_MODEL))
			return
		self._open_device()

	def configure(self) -> None:
		configure_instant_camera(self._require(), self.settings)
		self._fov = fov_from_camera(self._require(), self.model)

	def start_grabbing(self) -> None:
		# Why: LatestImageOnly drops stale USB frames, like pylon-track.
		cam = self._require()
		strategy = GRAB_STRATEGY
		if self._pylon is not None:
			strategy = self._pylon.GrabStrategy_LatestImageOnly
		cam.StartGrabbing(strategy)
		self._grabbing = True

	def stop_grabbing(self) -> None:
		if self._cam is not None and self._grabbing:
			_call(self._cam, "StopGrabbing")
		self._grabbing = False

	def retrieve_frame(self) -> CameraFrame | None:
		if not self._grabbing:
			return None
		grab = self._retrieve()
		if grab is None:
			return None
		try:
			return self._frame_from_grab(grab)
		finally:
			_call(grab, "Release")

	def close(self) -> None:
		self.stop_grabbing()
		if self._cam is not None:
			_call(self._cam, "Close")
			self._cam = None
		if self._injected is None and self._pylon is not None:
			term = getattr(self._pylon, "PylonTerminate", None)
			if callable(term):
				term()

	def fov(self) -> CameraFov:
		return self._fov

	def _require(self) -> object:
		if self._cam is None:
			raise RuntimeError("PylonAceCamera.open first")
		return self._cam

	def _open_device(self) -> None:
		pylon = load_pylon()
		self._pylon = pylon
		init = getattr(pylon, "PylonInitialize", None)
		if callable(init):
			init()
		self._cam = _create_instant_camera(pylon)
		_call(self._cam, "Open")
		self.model = _model_name(self._cam)

	def _retrieve(self):
		cam = self._require()
		handling = None
		if self._pylon is not None:
			handling = getattr(self._pylon, "TimeoutHandling_Return", None)
		if handling is not None:
			return cam.RetrieveResult(self.timeout_ms, handling)
		return cam.RetrieveResult(self.timeout_ms)

	def _frame_from_grab(self, grab: object) -> CameraFrame | None:
		ok = getattr(grab, "GrabSucceeded", False)
		if callable(ok):
			ok = ok()
		if not ok:
			return None
		self._index += 1
		w = int(getattr(grab, "Width", self._fov.width_px))
		h = int(getattr(grab, "Height", self._fov.height_px))
		return CameraFrame(
			frame_index=self._index,
			camera_ts_ns=int(getattr(grab, "TimeStamp", 0) or 0),
			host_time_ns=time.time_ns(),
			width_px=w,
			height_px=h,
			pixels=_pixels_from_grab(grab),
			grab_ok=True,
		)


def _create_instant_camera(pylon: object) -> object:
	tlf = pylon.TlFactory.GetInstance()
	devices = tlf.EnumerateDevices()
	if not devices:
		raise RuntimeError("no Basler camera (EnumerateDevices empty)")
	serial = os.environ.get("PYLON_SERIAL") or os.environ.get("PYLON_CAMERA") or ""
	info = _pick_device(devices, serial)
	return pylon.InstantCamera(tlf.CreateDevice(info))


def _pick_device(devices: list, serial: str):
	if not serial:
		return devices[0]
	for info in devices:
		get_sn = getattr(info, "GetSerialNumber", None)
		sn = get_sn() if callable(get_sn) else str(info)
		if sn == serial:
			return info
	raise RuntimeError(f"no Basler camera serial {serial}")


def _model_name(cam: object) -> str:
	info = getattr(cam, "GetDeviceInfo", None)
	if callable(info):
		dev = info()
		get_model = getattr(dev, "GetModelName", None)
		if callable(get_model):
			return str(get_model())
	return ACE_MODEL


def _pixels_from_grab(grab: object) -> bytes:
	arr = getattr(grab, "Array", None)
	if arr is not None and hasattr(arr, "tobytes"):
		return bytes(arr.tobytes())
	buf = getattr(grab, "GetBuffer", None)
	if callable(buf):
		return bytes(buf())
	return b""


def _call(obj: object, name: str) -> None:
	fn = getattr(obj, name, None)
	if callable(fn):
		fn()
