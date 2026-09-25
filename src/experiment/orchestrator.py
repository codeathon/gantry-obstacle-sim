"""Binds Basler + Zaber. Why: chase_feed overwrites prey with encoder XY."""

from __future__ import annotations

import copy
import math
import sys
import time

from basler.protocol import AceGrabber
from chase.controller import ChaseController
from chase.policy import fill_tracking_derived
from experiment.trial import TrialStateMachine
from vision.pipeline import TrackingPipeline
from vision.tracking_frame import TrackingFrame, TrackState
from zaber.arena_map import arena_to_gantry, gantry_to_arena, scale_vel, travel_box
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
		sphero: object | None = None,
	) -> None:
		self._gantry = gantry
		self._grabber = grabber
		self.trial = TrialStateMachine()
		self.chase = ChaseController(
			gantry, cfg, width_mm, height_mm, period_ms, stale_ms
		)
		self._pipeline = pipeline or TrackingPipeline()
		self._running = False
		self._fov_w = width_mm
		self._fov_h = height_mm
		self.last_scene: TrackingFrame | None = None
		# Why: injected stub in tests; factory runs only when PREY_ANIMAL=sphero.
		self._sphero = sphero
		self._sphero_runner = None

	def start(self) -> None:
		# Why: open serial + Ace, then LatestImageOnly, matching phase_configuring.
		self._gantry.connect()
		self._gantry.home()
		self._grabber.open()
		self._grabber.configure()
		self._apply_live_fov()
		# Why: FOV is ferret space; prey keep-away must use X-MCC travel.
		self._apply_gantry_travel()
		self._grabber.start_grabbing()
		self._start_animal()
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
			if cam_frame is None:
				# Why: timeout=0 empty retrieves are not a dead camera; 80 ms
				# stale-stop used to freeze the toy between Ace frames.
				self.last_scene.host_time_ns = time.time_ns()
			self._stamp_encoder_prey(self.last_scene, arena=True)
			self._submit_chase(self.last_scene)
			self._offer_animal(self.last_scene)
		self.chase.poll(self._poll_time(t_s, cam_frame))
		return delivered

	def feed_ferret_mm(self, ferret: TrackState, t_s: float | None = None) -> TrackingFrame:
		# Why: pointer hybrid must not wait SimulatedPylon exposure/USB delay.
		if t_s is None:
			now_ns = time.time_ns()
			now_s = now_ns * 1e-9
		else:
			now_s = t_s
			now_ns = int(t_s * 1e9)
		scene = TrackingFrame(
			frame_index=(self.last_scene.frame_index + 1) if self.last_scene else 1,
			host_time_ns=now_ns,
			ferret=TrackState(
				ferret.x_mm,
				ferret.y_mm,
				ferret.speed_mm_s,
				ferret.direction_deg,
				True,
				ferret.x_px,
				ferret.y_px,
			),
			trial_phase=self.trial.phase,
		)
		scene.quality.ferret_confidence = 1.0
		self._stamp_encoder_prey(scene, arena=True)
		self._submit_chase(scene)
		self._offer_animal(scene)
		self.last_scene = scene
		self.chase.poll(now_s)
		return scene

	def on_operator_key(self, key: str) -> None:
		self.trial.on_operator_key(key)

	def shutdown(self) -> None:
		# Why: stop chase, gantry.stop(), stop grabbing, then join threads.
		self._running = False
		self._stop_animal()
		self._gantry.stop()
		self._grabber.close()
		self._gantry.close()

	def _start_animal(self) -> None:
		from sphero.animal import want_sphero
		from sphero.factory import open_sphero
		from sphero.runner import SpheroRunner

		if not want_sphero():
			return
		self._enable_mini_lure()
		# Why: uvicorn already has an event loop; Bleak asyncio.run() must not run here.
		if self._sphero is not None:
			self._sphero_runner = SpheroRunner(self._sphero)
		else:
			self._sphero_runner = SpheroRunner(factory=open_sphero)
		# Why: Mini rolls free; pin it to the same mapped travel the gantry uses.
		self._apply_mini_travel()
		self._sphero_runner.start()

	def _apply_mini_travel(self) -> None:
		if self._sphero_runner is None:
			return
		from chase.bounds import ArenaBounds, fit_chase_policy
		from chase.config import ChasePolicyConfig

		# Mapped gantry travel is the FOV rectangle Mini already lives in.
		box = ArenaBounds(0.0, self._fov_w, 0.0, self._fov_h)
		src = self.chase._cfg_src
		if isinstance(src, ChasePolicyConfig):
			margin = fit_chase_policy(src, box).wall_margin_mm
		else:
			margin = min(280.0, min(box.width_mm, box.height_mm) * 0.18)
		self._sphero_runner.set_travel(box, margin)

	def _enable_mini_lure(self) -> None:
		# Why: Mini GATT cannot follow a 480 mm/s keep-away; wait in the ring.
		from dataclasses import replace

		from chase.config import ChasePolicyConfig

		cfg = self.chase._cfg_src
		if not isinstance(cfg, ChasePolicyConfig):
			return
		self.chase._cfg_src = replace(cfg, lure_speed_mm_s=80.0)
		self.chase._refit()

	def _stop_animal(self) -> None:
		if self._sphero_runner is not None:
			self._sphero_runner.stop()
			self._sphero_runner = None

	def _offer_animal(self, scene: TrackingFrame) -> None:
		# Why: non-blocking pointer swap; BLE roll is on sphero-seek.
		if self._sphero_runner is None:
			return
		self._sphero_runner.offer(scene)

	def sphero_status(self) -> dict:
		from sphero.animal import animal_name

		backend = "off"
		toy = self._sphero
		if self._sphero_runner is not None:
			toy = getattr(self._sphero_runner, "_toy", None) or toy
		if toy is not None:
			backend = str(getattr(toy, "backend", "stub"))
		return {"animal": animal_name(), "backend": backend}

	def _ingest_camera(self, cam_frame) -> TrackingFrame | None:
		if cam_frame is None:
			return None
		# Why: AnimalDetector does mm/GSD; raw rail mm is not Ace pixels.
		scene = self._pipeline.process(
			cam_frame, self.trial.phase, self._prey_arena_xy()
		)
		self._stamp_encoder_prey(scene, arena=True)
		self._submit_chase(scene)
		self.last_scene = scene
		return scene

	def _prey_arena_xy(self) -> tuple[float, float]:
		box = travel_box(self._gantry, self._fov_w, self._fov_h)
		return gantry_to_arena(*self._gantry.get_xy(), box, self._fov_w, self._fov_h)

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
		ground = getattr(self._pipeline, "_ground", None)
		if ground is not None:
			# Why: Charuco footprint is the arena, not a2A1920 Width×1.035.
			self._fov_w = ground.width_mm
			self._fov_h = ground.height_mm
			self.chase.set_workspace(ground.width_mm, ground.height_mm)
			return
		fov_fn = getattr(self._grabber, "fov", None)
		if not callable(fov_fn):
			return
		fov = fov_fn()
		self._fov_w = fov.width_mm
		self._fov_h = fov.height_mm
		self.chase.set_workspace(fov.width_mm, fov.height_mm)

	def _apply_gantry_travel(self) -> None:
		if getattr(self._gantry, "backend", "") != "hardware":
			return
		s = getattr(self._gantry, "settings", None)
		if s is None:
			return
		self.chase.set_travel(
			float(getattr(s, "x_min", 0.0)),
			float(getattr(s, "x_max", self.chase._w)),
			float(getattr(s, "y_min", 0.0)),
			float(getattr(s, "y_max", self.chase._h)),
		)
		print(
			f"Zaber travel {s.x_min:.1f}–{s.x_max:.1f} × {s.y_min:.1f}–{s.y_max:.1f} mm",
			file=sys.stderr,
		)

	def _poll_time(self, t_s: float | None, cam_frame) -> float:
		if t_s is not None:
			return t_s
		if cam_frame is not None:
			return cam_frame.host_time_ns * 1e-9
		return time.time_ns() * 1e-9

	def _stamp_encoder_prey(self, scene: TrackingFrame, *, arena: bool = False) -> None:
		x_mm, y_mm = self._gantry.get_xy()
		vx, vy = self._gantry.get_velocity()
		if arena:
			box = travel_box(self._gantry, self._fov_w, self._fov_h)
			x_mm, y_mm = gantry_to_arena(x_mm, y_mm, box, self._fov_w, self._fov_h)
			vx, vy = scale_vel(vx, vy, box, self._fov_w, self._fov_h, to_arena=True)
		spd = math.hypot(vx, vy)
		scene.prey.x_mm = x_mm
		scene.prey.y_mm = y_mm
		scene.prey.speed_mm_s = spd
		scene.prey.direction_deg = math.degrees(math.atan2(-vy, vx)) if spd > 1 else 0.0
		scene.prey.valid = True
		# Why: encoder prey is trusted; camera prey_confidence is not used for the toy.
		scene.quality.prey_confidence = 1.0
		fill_tracking_derived(scene)

	def _submit_chase(self, hud: TrackingFrame) -> None:
		# Why: chase stays in rail mm; HUD last_scene stays in FOV mm.
		chase = copy.deepcopy(hud)
		chase.ferret = self._ferret_to_gantry(hud.ferret)
		self._stamp_encoder_prey(chase, arena=False)
		self.chase.submit_frame(chase)

	def _ferret_to_gantry(self, ferret: TrackState) -> TrackState:
		box = travel_box(self._gantry, self._fov_w, self._fov_h)
		x_mm, y_mm = arena_to_gantry(
			ferret.x_mm, ferret.y_mm, box, self._fov_w, self._fov_h
		)
		return TrackState(
			x_mm,
			y_mm,
			ferret.speed_mm_s,
			ferret.direction_deg,
			ferret.valid,
			ferret.x_px,
			ferret.y_px,
		)
