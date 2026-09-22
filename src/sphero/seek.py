"""Arena mm → Mini roll. Why: Ace ferret + encoder prey already share last_scene."""

from __future__ import annotations

import math

from vision.tracking_frame import TrackState, TrialPhase


def seek_command(
	ferret: TrackState,
	prey: TrackState,
	phase: TrialPhase = TrialPhase.running,
	*,
	max_speed: float = 180.0,
	aim_offset_deg: float = 0.0,
	arrive_mm: float = 40.0,
) -> tuple[float, float] | None:
	# Why: None means stop — invalid Ace or idle trial must not keep rolling.
	if phase != TrialPhase.running or not ferret.valid or not prey.valid:
		return None
	dx = prey.x_mm - ferret.x_mm
	dy = prey.y_mm - ferret.y_mm
	dist = math.hypot(dx, dy)
	# Why: fill_tracking_derived uses 0=right, 90=up (Y flipped).
	heading = math.degrees(math.atan2(-dy, dx)) + aim_offset_deg
	heading = heading % 360.0
	if dist <= arrive_mm:
		return 0.0, heading
	return max_speed, heading
