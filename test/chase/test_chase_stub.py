"""Stub chase policy + 50 Hz controller, no real keep-away."""

from chase.controller import ChaseController
from chase.policy import compute_chase_decision
from vision.tracking_frame import TrackingFrame, TrackState, TrialPhase
from zaber.client import ZaberGantry


def test_policy_idles_when_trial_not_running() -> None:
	d = compute_chase_decision(TrackingFrame(), None, 100.0, 100.0)
	assert d.reason == "trial_not_running"
	assert not d.enable_motion


def test_policy_idles_when_tracks_invalid() -> None:
	scene = TrackingFrame(trial_phase=TrialPhase.running)
	d = compute_chase_decision(scene, None, 100.0, 100.0)
	assert d.reason == "tracks_invalid"
	assert not d.enable_motion


def test_policy_stub_idle_when_both_valid() -> None:
	scene = TrackingFrame(
		trial_phase=TrialPhase.running,
		ferret=TrackState(valid=True),
		prey=TrackState(valid=True),
	)
	d = compute_chase_decision(scene, None, 100.0, 100.0)
	assert d.reason == "stub_idle"
	assert not d.enable_motion


def test_stale_frame_stops_gantry() -> None:
	g = ZaberGantry()
	ctrl = ChaseController(g)
	ctrl.submit_frame(TrackingFrame(host_time_ns=0, trial_phase=TrialPhase.running))
	ctrl.poll(1.0)
	assert "stop" in g.calls
	assert ctrl.last_decision.reason == "stale_frame"
	assert ctrl.stale_stops == 1


def test_fresh_invalid_tracks_still_stop() -> None:
	g = ZaberGantry()
	ctrl = ChaseController(g)
	now_ns = 2_000_000_000
	ctrl.submit_frame(TrackingFrame(host_time_ns=now_ns, trial_phase=TrialPhase.running))
	ctrl.poll(now_ns * 1e-9)
	assert "stop" in g.calls
	assert ctrl.last_decision.reason == "tracks_invalid"
	assert "move_velocity" not in g.calls
