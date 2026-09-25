"""Soft keep-away policy: preferred gap, slight nudge, wall dodge."""

from simulation.chase_policy import compute_chase_decision, fill_tracking_derived
from simulation.config import load_sim_config
from simulation.tracking_frame import TrackingFrame, TrackingQuality, TrackState, TrialPhase


def _cfg():
	return load_sim_config()


def _scene(fx, fy, px, py, heading=0.0, speed=800.0, phase=TrialPhase.running):
	frame = TrackingFrame(
		host_time_ns=1_000_000_000,
		ferret=TrackState(fx, fy, speed, heading, True),
		prey=TrackState(px, py, 0.0, 0.0, True),
		quality=TrackingQuality(1.0, 1.0),
		trial_phase=phase,
	)
	fill_tracking_derived(frame)
	return frame


def test_idle_when_trial_not_running():
	cfg = _cfg()
	d = compute_chase_decision(
		_scene(100, 100, 200, 100, phase=TrialPhase.warmup),
		cfg.chase,
		cfg.camera.width_mm,
		cfg.camera.height_mm,
	)
	assert d.reason == "trial_not_running"
	assert not d.enable_motion


def test_close_nudge_away_not_flee():
	cfg = _cfg()
	# Ferret presses from the left — prey should ease right, no discrete flee.
	d = compute_chase_decision(
		_scene(400, 600, 550, 600, heading=0.0, speed=900.0),
		cfg.chase,
		cfg.camera.width_mm,
		cfg.camera.height_mm,
	)
	assert d.enable_motion
	assert not d.use_planned_flee
	assert d.reason in ("nudge_away", "press")
	assert d.target_vx_mm_s > 0
	assert abs(d.target_vx_mm_s) <= cfg.chase.max_engage_speed_mm_s + 1


def test_far_reels_back_to_keep_hunt_alive():
	cfg = _cfg()
	# Gap >> preferred — prey should move toward ferret (negative x here).
	d = compute_chase_decision(
		_scene(400, 600, 1400, 600, heading=0.0, speed=100.0),
		cfg.chase,
		cfg.camera.width_mm,
		cfg.camera.height_mm,
	)
	assert d.reason == "reel_in"
	assert d.target_vx_mm_s < 0
	# Why: a crawl looked parked once the toy sat outside the gold ring.
	assert d.target_vx_mm_s <= -180.0


def test_rail_edge_reels_in_instead_of_parking():
	# Why: wall push used to cancel reel-in at x_max so the hunt froze.
	from chase.bounds import ArenaBounds, fit_chase_policy

	cfg = _cfg()
	box = ArenaBounds(70.0, 738.0, 70.0, 808.0)
	fitted = fit_chase_policy(cfg.chase, box)
	d = compute_chase_decision(
		_scene(400, 440, 738, 440, heading=0.0, speed=100.0),
		fitted,
		box.width_mm,
		box.height_mm,
		box,
	)
	assert d.reason == "reel_in"
	assert d.enable_motion
	assert d.target_vx_mm_s < -100.0


def test_short_travel_does_not_pin_x_to_fov_center():
	# Why: FOV walls + firmware x_max made chase command +x forever (Y-only motion).
	from chase.bounds import ArenaBounds, fit_chase_policy

	cfg = _cfg()
	box = ArenaBounds(0.0, 300.0, 0.0, 200.0)
	fitted = fit_chase_policy(cfg.chase, box)
	assert fitted.preferred_gap_mm < cfg.chase.preferred_gap_mm
	assert fitted.wall_margin_mm < 280.0
	d = compute_chase_decision(
		_scene(1500, 100, 300, 100, heading=0.0, speed=100.0),
		fitted,
		box.width_mm,
		box.height_mm,
		box,
	)
	assert d.enable_motion
	assert d.target_vx_mm_s <= 0.0


def test_lure_reels_in_slowly():
	from dataclasses import replace

	cfg = replace(_cfg().chase, lure_speed_mm_s=80.0)
	d = compute_chase_decision(
		_scene(400, 600, 1400, 600, heading=0.0, speed=0.0),
		cfg,
		1987.0,
		1242.0,
	)
	assert d.reason == "reel_in"
	assert d.target_vx_mm_s < 0
	assert d.target_vx_mm_s >= -80.0


def test_lure_waits_until_mini_moves():
	from dataclasses import replace

	cfg = replace(_cfg().chase, lure_speed_mm_s=80.0)
	# Inside the ring, Mini still — hold/creep, do not flee.
	d = compute_chase_decision(
		_scene(400, 600, 700, 600, heading=0.0, speed=0.0),
		cfg,
		1987.0,
		1242.0,
	)
	assert d.reason == "wait_hunter"
	assert d.target_vx_mm_s <= 0.0
	assert abs(d.target_vx_mm_s) <= 40.0


def test_lure_opens_gap_when_ace_would_merge():
	# Why: wait/creep on a close pair merges the blobs and freezes the hunt.
	from dataclasses import replace

	from chase.config import ACE_SEP_MM

	cfg = replace(
		_cfg().chase, lure_speed_mm_s=80.0, min_gap_mm=ACE_SEP_MM, ace_sep_mm=ACE_SEP_MM
	)
	d = compute_chase_decision(
		_scene(400, 600, 500, 600, heading=0.0, speed=0.0),
		cfg,
		1987.0,
		1242.0,
	)
	assert d.reason == "lead_away"
	assert d.target_vx_mm_s > 0


def test_lure_leads_slowly_when_mini_closes():
	from dataclasses import replace

	cfg = replace(_cfg().chase, lure_speed_mm_s=80.0)
	# Ferret heading +x toward prey at 700 — Mini is responding.
	d = compute_chase_decision(
		_scene(400, 600, 700, 600, heading=0.0, speed=200.0),
		cfg,
		1987.0,
		1242.0,
	)
	assert d.reason == "lead_away"
	assert d.target_vx_mm_s > 0
	assert d.target_vx_mm_s <= 70.0


def test_corner_pushes_inward():
	cfg = _cfg()
	d = compute_chase_decision(
		_scene(400, 400, 40, 40, heading=225.0, speed=200.0),
		cfg.chase,
		cfg.camera.width_mm,
		cfg.camera.height_mm,
	)
	assert d.wall_push > 0.3
	assert d.target_vx_mm_s > 0
	assert d.target_vy_mm_s > 0
	# Why: far + corner is reel-in first so the hunt does not freeze on a wall.
	assert d.reason in ("edge_dodge", "reel_in")
