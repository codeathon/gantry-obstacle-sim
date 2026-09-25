"""open_sphero uses a stub unless BLE is required."""

from sphero.client import SpheroStub
from sphero.factory import open_sphero


def test_sphero_stub_env(monkeypatch) -> None:
	monkeypatch.setenv("SPHERO_STUB", "1")
	toy = open_sphero()
	assert isinstance(toy, SpheroStub)
	assert toy.connected


def test_ble_fallback_names_empty_exception(monkeypatch, capsys) -> None:
	# Why: ToyNotFoundError prints as () and looked like a silent die.
	monkeypatch.delenv("SPHERO_STUB", raising=False)
	monkeypatch.delenv("PREY_SPHERO_REQUIRE", raising=False)

	def boom():
		raise RuntimeError()

	monkeypatch.setattr("sphero.ble_hw.connect_ble", boom)
	toy = open_sphero()
	err = capsys.readouterr().err
	assert isinstance(toy, SpheroStub)
	assert "RuntimeError" in err
	assert "SpheroStub" in err
	assert "demo_roll" in err
