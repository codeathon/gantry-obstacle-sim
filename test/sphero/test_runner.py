"""SpheroRunner rolls on sphero-seek, not the caller thread."""

from __future__ import annotations

import time

from sphero.client import SpheroStub
from sphero.runner import SpheroRunner
from vision.tracking_frame import TrackingFrame, TrackState, TrialPhase


def test_offer_rolls_on_seek_thread() -> None:
	toy = SpheroStub()
	runner = SpheroRunner(toy, period_s=0.01)
	runner.start()
	scene = TrackingFrame(
		ferret=TrackState(0.0, 0.0, valid=True),
		prey=TrackState(200.0, 0.0, valid=True),
		trial_phase=TrialPhase.running,
	)
	runner.offer(scene)
	deadline = time.perf_counter() + 0.5
	while "roll" not in toy.calls and time.perf_counter() < deadline:
		time.sleep(0.005)
	speed, heading, thread = toy.speed, toy.heading_deg, toy.roll_thread
	runner.stop()
	assert "roll" in toy.calls
	assert thread == "sphero-seek"
	assert speed == 180.0
	assert abs(heading - 0.0) < 1.0


def test_invalid_ferret_stops() -> None:
	toy = SpheroStub()
	runner = SpheroRunner(toy, period_s=0.01)
	runner.start()
	runner.offer(
		TrackingFrame(
			ferret=TrackState(valid=False),
			prey=TrackState(1.0, 1.0, valid=True),
			trial_phase=TrialPhase.running,
		)
	)
	deadline = time.perf_counter() + 0.5
	while "stop" not in toy.calls and time.perf_counter() < deadline:
		time.sleep(0.005)
	runner.stop()
	assert "roll" not in toy.calls
