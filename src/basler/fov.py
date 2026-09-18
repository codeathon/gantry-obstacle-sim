"""FOV helpers. Why: millimetres come from Ace Width/Height × GSD, not a guess."""

from __future__ import annotations

from pathlib import Path

from basler.optics import ACE_MODEL, GSD_MM_PX
from basler.settings import CameraSettings
from basler.types import CameraFov, CameraFrame


def fov_from_settings(settings: CameraSettings, model: str = ACE_MODEL) -> CameraFov:
	return CameraFov(
		width_px=settings.width,
		height_px=settings.height,
		offset_x=settings.offset_x,
		offset_y=settings.offset_y,
		gsd_mm_per_px=GSD_MM_PX,
		model=model,
	)


def node_value(cam: object, name: str, default: object = 0) -> object:
	node = getattr(cam, name, None)
	if node is None:
		return default
	getv = getattr(node, "GetValue", None)
	if callable(getv):
		return getv()
	return getattr(node, "Value", node)


def fov_from_camera(cam: object, model: str = ACE_MODEL) -> CameraFov:
	# Why: after configure, firmware AOI is the truth even if JSON was clipped.
	return CameraFov(
		width_px=int(node_value(cam, "Width", 0)),
		height_px=int(node_value(cam, "Height", 0)),
		offset_x=int(node_value(cam, "OffsetX", 0)),
		offset_y=int(node_value(cam, "OffsetY", 0)),
		gsd_mm_per_px=GSD_MM_PX,
		model=model,
	)


def save_mono8_pgm(path: Path, frame: CameraFrame) -> None:
	# Why: PGM needs no Pillow; pypylon Array is already Mono8.
	pixels = frame.pixels if isinstance(frame.pixels, (bytes, bytearray)) else None
	if pixels is None:
		pixels = bytes(frame.width_px * frame.height_px)
	header = f"P5\n{frame.width_px} {frame.height_px}\n255\n".encode("ascii")
	path.write_bytes(header + bytes(pixels))
