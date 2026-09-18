"""Binds Basler + Zaber. Why: chase_feed overwrites prey with encoder XY."""

from __future__ import annotations

from chase.controller import ChaseController
from experiment.trial import TrialStateMachine
from vision.pipeline import TrackingPipeline
from vision.tracking_frame import TrackingFrame
from zaber.protocol import Gantry
from basler.protocol import AceGrabber


class Experiment:
	def __init__(self, gantry: Gantry, grabber: AceGrabber) -> None:
		self._gantry = gantry
		self._grabber = grabber
		self._trial = TrialStateMachine()
		self._chase = ChaseController(gantry, cfg=None)
		self._pipeline = TrackingPipeline()
		self._running = False
		self.last_scene: TrackingFrame | None = None

	def start(self) -> None:
		# Why: open serial + Ace, then LatestImageOnly, matching phase_configuring.
		self._gantry.connect()
		self._gantry.home()
		self._grabber.open()
		self._grabber.configure()
		self._grabber.start_grabbing()
		self._running = True

	def run(self, cycles: int = 1) -> None:
		# Why: dry in-process cycle — no chase/operator threads until hardware.
		self.start()
		try:
			for _ in range(cycles):
				self.chase_feed_loop()
		finally:
			self.shutdown()

	def chase_feed_loop(self, t_s: float | None = None) -> TrackingFrame | None:
		# Why: copy TrackingFrame, set prey from gantry.get_xy(), submit_frame.
		# Do not use vision for prey XY.
		cam_frame = self._grabber.retrieve_frame()
		if cam_frame is None:
			return None
		scene = self._pipeline.process(cam_frame, self._trial.phase)
		self._stamp_encoder_prey(scene)
		self._chase.submit_frame(scene)
		poll_t = t_s if t_s is not None else cam_frame.host_time_ns * 1e-9
		self._chase.poll(poll_t)
		self.last_scene = scene
		return scene

	def on_operator_key(self, key: str) -> None:
		self._trial.on_operator_key(key)

	def shutdown(self) -> None:
		# Why: stop chase, gantry.stop(), stop grabbing, then join threads.
		self._running = False
		self._gantry.stop()
		self._grabber.close()
		self._gantry.close()

	def _stamp_encoder_prey(self, scene: TrackingFrame) -> None:
		x_mm, y_mm = self._gantry.get_xy()
		vx, vy = self._gantry.get_velocity()
		scene.prey.x_mm = x_mm
		scene.prey.y_mm = y_mm
		scene.prey.speed_mm_s = (vx * vx + vy * vy) ** 0.5
		scene.prey.valid = True
