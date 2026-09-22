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
