"""Edu roll(heading, speed, duration) — duration is required on the lab wheel."""

from sphero.ble_hw import BleSphero


class _Api:
	def __init__(self) -> None:
		self.args = None

	def roll(self, heading, speed, duration) -> None:
		self.args = (heading, speed, duration)


def test_stop_swallows_dead_gatt() -> None:
	class _Dead:
		def stop_roll(self) -> None:
			raise TimeoutError()

	BleSphero(_Dead()).stop()


def test_roll_sends_heading_speed_duration() -> None:
	api = _Api()
	BleSphero(api).roll(80.0, 90.0, duration=1.5)
	assert api.args == (90, 80, 1.5)
