"""demo_roll drives the stub without BLE so CI stays offline."""

from sphero.client import SpheroStub
from sphero.demo_roll import _drive_square


def test_drive_square_issues_four_rolls() -> None:
	toy = SpheroStub()
	toy.connect()
	_drive_square(toy, seconds=0.0, speed=50.0)
	assert toy.calls.count("roll") == 4
	assert toy.calls.count("stop") == 4
	assert abs(toy.heading_deg - 270.0) < 1e-6
