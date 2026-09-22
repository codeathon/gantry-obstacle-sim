"""Sphero Mini stand-in ferret. Why: keep BLE out of Ace/Zaber; gate with PREY_ANIMAL."""

from sphero.animal import animal_name, want_sphero
from sphero.factory import open_sphero
from sphero.seek import seek_command

__all__ = ["animal_name", "open_sphero", "seek_command", "want_sphero"]
