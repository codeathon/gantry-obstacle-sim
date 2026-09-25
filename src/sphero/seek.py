"""Arena mm → Mini roll. Why: Ace ferret + encoder prey already share last_scene."""

from __future__ import annotations

import math

from chase.bounds import ArenaBounds
from vision.tracking_frame import TrackState, TrialPhase


def seek_command(
	ferret: TrackState,
	prey: TrackState,
	phase: TrialPhase = TrialPhase.running,
	*,
	max_speed: float = 180.0,
	aim_offset_deg: float = 0.0,
	arrive_mm: float = 40.0,
	bounds: ArenaBounds | None = None,
	wall_margin_mm: float = 0.0,
) -> tuple[float, float] | None:
	# Why: None means stop — invalid Ace or idle trial must not keep rolling.
	if phase != TrialPhase.running or not ferret.valid or not prey.valid:
		return None
	dx = prey.x_mm - ferret.x_mm
	dy = prey.y_mm - ferret.y_mm
	dist = math.hypot(dx, dy)
	# Why: fill_tracking_derived uses 0=right, 90=up (Y flipped).
	heading = math.degrees(math.atan2(-dy, dx)) + aim_offset_deg
	heading = heading % 360.0
	speed = 0.0 if dist <= arrive_mm else max_speed
	if bounds is None or wall_margin_mm <= 0.0:
		return speed, heading
	# Why: Mini has no firmware rails; reuse gantry travel so it cannot pin on a wall.
	return _keep_in(
		ferret.x_mm, ferret.y_mm, speed, heading, bounds, wall_margin_mm, max_speed
	)


def _keep_in(
	x: float,
	y: float,
	speed: float,
	heading: float,
	box: ArenaBounds,
	margin: float,
	max_speed: float,
) -> tuple[float, float]:
	rad = math.radians(heading)
	vx = speed * math.cos(rad)
	vy = -speed * math.sin(rad)
	# Why: kill wall-leaving seek first so inward push is not cancelled to 0.
	vx, vy = _clip_outward(x, y, vx, vy, box)
	wx, wy = _wall_vel(x, y, box, margin, max_speed)
	vx, vy = _clip_outward(x, y, vx + wx, vy + wy, box)
	spd = math.hypot(vx, vy)
	if spd < 1e-6:
		return 0.0, heading
	if spd > max_speed:
		vx *= max_speed / spd
		vy *= max_speed / spd
		spd = max_speed
	return spd, math.degrees(math.atan2(-vy, vx)) % 360.0


def _wall_vel(
	x: float, y: float, box: ArenaBounds, margin: float, max_speed: float
) -> tuple[float, float]:
	# Why: same inset as chase _wall_push — squared so corners kick harder.
	m = max(margin, 1.0)
	left = max(0.0, m - (x - box.x_min)) / m
	right = max(0.0, m - (box.x_max - x)) / m
	top = max(0.0, m - (y - box.y_min)) / m
	bottom = max(0.0, m - (box.y_max - y)) / m
	px = left * left - right * right
	py = top * top - bottom * bottom
	if x < box.x_min:
		px += 1.0
	elif x > box.x_max:
		px -= 1.0
	if y < box.y_min:
		py += 1.0
	elif y > box.y_max:
		py -= 1.0
	n = math.hypot(px, py)
	if n < 1e-6:
		return 0.0, 0.0
	mag = max_speed * min(n, 1.0)
	return (px / n) * mag, (py / n) * mag


def _clip_outward(
	x: float, y: float, vx: float, vy: float, box: ArenaBounds
) -> tuple[float, float]:
	# Why: match X-MCC _cap_vel — kill only the axis that would leave the box.
	if x <= box.x_min and vx < 0:
		vx = 0.0
	if x >= box.x_max and vx > 0:
		vx = 0.0
	if y <= box.y_min and vy < 0:
		vy = 0.0
	if y >= box.y_max and vy > 0:
		vy = 0.0
	return vx, vy
