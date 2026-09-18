"""In-memory ZaberGantry records motion-library-shaped calls."""

from zaber.client import ZaberGantry
from zaber.factory import open_gantry
from zaber.workspace import clip_xy, point_in_workspace


def test_connect_home_move_and_encoder() -> None:
	g = ZaberGantry()
	g.connect()
	g.home()
	g.move_absolute(100.0, 50.0, wait_until_idle=False)
	assert g.get_xy() == (100.0, 50.0)
	g.move_velocity(12.0, -3.0)
	assert g.get_velocity() == (12.0, -3.0)
	g.stop()
	assert g.get_velocity() == (0.0, 0.0)
	g.close()
	assert g.calls == [
		"connect",
		"home",
		"move_absolute",
		"move_velocity",
		"stop",
		"close",
	]


def test_open_gantry_returns_connected_stub() -> None:
	g = open_gantry(None)
	assert g.get_xy() == (0.0, 0.0)
	g.close()


def test_clip_xy_and_membership() -> None:
	assert clip_xy(-10, 500, 0, 100, 0, 200) == (0.0, 200.0)
	assert point_in_workspace(10, 10, 0, 100, 0, 100)
	assert not point_in_workspace(101, 10, 0, 100, 0, 100)
