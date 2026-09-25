"""Soft keep-away hunt: nudge slightly off the ferret, stay engaged, dodge walls.

Why: discrete 200–600 mm flees ended the chase. This policy holds a preferred
gap, only inches away when pressed, and steers toward arena center near edges.
"""

from __future__ import annotations

import math

from chase.bounds import ArenaBounds, bounds_from_size
from chase.config import ChasePolicyConfig
from chase.decision import ChaseDecision
from vision.tracking_frame import TrackingFrame, TrialPhase


def _clamp01(v: float) -> float:
	return max(0.0, min(1.0, v))


def _norm(x: float, y: float) -> tuple[float, float, float]:
	n = math.hypot(x, y)
	if n < 1e-6:
		return 0.0, 0.0, 0.0
	return x / n, y / n, n


def fill_tracking_derived(frame: TrackingFrame) -> None:
	"""pylon-track fill_tracking_derived: bearing 0=right, 90=up (Y flipped)."""
	frame.distance_mm = -1.0
	frame.bearing_deg = 0.0
	frame.closing_speed_mm_s = 0.0
	if not frame.both_valid():
		return
	dx = frame.prey.x_mm - frame.ferret.x_mm
	dy = frame.prey.y_mm - frame.ferret.y_mm
	dist = math.hypot(dx, dy)
	frame.distance_mm = dist
	frame.bearing_deg = math.degrees(math.atan2(-dy, dx))
	heading = math.radians(frame.ferret.direction_deg)
	vx = math.cos(heading) * frame.ferret.speed_mm_s
	vy = -math.sin(heading) * frame.ferret.speed_mm_s
	if dist > 1e-3:
		frame.closing_speed_mm_s = (vx * dx + vy * dy) / dist


def compute_chase_decision(
	scene: TrackingFrame,
	cfg: object,
	width_mm: float,
	height_mm: float,
	bounds: ArenaBounds | None = None,
) -> ChaseDecision:
	# Why: TrackingFrame → velocity command; idle unless TrialPhase.running.
	out = ChaseDecision(decision_time_ns=scene.host_time_ns)
	if scene.trial_phase != TrialPhase.running:
		out.reason = "trial_not_running"
		return out
	if not scene.both_valid():
		out.reason = "tracks_invalid"
		return out
	if cfg is None:
		# Why: Ace-only dry runs have no keep-away gains yet.
		out.reason = "stub_idle"
		return out
	box = bounds or bounds_from_size(width_mm, height_mm)
	return _engage(scene, cfg, box, out)


def _engage(
	scene: TrackingFrame,
	cfg: object,
	box: ArenaBounds,
	out: ChaseDecision,
) -> ChaseDecision:
	assert isinstance(cfg, ChasePolicyConfig)
	if scene.quality.ferret_confidence < 0.3 or scene.quality.prey_confidence < 0.3:
		out.reason = "low_track_confidence"
		return out
	out.enable_motion = True
	ax, ay, reason = _engage_accel(scene, cfg, box, out)
	# Why: convert soft accel (mm/s² scale) to a capped velocity command for Zaber.
	vx, vy = _hold_ring_vel(
		ax * cfg.velocity_gain_s, ay * cfg.velocity_gain_s, scene, cfg, box
	)
	vx, vy, lure = _lure_prey(vx, vy, scene, cfg, box)
	if lure:
		reason = lure
	spd = math.hypot(vx, vy)
	cap = cfg.max_engage_speed_mm_s
	if spd > cap and spd > 1e-6:
		s = cap / spd
		vx *= s
		vy *= s
	out.reason = reason
	out.target_vx_mm_s = vx
	out.target_vy_mm_s = vy
	out.flee_direction_deg = math.degrees(math.atan2(-vy, vx)) if spd > 1 else 0.0
	out.threat = _clamp01(out.dist_threat)
	return out


def _engage_accel(
	scene: TrackingFrame,
	cfg: ChasePolicyConfig,
	box: ArenaBounds,
	out: ChaseDecision,
) -> tuple[float, float, str]:
	px, py = scene.prey.x_mm, scene.prey.y_mm
	fx, fy = scene.ferret.x_mm, scene.ferret.y_mm
	ux, uy, dist = _prey_away_unit(px, py, fx, fy, box)
	rx, ry, tag = _gap_radial(ux, uy, dist, cfg, out)
	tx, ty, lateral = _center_slip(ux, uy, px, py, box, scene, cfg)
	wx, wy, wall = _wall_push(px, py, box, cfg)
	out.wall_push = wall
	out.approach_threat = _clamp01(max(0.0, scene.closing_speed_mm_s) / 800.0)
	out.cone_threat = wall
	if dist > cfg.preferred_gap_mm:
		# Why: edge dodge used to cancel reel-in and park the toy outside the ring.
		wx, wy = _wall_along_reel(wx, wy, -ux, -uy)
		tag = "reel_in"
	elif wall > 0.35:
		tag = "edge_dodge"
	elif dist < cfg.min_gap_mm:
		tag = "press"
	return rx + tx * lateral + wx, ry + ty * lateral + wy, tag


def _hold_ring_vel(
	vx: float,
	vy: float,
	scene: TrackingFrame,
	cfg: ChasePolicyConfig,
	box: ArenaBounds,
) -> tuple[float, float]:
	# Why: if the toy sits outside the keep-away circle, walk it back so the
	# ferret (or Mini) always has something to chase. Aim at the rail-clamped
	# ferret so an off-travel blob cannot pin +x into a wall.
	fx = min(max(scene.ferret.x_mm, box.x_min), box.x_max)
	fy = min(max(scene.ferret.y_mm, box.y_min), box.y_max)
	tx, ty, dist = _norm(fx - scene.prey.x_mm, fy - scene.prey.y_mm)
	if dist <= cfg.preferred_gap_mm:
		return vx, vy
	# Why: Mini lure must not slam 240 mm/s into the ring; BLE cannot follow.
	if float(getattr(cfg, "lure_speed_mm_s", 0.0) or 0.0) > 0:
		return vx, vy
	floor = min(cfg.max_engage_speed_mm_s * 0.5, 240.0)
	spd = math.hypot(vx, vy)
	if spd >= floor and vx * tx + vy * ty >= 0.0:
		return vx, vy
	use = max(spd, floor)
	return tx * use, ty * use


