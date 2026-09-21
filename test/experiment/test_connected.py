"""Dry-run wiring: Basler + Zaber + vision + chase, no vendor SDKs."""

import sys

from basler.camera import AceCamera
from experiment.camera_preview import main as camera_preview_main
from experiment.orchestrator import Experiment
from experiment.run import main as run_main
from experiment.trial import TrialStateMachine
from vision.tracking_frame import TrackState, TrialPhase
from zaber.client import ZaberGantry


def test_no_vendor_sdks_imported() -> None:
	# Why: stubs must run in this env without pypylon or zaber_motion installed.
	assert "pypylon" not in sys.modules
	assert "zaber_motion" not in sys.modules


def test_trial_ser_keys() -> None:
	fsm = TrialStateMachine()
	assert fsm.phase == TrialPhase.warmup
	assert fsm.on_operator_key("s") == TrialPhase.running
	assert fsm.on_operator_key("e") == TrialPhase.ended
	assert fsm.on_operator_key("r") == TrialPhase.warmup


def test_chase_feed_overwrites_prey_from_encoder() -> None:
	# Why: HuntSim.step / pylon-track chase_feed: prey XY is encoder, not vision.
	gantry = ZaberGantry()
	exp = Experiment(gantry, AceCamera())
	exp.start()
	gantry.move_absolute(111.0, 222.0)
	scene = exp.chase_feed_loop()
	exp.shutdown()
	assert scene is not None
	assert scene.prey.x_mm == 111.0
	assert scene.prey.y_mm == 222.0
	assert scene.prey.valid
	assert not scene.ferret.valid
	assert scene.frame_index == 1


def test_start_applies_gantry_travel_to_chase() -> None:
	# Why: prey walls must be firmware rails, not the Ace FOV rectangle.
	gantry = ZaberGantry()
	gantry.settings.x_min = 0.0
	gantry.settings.x_max = 320.0
	gantry.settings.y_min = 0.0
	gantry.settings.y_max = 210.0
	exp = Experiment(gantry, AceCamera(), cfg=None)
	exp.start()
	b = exp.chase._bounds
	exp.shutdown()
	assert b.x_max == 320.0
	assert b.y_max == 210.0


def test_feed_ferret_mm_bypasses_camera() -> None:
	# Why: pointer hybrid must not wait for SimulatedPylon grab_to_track.
	gantry = ZaberGantry()
	exp = Experiment(gantry, AceCamera())
	exp.start()
	gantry.move_absolute(111.0, 222.0)
	scene = exp.feed_ferret_mm(TrackState(40.0, 50.0, 0, 0, True))
	exp.shutdown()
	assert scene.ferret.x_mm == 40.0
	assert scene.ferret.y_mm == 50.0
	assert scene.prey.x_mm == 111.0
	assert scene.quality.ferret_confidence == 1.0
	assert scene.ferret.valid


def test_operator_start_reaches_tracking_frame() -> None:
	gantry = ZaberGantry()
	exp = Experiment(gantry, AceCamera())
	exp.start()
	exp.on_operator_key("s")
	scene = exp.chase_feed_loop()
	exp.shutdown()
	assert scene is not None
	assert scene.trial_phase == TrialPhase.running


def test_experiment_run_dry_cycle() -> None:
	gantry = ZaberGantry()
	exp = Experiment(gantry, AceCamera())
	exp.run(cycles=2)
	assert exp.last_scene is not None
	assert "connect" in gantry.calls
	assert "home" in gantry.calls
	assert "stop" in gantry.calls
	assert "close" in gantry.calls


def test_camera_preview_has_no_gantry() -> None:
	scene = camera_preview_main()
	assert scene is not None
	assert scene.trial_phase == TrialPhase.warmup
	assert not scene.prey.valid


def test_run_main_binds_both_stacks() -> None:
	exp = run_main()
	assert exp.last_scene is not None
	assert exp.last_scene.prey.valid
