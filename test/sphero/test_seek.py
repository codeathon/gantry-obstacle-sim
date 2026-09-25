"""Seek heading uses Ace ferret + encoder prey in arena mm."""

from sphero.seek import seek_command
from vision.tracking_frame import TrackState, TrialPhase


def test_rolls_right_toward_prey() -> None:
	cmd = seek_command(
		TrackState(0.0, 0.0, valid=True),
		TrackState(200.0, 0.0, valid=True),
	)
	assert cmd is not None
	speed, heading = cmd
	assert speed == 180.0
	assert abs(heading - 0.0) < 1.0


def test_rolls_up_toward_prey() -> None:
	# Why: arena +Y is down in image; bearing 90° is up (negative dy).
	cmd = seek_command(
		TrackState(0.0, 100.0, valid=True),
		TrackState(0.0, 0.0, valid=True),
	)
	assert cmd is not None
	assert abs(cmd[1] - 90.0) < 1.0


def test_stops_when_ferret_missing() -> None:
	assert seek_command(TrackState(), TrackState(10.0, 10.0, valid=True)) is None


def test_stops_when_trial_idle() -> None:
	assert (
		seek_command(
			TrackState(0.0, 0.0, valid=True),
			TrackState(200.0, 0.0, valid=True),
			TrialPhase.warmup,
		)
		is None
	)


def test_zero_speed_when_arrived() -> None:
	cmd = seek_command(
		TrackState(10.0, 10.0, valid=True),
		TrackState(12.0, 10.0, valid=True),
		arrive_mm=40.0,
	)
	assert cmd is not None
	assert cmd[0] == 0.0


def _vx(cmd: tuple[float, float]) -> float:
	import math

	return cmd[0] * math.cos(math.radians(cmd[1]))


def test_wall_blocks_roll_out_of_gantry_box() -> None:
	# Why: Mini was rolling into the enclosure; gantry already clips this axis.
	from chase.bounds import ArenaBounds

	box = ArenaBounds(0.0, 200.0, 0.0, 200.0)
	cmd = seek_command(
		TrackState(200.0, 100.0, valid=True),
		TrackState(400.0, 100.0, valid=True),
		bounds=box,
		wall_margin_mm=40.0,
	)
	assert cmd is not None
	assert _vx(cmd) <= 1e-6


def test_outside_wall_rolls_back_in() -> None:
	from chase.bounds import ArenaBounds

	box = ArenaBounds(0.0, 200.0, 0.0, 200.0)
	cmd = seek_command(
		TrackState(250.0, 100.0, valid=True),
		TrackState(400.0, 100.0, valid=True),
		bounds=box,
		wall_margin_mm=40.0,
	)
	assert cmd is not None
	assert _vx(cmd) < 0.0


def test_backs_off_when_ace_would_merge() -> None:
	# Why: Mini parked on the toy deadlocks Ace into one blob.
	cmd = seek_command(
		TrackState(0.0, 0.0, valid=True),
		TrackState(100.0, 0.0, valid=True),
		arrive_mm=250.0,
	)
	assert cmd is not None
	assert cmd[0] == 180.0
	assert abs(cmd[1] - 180.0) < 1.0


def test_open_field_seek_unchanged() -> None:
	from chase.bounds import ArenaBounds

	box = ArenaBounds(0.0, 1000.0, 0.0, 1000.0)
	cmd = seek_command(
		TrackState(500.0, 500.0, valid=True),
		TrackState(700.0, 500.0, valid=True),
		bounds=box,
		wall_margin_mm=40.0,
	)
	assert cmd is not None
	assert cmd[0] == 180.0
	assert abs(cmd[1] - 0.0) < 1.0
