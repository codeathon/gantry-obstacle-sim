"""ferret_behavior camera_calibration.toml → ground-plane millimetres.

Why: Charuco world XY is the fixed arena. pylon-track 1.035 mm/px is the
missing a2A1920, not acA1300-200um serial 24676894.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path

Vec3 = tuple[float, float, float]


def default_calib_path() -> Path:
	return Path(__file__).resolve().parents[2] / "config" / "camera_calibration.toml"


@dataclass(frozen=True)
class GroundCam:
	serial: str
	width_px: int
	height_px: int
	fx: float
	fy: float
	cx: float
	cy: float
	ax: Vec3
	ay: Vec3
	az: Vec3
	pos: Vec3
	xmin: float
	xmax: float
	ymin: float
	ymax: float

	@property
	def width_mm(self) -> float:
		return self.xmax - self.xmin

	@property
	def height_mm(self) -> float:
		return self.ymax - self.ymin

	@property
	def gsd_mm_per_px(self) -> float:
		# Why: HUD/exclude still want one scale; ferret XY uses the plane hit.
		return self.width_mm / max(self.width_px, 1)


def load_ground_cams(path: Path | None = None) -> dict[str, GroundCam]:
	cfg = path or default_calib_path()
	if not cfg.is_file():
		return {}
	with cfg.open("rb") as fh:
		raw = tomllib.load(fh)
	out: dict[str, GroundCam] = {}
	for key, block in raw.items():
		if not str(key).startswith("cam_") or not isinstance(block, dict):
			continue
		cam = _cam_from_block(block)
		out[cam.serial] = cam
	return out


def ground_cam_for_serial(serial: str, path: Path | None = None) -> GroundCam | None:
	if not serial:
		return None
	return load_ground_cams(path).get(serial)


def overhead_ground_cam(path: Path | None = None) -> GroundCam | None:
	# Why: ferret is on the floor; side NIR look across the arena (az_z ~ -0.89).
	cams = load_ground_cams(path)
	if not cams:
		return None
	return min(cams.values(), key=lambda c: c.az[2])


def px_to_world(cam: GroundCam, u: float, v: float) -> tuple[float, float]:
	# Ray in camera: K^{-1}[u,v,1]; world_orientation columns are camera axes.
	x = (u - cam.cx) / cam.fx
	y = (v - cam.cy) / cam.fy
	d = _add(_add(_scale(cam.ax, x), _scale(cam.ay, y)), cam.az)
	if abs(d[2]) < 1e-9:
		raise ValueError("ray parallel to ground")
	# Why: groundplane_calibration — world Z = 0 is the floor.
	t = -cam.pos[2] / d[2]
	hit = _add(cam.pos, _scale(d, t))
	return hit[0], hit[1]


def px_to_arena(cam: GroundCam, u: float, v: float) -> tuple[float, float]:
	wx, wy = px_to_world(cam, u, v)
	# Why: image +v is camera +Y ≈ −world Y; flip so top-left stays (0,0).
	return wx - cam.xmin, cam.ymax - wy


def world_to_px(cam: GroundCam, wx: float, wy: float) -> tuple[float, float]:
	# Why: encoder/Charuco world → Ace pixel so the toy disc sits on the carriage.
	dx, dy, dz = wx - cam.pos[0], wy - cam.pos[1], -cam.pos[2]
	xc = cam.ax[0] * dx + cam.ax[1] * dy + cam.ax[2] * dz
	yc = cam.ay[0] * dx + cam.ay[1] * dy + cam.ay[2] * dz
	zc = cam.az[0] * dx + cam.az[1] * dy + cam.az[2] * dz
	if abs(zc) < 1e-9:
		raise ValueError("point behind camera")
	return cam.fx * xc / zc + cam.cx, cam.fy * yc / zc + cam.cy


def arena_to_px(cam: GroundCam, ax: float, ay: float) -> tuple[float, float]:
	return world_to_px(cam, cam.xmin + ax, cam.ymax - ay)


def _cam_from_block(block: dict) -> GroundCam:
	name = str(block.get("name", ""))
	serial = name.split("_", 1)[0]
	size = block["size"]
	k = block["matrix"]
	o = block["world_orientation"]
	p = tuple(float(v) for v in block["world_position"])
	ax, ay, az = _col(o, 0), _col(o, 1), _col(o, 2)
	partial = GroundCam(
		serial, int(size[0]), int(size[1]),
		float(k[0][0]), float(k[1][1]), float(k[0][2]), float(k[1][2]),
		ax, ay, az, p, 0.0, 1.0, 0.0, 1.0,
	)
	return _with_footprint(partial)


def _with_footprint(cam: GroundCam) -> GroundCam:
	corners = (
		px_to_world(cam, 0.0, 0.0),
		px_to_world(cam, cam.width_px - 1.0, 0.0),
		px_to_world(cam, cam.width_px - 1.0, cam.height_px - 1.0),
		px_to_world(cam, 0.0, cam.height_px - 1.0),
	)
	xs = [c[0] for c in corners]
	ys = [c[1] for c in corners]
	return GroundCam(
		cam.serial, cam.width_px, cam.height_px, cam.fx, cam.fy, cam.cx, cam.cy,
		cam.ax, cam.ay, cam.az, cam.pos,
		min(xs), max(xs), min(ys), max(ys),
	)


def _col(m: list, i: int) -> Vec3:
	return (float(m[0][i]), float(m[1][i]), float(m[2][i]))


def _add(a: Vec3, b: Vec3) -> Vec3:
	return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def _scale(a: Vec3, s: float) -> Vec3:
	return (a[0] * s, a[1] * s, a[2] * s)
