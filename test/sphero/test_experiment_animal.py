"""Experiment starts the Mini only when PREY_ANIMAL=sphero."""

from __future__ import annotations

import time

from basler.camera import AceCamera
from experiment.orchestrator import Experiment
from sphero.client import SpheroStub
from vision.tracking_frame import TrackState
from zaber.client import ZaberGantry


def test_ferret_mode_does_not_connect_sphero(monkeypatch) -> None:
	monkeypatch.setenv("PREY_ANIMAL", "ferret")
	exp = Experiment(ZaberGantry(), AceCamera())
	exp.start()
	exp.chase_feed_loop()
	exp.shutdown()
	assert exp._sphero_runner is None
	assert exp._sphero is None
	assert exp.sphero_status() == {"animal": "ferret", "backend": "off"}


def test_sphero_factory_opens_off_start_thread(monkeypatch) -> None:
	# Why: HuntSim starts on uvicorn; find_toy must not use that loop.
	import threading

	seen: list[str] = []

	def factory():
		seen.append(threading.current_thread().name)
		toy = SpheroStub()
		toy.connect()
		return toy

	monkeypatch.setenv("PREY_ANIMAL", "sphero")
	monkeypatch.setattr("sphero.factory.open_sphero", factory)
	exp = Experiment(ZaberGantry(), AceCamera())
	exp.start()
	deadline = time.perf_counter() + 0.5
	while not seen and time.perf_counter() < deadline:
		time.sleep(0.005)
	exp.shutdown()
	assert seen == ["sphero-seek"]


def test_sphero_mode_enables_mini_lure(monkeypatch) -> None:
	from simulation.config import load_sim_config

	monkeypatch.setenv("PREY_ANIMAL", "sphero")
	exp = Experiment(
		ZaberGantry(), AceCamera(), cfg=load_sim_config().chase, sphero=SpheroStub()
	)
	exp.start()
	lure = exp.chase._cfg.lure_speed_mm_s
	exp.shutdown()
	assert lure == 80.0


def test_sphero_mode_offers_scene(monkeypatch) -> None:
	monkeypatch.setenv("PREY_ANIMAL", "sphero")
	toy = SpheroStub()
	gantry = ZaberGantry()
	exp = Experiment(gantry, AceCamera(), sphero=toy)
	exp.start()
	gantry.move_absolute(200.0, 0.0)
	exp.on_operator_key("s")
	# Why: pointer hybrid still stamps encoder prey; Ace ferret may be empty.
	exp.feed_ferret_mm(TrackState(0.0, 0.0, valid=True))
	deadline = time.perf_counter() + 0.5
	while "roll" not in toy.calls and time.perf_counter() < deadline:
		time.sleep(0.005)
	status = exp.sphero_status()
	exp.shutdown()
	assert status["animal"] == "sphero"
	assert "roll" in toy.calls
	assert toy.roll_thread == "sphero-seek"
