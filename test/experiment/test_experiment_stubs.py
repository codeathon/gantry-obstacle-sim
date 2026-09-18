"""Import-only: experiment binds packages without running hardware."""

from chase.controller import ChaseController
from chase.policy import compute_chase_decision
from experiment.camera_preview import main as camera_preview_main
from experiment.orchestrator import Experiment
from experiment.run import main as run_main
from experiment.trial import TrialStateMachine
from vision.pipeline import TrackingPipeline
from vision.tracking_frame import TrackingFrame


def test_experiment_and_chase_stubs_import() -> None:
	assert Experiment is not None
	assert TrialStateMachine is not None
	assert ChaseController is not None
	assert compute_chase_decision is not None
	assert TrackingPipeline is not None
	assert TrackingFrame is not None
	assert camera_preview_main is not None
	assert run_main is not None
