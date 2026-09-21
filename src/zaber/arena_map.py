"""Map X-MCC travel onto the Ace FOV so the toy uses the full HUD."""

from __future__ import annotations

from chase.bounds import ArenaBounds


def travel_box(gantry, fov_w: float, fov_h: float) -> ArenaBounds:
	# Why: stub/sim have no rails; only hardware settings are firmware travel.
	if getattr(gantry, "backend", "") != "hardware":
		w = float(getattr(gantry, "width_mm", fov_w))
		h = float(getattr(gantry, "height_mm", fov_h))
		return ArenaBounds(0.0, w, 0.0, h)
	s = getattr(gantry, "settings", None)
	if s is None:
		return ArenaBounds(0.0, fov_w, 0.0, fov_h)
	return ArenaBounds(
		float(s.x_min), float(s.x_max), float(s.y_min), float(s.y_max)
	)


def gantry_to_arena(
	x_mm: float, y_mm: float, box: ArenaBounds, fov_w: float, fov_h: float
) -> tuple[float, float]:
	# Why: firmware rails are smaller than the camera; stretch them to the canvas.
	return (
		(x_mm - box.x_min) / box.width_mm * fov_w,
		(y_mm - box.y_min) / box.height_mm * fov_h,
	)


def arena_to_gantry(
	x_mm: float, y_mm: float, box: ArenaBounds, fov_w: float, fov_h: float
) -> tuple[float, float]:
	# Why: pointer/Ace mm must land on the same rail corner the HUD shows.
	return (
		box.x_min + x_mm / max(fov_w, 1e-6) * box.width_mm,
		box.y_min + y_mm / max(fov_h, 1e-6) * box.height_mm,
	)


def scale_vel(
	vx: float, vy: float, box: ArenaBounds, fov_w: float, fov_h: float, *, to_arena: bool
) -> tuple[float, float]:
	sx = fov_w / box.width_mm
	sy = fov_h / box.height_mm
	if to_arena:
		return vx * sx, vy * sy
	return vx / sx, vy / sy
