"""Firmware travel stretches onto the Ace FOV canvas."""

from chase.bounds import ArenaBounds
from simulation.engine import HuntSim
from zaber.arena_map import arena_to_gantry, gantry_to_arena, travel_box
from zaber.client import ZaberGantry
from zaber.motion import HardwareSettings


def test_identity_when_travel_matches_fov() -> None:
	box = ArenaBounds(0.0, 1987.0, 0.0, 1242.0)
	assert gantry_to_arena(100.0, 50.0, box, 1987.0, 1242.0) == (100.0, 50.0)
	assert arena_to_gantry(100.0, 50.0, box, 1987.0, 1242.0) == (100.0, 50.0)


def test_gantry_midpoint_maps_to_fov_center() -> None:
	box = ArenaBounds(0.0, 300.0, 0.0, 200.0)
	x, y = gantry_to_arena(150.0, 100.0, box, 1987.0, 1242.0)
	assert abs(x - 993.5) < 1e-6
	assert abs(y - 621.0) < 1e-6
	rx, ry = arena_to_gantry(x, y, box, 1987.0, 1242.0)
	assert abs(rx - 150.0) < 1e-6
	assert abs(ry - 100.0) < 1e-6


def test_huntsim_scales_short_travel_to_full_arena() -> None:
	# Why: the teal rail window should fill the simulation canvas.
	class _Ax:
		def __init__(self, pos: float) -> None:
			self.pos = pos
			self.vel = 0.0
			self.homed = True

		def get_position(self, unit=None):
			return self.pos

		def home(self) -> None:
			self.pos = 0.0

		def is_homed(self) -> bool:
			return True

		def move_absolute(self, position, unit=None, **kwargs) -> None:
			self.pos = float(position)

		def move_velocity(self, velocity, unit=None, **kwargs) -> None:
			self.vel = float(velocity)

		def stop(self, wait_until_idle: bool = True) -> None:
			del wait_until_idle
			self.vel = 0.0

	g = ZaberGantry(
		HardwareSettings(
			home_x_mm=150.0,
			home_y_mm=100.0,
			x_max=300.0,
			y_max=200.0,
			poll_min_s=0.0,
		),
		x_axis=_Ax(150.0),
		y_axis=_Ax(100.0),
	)
	sim = HuntSim(gantry=g)
	box = travel_box(g, sim.cfg.camera.width_mm, sim.cfg.camera.height_mm)
	assert box.x_max == 300.0
	snap = sim.snapshot()
	prey = snap["prey"]
	z = snap["zaber"]
	assert abs(prey["x_mm"] - sim.cfg.camera.width_mm * 0.5) < 1.0
	assert abs(z["enc_x_mm"] - 150.0) < 1e-6
	assert z["x_max"] == sim.cfg.camera.width_mm
