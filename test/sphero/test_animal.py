"""PREY_ANIMAL selects ferret vs Sphero without deleting src/sphero/."""

from sphero.animal import animal_name, want_sphero


def test_default_animal_is_ferret(monkeypatch) -> None:
	monkeypatch.delenv("PREY_ANIMAL", raising=False)
	assert animal_name() == "ferret"
	assert not want_sphero()


def test_prey_animal_sphero(monkeypatch) -> None:
	monkeypatch.setenv("PREY_ANIMAL", "sphero")
	assert animal_name() == "sphero"
	assert want_sphero()


def test_prey_animal_ferret(monkeypatch) -> None:
	monkeypatch.setenv("PREY_ANIMAL", "ferret")
	assert animal_name() == "ferret"
	assert not want_sphero()
