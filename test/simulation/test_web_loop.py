"""Web loop must yield for pointer WS instead of 1 ms serial catch-up."""

from simulation.engine import HuntSim, loop_timing


class _Hw:
	backend = "hardware"


def test_loop_timing_hardware_is_chase_rate() -> None:
	# Why: 1 ms catch-up blocked the websocket behind X-MCC RTTs.
	assert loop_timing(_Hw()) == (0.020, 0.016, 0.005)


def test_web_app_autostarts_trial() -> None:
	# Why: warmup left the X-MCC idle; Ace and pointer hunts both auto-start.
	from simulation.web.app import create_app

	app = create_app()
	assert app.state.sim.trial.value == "running"
	app.state.sim.exp.shutdown()


def test_loop_timing_sim_keeps_1ms_physics() -> None:
	step_s, send_every, idle_s = loop_timing(HuntSim().gantry)
	assert step_s == 0.001
	assert send_every == 0.016
	assert idle_s == 0.0
