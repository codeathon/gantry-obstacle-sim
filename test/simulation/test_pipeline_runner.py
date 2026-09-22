"""PipelineRunner: Ace+Zaber keep stepping when the HUD is idle or slow."""

from __future__ import annotations

import time

from simulation.engine import HuntSim
from simulation.pipeline_runner import PipelineRunner


class _FakeSim:
	"""No pylon/Zaber. Why: isolate the thread contract from HuntSim setup."""

	def __init__(self, backend: str = "sim") -> None:
		self.steps = 0
		self.snaps = 0
		self.gantry = type("G", (), {"backend": backend})()
		self.pointer = None
		self.trials: list[str] = []
		self._loop_error = ""

	def step(self, dt_s: float) -> None:
		del dt_s
		self.steps += 1

	def snapshot(self) -> dict:
		self.snaps += 1
		return {"n": self.steps}

	def set_pointer(self, x_mm: float, y_mm: float) -> None:
		self.pointer = (x_mm, y_mm)

	def set_trial(self, cmd: str) -> None:
		self.trials.append(cmd)


def test_runner_steps_without_a_hud_subscriber() -> None:
	# Why: closing the browser used to cancel chase_feed with the websocket.
	sim = _FakeSim()
	runner = PipelineRunner(sim)
	runner.start()
	time.sleep(0.03)
	runner.stop()
	assert sim.steps > 0
	assert sim.snaps == 0


def test_slow_hud_read_does_not_stop_steps() -> None:
	# Why: send_json used to sit on the same loop as RetrieveResult / move_velocity.
	sim = _FakeSim()
	runner = PipelineRunner(sim)
	runner.start()
	time.sleep(0.02)
	n0 = sim.steps
	time.sleep(0.04)
	n1 = sim.steps
	_ = runner.hud()
	runner.stop()
	assert n1 > n0


def test_watch_publishes_a_copy() -> None:
	sim = _FakeSim()
	runner = PipelineRunner(sim)
	runner.watch(1)
	runner.start()
	time.sleep(0.03)
	snap = runner.hud()
	runner.stop()
	assert sim.snaps > 0
	assert snap["n"] == sim.steps


def test_post_trial_runs_on_the_pipeline() -> None:
	# Why: set_trial calls gantry.stop/home; asyncio must not touch zaber_motion.
	sim = _FakeSim()
	runner = PipelineRunner(sim)
	runner.start()
	runner.post({"type": "trial", "cmd": "end"})
	deadline = time.perf_counter() + 0.5
	while "end" not in sim.trials and time.perf_counter() < deadline:
		time.sleep(0.005)
	runner.stop()
	assert "end" in sim.trials


def test_snapshot_does_not_poll_the_encoder() -> None:
	# Why: HUD get_xy used to add an X-MCC RTT after every chase_feed poll.
	sim = HuntSim()
	try:
		real = sim.gantry.get_xy
		polls = {"n": 0}

		def spy() -> tuple[float, float]:
			polls["n"] += 1
			return real()

		sim.gantry.get_xy = spy
		sim.step(0.001)
		polls["n"] = 0
		snap = sim.snapshot()
		assert polls["n"] == 0
		assert snap["prey"]["valid"]
	finally:
		sim.exp.shutdown()
