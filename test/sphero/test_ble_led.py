"""Edu set_main_led wants a Color, not three ints."""

from sphero.ble_hw import BleSphero


class _Api:
	def __init__(self) -> None:
		self.got = None

	def set_main_led(self, color) -> None:
		# Why: matches spherov2 SpheroEduAPI — one Color argument.
		if isinstance(color, tuple):
			raise TypeError("takes 2 positional arguments but 4 were given")
		self.got = color


def test_set_led_passes_one_color() -> None:
	api = _Api()
	BleSphero(api).set_led(0, 180, 80)
	assert api.got is not None
	assert getattr(api.got, "r", None) == 0
	assert getattr(api.got, "g", None) == 180
	assert getattr(api.got, "b", None) == 80
