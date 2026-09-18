"""Hunt sim: ferret from Basler pixels, toy from Zaber encoder."""

from chase.controller import ChaseController
from simulation.engine import HuntSim
from vision.tracking_frame import TrialPhase
from zaber.factory import open_gantry


def test_camera_ferret_lags_pointer_in_mm() -> None:
	sim = HuntSim()
	sim.trial = TrialPhase.running
	for _ in range(12):
		sim.step(0.001)
	spawn_x = sim.true_ferret.x_mm
	assert sim.controller._latest is not None
	sim.set_pointer(100.0, 100.0)
	for _ in range(3):
		sim.step(0.001)
	assert abs(sim.controller._latest.ferret.x_mm - spawn_x) < 2.0
	for _ in range(20):
		sim.step(0.001)
	assert abs(sim.controller._latest.ferret.x_mm - 100.0) < 1.0


def test_chase_ferret_is_camera_pixels_times_gsd() -> None:
	sim = HuntSim()
	for _ in range(20):
		sim.step(0.001)
	seen = sim.controller._latest.ferret
	gsd = sim.cfg.camera.gsd_mm_per_px
	assert seen.valid
	assert abs(seen.x_mm - seen.x_px * gsd) < 1e-6
	assert abs(seen.y_mm - seen.y_px * gsd) < 1e-6


def test_toy_pose_is_zaber_encoder() -> None:
	sim = HuntSim()
	sim.trial = TrialPhase.running
	sim.set_pointer(sim.gantry.x_mm - 80.0, sim.gantry.y_mm)
	for _ in range(80):
		sim.step(0.001)
	frame = sim.controller._latest
	x_mm, y_mm = sim.gantry.get_xy()
	assert abs(frame.prey.x_mm - x_mm) < 0.05
	assert abs(frame.prey.y_mm - y_mm) < 0.05
	assert frame.prey.valid
	assert any(c.name == "move_velocity" for c in sim.gantry.calls)


def test_reset_places_toy_via_zaber_home() -> None:
	sim = HuntSim()
	sim.gantry.move_absolute(40.0, 50.0)
	sim.gantry.step(0.01, 0.01)
	sim.set_trial("reset")
	assert abs(sim.gantry.x_mm - sim.cfg.zaber.home_x_mm) < 0.1
	assert abs(sim.gantry.y_mm - sim.cfg.zaber.home_y_mm) < 0.1
	assert any(c.name == "home" for c in sim.gantry.calls)


def test_shared_chase_controller_and_fake_gantry() -> None:
	sim = HuntSim()
	assert isinstance(sim.controller, ChaseController)
	g = open_gantry(sim.cfg)
	assert g.get_xy() == (sim.cfg.zaber.home_x_mm, sim.cfg.zaber.home_y_mm)
	g.close()


def test_huntsim_toy_backend_is_sim_by_default() -> None:
	# Why: no X-MCC in CI; ferret stays on the delayed camera path either way.
	sim = HuntSim()
	assert sim.gantry.backend == "sim"
	snap = sim.snapshot()
	assert snap["zaber"]["backend"] == "sim"
	assert any(c["name"] == "home" for c in snap["zaber"]["api_calls"])


def test_huntsim_falls_back_when_prey_zaber_set(monkeypatch) -> None:
	# Why: web hunt must still run if the toy stage is unplugged.
	monkeypatch.setenv("PREY_ZABER", "1")
	sim = HuntSim()
	assert sim.gantry.backend == "sim"
