"""Binds Basler + Zaber. Why: chase_feed overwrites prey with encoder XY."""

from __future__ import annotations

import math
import time

from basler.protocol import AceGrabber
from chase.controller import ChaseController
from chase.policy import fill_tracking_derived
from experiment.trial import TrialStateMachine
from vision.pipeline import TrackingPipeline
from vision.tracking_frame import TrackingFrame
from zaber.protocol import Gantry


class Experiment:
	def __init__(
		self,
		gantry: Gantry,
		grabber: AceGrabber,
		*,
		cfg: object = None,
		width_mm: float = 1987.0,
		height_mm: float = 1242.0,
		period_ms: int = 20,
		stale_ms: float = 80.0,
		pipeline: TrackingPipeline | None = None,
	) -> None:
		self._gantry = gantry
		self._grabber = grabber
		self.trial = TrialStateMachine()
		self.chase = ChaseController(
			gantry, cfg, width_mm, height_mm, period_ms, stale_ms
		)
		self._pipeline = pipeline or TrackingPipeline()
		self._running = False
		self.last_scene: TrackingFrame | None = None

	def start(self) -> None:
		# Why: open serial + Ace, then LatestImageOnly, matching phase_configuring.
		self._gantry.connect()
		self._gantry.home()
		self._grabber.open()
		self._grabber.configure()
		self._apply_live_fov()
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
		# Do not use vision for prey XY. Always poll so 50 Hz runs without a grab.
		cam_frame = self._grabber.retrieve_frame()
		delivered = self._ingest_camera(cam_frame)
		# Why: encoder is live; refresh toy XY even when the Ace has no new frame.
		if self.last_scene is not None:
			self._stamp_encoder_prey(self.last_scene)
		self.chase.poll(self._poll_time(t_s, cam_frame))
		return delivered

	def on_operator_key(self, key: str) -> None:
		self.trial.on_operator_key(key)

	def shutdown(self) -> None:
		# Why: stop chase, gantry.stop(), stop grabbing, then join threads.
		self._running = False
		self._gantry.stop()
		self._grabber.close()
		self._gantry.close()

	def _ingest_camera(self, cam_frame) -> TrackingFrame | None:
		if cam_frame is None:
			return None
		prey_xy = self._gantry.get_xy()
		scene = self._pipeline.process(cam_frame, self.trial.phase, prey_xy)
		self._stamp_encoder_prey(scene)
		self.chase.submit_frame(scene)
		self.last_scene = scene
		return scene

	def run_live(self, duration_s: float = 0.0, auto_start: bool = True) -> None:
		# Why: pylon-track chase_feed is a tight loop, not a disk dump.
		self.start()
		if auto_start:
			self.trial.on_operator_key("s")
		t0 = time.perf_counter()
		try:
			self._live_loop(duration_s, t0)
		finally:
			self.shutdown()

	def _live_loop(self, duration_s: float, t0: float) -> None:
		# Why: 5 ms yield is pylon-track kMainLoopSleepMs; LatestImageOnly still wins.
		last = t0
		while self._running:
			now = time.perf_counter()
			if duration_s > 0 and now - t0 >= duration_s:
				return
			self._step_sim_gantry(now - last, now - t0)
			last = now
			self.chase_feed_loop()
			time.sleep(0.005)

	def _step_sim_gantry(self, dt_s: float, t_s: float) -> None:
		# Why: firmware integrates; SimulatedGantry still needs wall-clock steps.
		step = getattr(self._gantry, "step", None)
		if callable(step):
			step(dt_s, t_s)

	def _apply_live_fov(self) -> None:
		fov_fn = getattr(self._grabber, "fov", None)
		if not callable(fov_fn):
			return
		fov = fov_fn()
		self.chase.set_workspace(fov.width_mm, fov.height_mm)

	def _poll_time(self, t_s: float | None, cam_frame) -> float:
		if t_s is not None:
			return t_s
		if cam_frame is not None:
			return cam_frame.host_time_ns * 1e-9
		return time.time_ns() * 1e-9

	def _stamp_encoder_prey(self, scene: TrackingFrame) -> None:
		x_mm, y_mm = self._gantry.get_xy()
		vx, vy = self._gantry.get_velocity()
		spd = math.hypot(vx, vy)
		scene.prey.x_mm = x_mm
		scene.prey.y_mm = y_mm
		scene.prey.speed_mm_s = spd
		scene.prey.direction_deg = math.degrees(math.atan2(-vy, vx)) if spd > 1 else 0.0
		scene.prey.valid = True
		# Why: encoder prey is trusted; camera prey_confidence is not used for the toy.
		scene.quality.prey_confidence = 1.0
		fill_tracking_derived(scene)
