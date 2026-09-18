"""Import-only: zaber stubs must load without zaber_motion."""

from zaber.client import ZaberGantry
from zaber.factory import open_gantry
from zaber.protocol import Gantry
from zaber.workspace import clip_xy, point_in_workspace


def test_gantry_protocol_is_importable() -> None:
	assert Gantry is not None
	assert ZaberGantry is not None
	assert open_gantry is not None
	assert clip_xy is not None
	assert point_in_workspace is not None
