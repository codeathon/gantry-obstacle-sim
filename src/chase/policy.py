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
	out.reason = reason
	# Why: convert soft accel (mm/s² scale) to a capped velocity command for Zaber.
	vx = ax * cfg.velocity_gain_s
	vy = ay * cfg.velocity_gain_s
	spd = math.hypot(vx, vy)
	cap = cfg.max_engage_speed_mm_s
	if spd > cap and spd > 1e-6:
		s = cap / spd
		vx *= s
		vy *= s
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
	if wall > 0.35:
		tag = "edge_dodge"
	elif dist < cfg.min_gap_mm:
		tag = "press"
	return rx + tx * lateral + wx, ry + ty * lateral + wy, tag


def _prey_away_unit(
	px: float, py: float, fx: float, fy: float, box: ArenaBounds
) -> tuple[float, float, float]:
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
	pull = min(-gap_err, cfg.max_pull_mm)
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
