"""Trial FSM. Why: s/e/r is orthogonal to tracking — camera keeps grabbing."""

from __future__ import annotations

from vision.tracking_frame import TrialPhase


class TrialStateMachine:
	def __init__(self) -> None:
		self.phase = TrialPhase.warmup

	def on_operator_key(self, key: str) -> TrialPhase:
		# Why: s start, e end, r reset — same keys as the web sim and pylon-track.
		raise NotImplementedError("s/e/r → TrialPhase")