def _wall_along_reel(wx: float, wy: float, tx: float, ty: float) -> tuple[float, float]:
	# Why: keep wall slide, but never reverse the walk back toward the ferret.
	opp = wx * tx + wy * ty
	if opp < 0.0:
		wx -= tx * opp
		wy -= ty * opp
	return wx, wy


def _prey_away_unit(
	px: float, py: float, fx: float, fy: float, box: ArenaBounds
) -> tuple[float, float, float]:
	fx = min(max(fx, box.x_min), box.x_max)
	fy = min(max(fy, box.y_min), box.y_max)
	ux, uy, dist = _norm(px - fx, py - fy)
	if dist >= 1e-3:
		return ux, uy, dist
	# Overlap: break out toward gantry center so we do not freeze.
	ux, uy, _ = _norm(box.cx - px, box.cy - py)
	return ux, uy, 0.0


def _gap_radial(
	ux: float, uy: float, dist: float, cfg: ChasePolicyConfig, out: ChaseDecision
) -> tuple[float, float, str]:
	# Close → push away; far → ease back toward ferret (keeps the hunt alive).
	gap_err = cfg.preferred_gap_mm - dist
	out.gap_error_mm = gap_err
	if gap_err > 0:
		out.dist_threat = _clamp01(gap_err / max(cfg.preferred_gap_mm - cfg.min_gap_mm, 1.0))
		return ux * gap_err * cfg.away_gain, uy * gap_err * cfg.away_gain, "nudge_away"
	out.dist_threat = 0.0
	# Why: a tiny gap error looked parked on the short X-MCC; floor the pull.
	pull = max(min(-gap_err, cfg.max_pull_mm), cfg.preferred_gap_mm * 0.35)
	return -ux * pull * cfg.toward_gain, -uy * pull * cfg.toward_gain, "reel_in"


def _center_slip(
	ux: float,
	uy: float,
	px: float,
	py: float,
	box: ArenaBounds,
	scene: TrackingFrame,
	cfg: ChasePolicyConfig,
) -> tuple[float, float, float]:
	# Lateral slip when pressed: avoid head-on stall, stay playful.
	tx, ty = -uy, ux
	# Bias slip toward gantry center so we do not choose the wall side of a tangent.
	cx, cy = box.cx - px, box.cy - py
	if tx * cx + ty * cy < 0:
		tx, ty = -tx, -ty
	return tx, ty, max(0.0, scene.closing_speed_mm_s) * cfg.lateral_gain


def _wall_push(
	x: float,
	y: float,
	box: ArenaBounds,
	cfg: ChasePolicyConfig,
) -> tuple[float, float, float]:
	"""Repel from gantry edges toward open travel. Strength grows inside margin."""
	m = max(cfg.wall_margin_mm, 1.0)
	left = max(0.0, m - (x - box.x_min)) / m
	right = max(0.0, m - (box.x_max - x)) / m
	top = max(0.0, m - (y - box.y_min)) / m
	bottom = max(0.0, m - (box.y_max - y)) / m
	# Squared so corners (two walls) kick harder than a single edge.
	# Near left → +x; near top → +y (origin is top-left in arena mm).
	px = (left * left - right * right) * cfg.wall_gain
	py = (top * top - bottom * bottom) * cfg.wall_gain
	# Extra center pull when deep in a corner.
	corner = max(left, right) * max(top, bottom)
	if corner > 0:
		cx, cy, _ = _norm(box.cx - x, box.cy - y)
		px += cx * corner * cfg.corner_gain
		py += cy * corner * cfg.corner_gain
	strength = max(left, right, top, bottom)
	return px, py, strength


def _lure_prey(
	vx: float,
	vy: float,
	scene: TrackingFrame,
	cfg: ChasePolicyConfig,
	box: ArenaBounds,
) -> tuple[float, float, str | None]:
	# Why: Mini rolls on a slow GATT loop; the X-MCC used to enter and leave
	# the ring before SM-6399 could start following.
	cap = float(getattr(cfg, "lure_speed_mm_s", 0.0) or 0.0)
	if cap <= 0.0:
		return vx, vy, None
	fx = min(max(scene.ferret.x_mm, box.x_min), box.x_max)
	fy = min(max(scene.ferret.y_mm, box.y_min), box.y_max)
	tx, ty, dist = _norm(fx - scene.prey.x_mm, fy - scene.prey.y_mm)
	if dist > cfg.preferred_gap_mm:
		return tx * min(cap, 80.0), ty * min(cap, 80.0), "reel_in"
	if not _hunter_following(scene):
		if dist > cfg.min_gap_mm + 20.0:
			creep = min(40.0, cap * 0.5)
			return tx * creep, ty * creep, "wait_hunter"
		return 0.0, 0.0, "wait_hunter"
	return -tx * min(cap, 70.0), -ty * min(cap, 70.0), "lead_away"


def _hunter_following(scene: TrackingFrame) -> bool:
	# Why: Ace speed on the Mini blob is the cue that BLE roll actually started.
	if scene.closing_speed_mm_s > 25.0:
		return True
	return scene.ferret.speed_mm_s > 40.0 and scene.closing_speed_mm_s > 5.0
