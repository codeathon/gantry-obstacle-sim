"""open_sphero uses a stub unless BLE is required."""

from sphero.client import SpheroStub
from sphero.factory import open_sphero


def test_sphero_stub_env(monkeypatch) -> None:
	monkeypatch.setenv("SPHERO_STUB", "1")
	toy = open_sphero()
	assert isinstance(toy, SpheroStub)
	assert toy.connected
