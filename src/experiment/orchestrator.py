"""Binds Basler + Zaber. Why: chase_feed overwrites prey with encoder XY."""

from __future__ import annotations

from chase.controller import ChaseController
from experiment.trial import TrialStateMachine
from zaber.protocol import Gantry
from basler.protocol import AceGrabber


class Experiment:
	def __init__(self, gantry: Gantry, grabber: AceGrabber) -> None:
		self._gantry = gantry
		self._grabber = grabber
		self._trial = TrialStateMachine()
		self._chase = ChaseController(gantry, cfg=None)

	def run(self) -> None:
		# Why: start grab, chase thread, operator thread; join on shutdown.
		raise NotImplementedError("full arena_experiment run")

	def chase_feed_loop(self) -> None:
		# Why: copy TrackingFrame, set prey from gantry.get_xy(), submit_frame.
		# Do not use vision for prey XY.
		raise NotImplementedError("get_frame → encoder prey → submit_frame")

	def shutdown(self) -> None:
		# Why: stop chase, gantry.stop(), stop grabbing, then join threads.
		raise NotImplementedError("ordered shutdown")
