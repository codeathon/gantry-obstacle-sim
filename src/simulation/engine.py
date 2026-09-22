"""Real-time hunt world: mouse ferret, delayed pylon grab, Zaber XY prey."""

from __future__ import annotations

import math
import time
from dataclasses import asdict, dataclass

from basler.pylon import want_ace
from experiment.orchestrator import Experiment
from simulation.config import SimConfig, load_sim_config
from simulation.pylon_sim import SimulatedPylonCamera
from vision.ground_calib import GroundCam, ground_cam_for_serial
from vision.pipeline import TrackingPipeline
from vision.tracking_frame import TrackState, TrialPhase
from zaber.arena_map import gantry_to_arena, scale_vel, travel_box
from zaber.factory import open_gantry


@dataclass
class Pointer:
	x_mm: float
	y_mm: float


def loop_timing(gantry) -> tuple[float, float, float]:
	# Why: hardware serial must not run 1 ms catch-up on the websocket thread.
	if getattr(gantry, "backend", "") == "hardware":
		return 0.020, 0.016, 0.005
	return 0.001, 0.016, 0.0


def _select_camera(cam):
	# Why: live Ace blob drives chase when PREY_ACE finds a device; else pointer delay model.
	if not want_ace():
		return SimulatedPylonCamera(cam)
	from basler.factory import open_grabber

	grabber = open_grabber()
	if getattr(grabber, "backend", "") == "pylon":
		return grabber
	close = getattr(grabber, "close", None)
	if callable(close):
		close()
	return SimulatedPylonCamera(cam)


class HuntSim:
	def __init__(
		self,
		cfg: SimConfig | None = None,
		grabber: object | None = None,
		gantry: object | None = None,
	) -> None:
		self.cfg = cfg or load_sim_config()
		cam = self.cfg.camera
		self.t_s = 0.0
		self.true_ferret = TrackState(cam.width_mm * 0.25, cam.height_mm * 0.5, 0, 0, True)
		self._prev_fx = self.true_ferret.x_mm
		self._prev_fy = self.true_ferret.y_mm
		self._hud_dirty = False
		self._loop_error = ""
		# Why: SimulatedGantry unless PREY_ZABER / use_hardware finds an X-MCC.
		self.gantry = gantry if gantry is not None else open_gantry(self.cfg)
		self.camera = grabber if grabber is not None else _select_camera(cam)
		self._live_ace = getattr(self.camera, "backend", "") == "pylon"
		if self._live_ace:
			# Why: 1 ms web loop must not block on RetrieveResult(20).
			self.camera.timeout_ms = 0
			self.true_ferret.valid = False
		self.exp = self._bind_experiment(cam)
		self.last_frame_index = -1

	def _bind_experiment(self, cam) -> Experiment:
		# Why: same Experiment chase_feed as hardware; sim only supplies fakes.
		# Cache Charuco — snapshot used to re-read camera_calibration.toml.
		ground = _ground_for_camera(self.camera)
		self._ground = ground
		gsd = ground.gsd_mm_per_px if ground else cam.gsd_mm_per_px
		width_mm = ground.width_mm if ground else cam.width_mm
		height_mm = ground.height_mm if ground else cam.height_mm
		exp = Experiment(
			self.gantry,
			self.camera,
			cfg=self.cfg.chase,
			width_mm=width_mm,
			height_mm=height_mm,
			period_ms=self.cfg.control_period_ms,
			stale_ms=self.cfg.stale_frame_ms,
			pipeline=TrackingPipeline(gsd, cam.frame_rate_fps, ground=ground),
		)
		exp.start()
		return exp

	@property
	def controller(self):
		return self.exp.chase

	@property
	def trial(self) -> TrialPhase:
		return self.exp.trial.phase

	@trial.setter
	def trial(self, phase: TrialPhase) -> None:
		self.exp.trial.phase = phase

	@property
	def _direct_pointer_chase(self) -> bool:
		# Why: hardware + pointer: skip Ace delay; chase sees mouse mm immediately.
		return (not self._live_ace) and getattr(self.gantry, "backend", "") == "hardware"

	def set_pointer(self, x_mm: float, y_mm: float) -> None:
		# Why: pointer is only the animal when no live Ace is grabbing Mono8.
		if self._live_ace:
			return
		cam = self.cfg.camera
		self.true_ferret.x_mm = min(max(x_mm, 0.0), cam.width_mm)
		self.true_ferret.y_mm = min(max(y_mm, 0.0), cam.height_mm)
		self._hud_dirty = True

	def set_trial(self, cmd: str) -> None:
		if cmd == "start":
			self.exp.on_operator_key("s")
		elif cmd == "end":
			self.exp.on_operator_key("e")
			self.gantry.stop()
		elif cmd == "reset":
			self.exp.on_operator_key("r")
			self.gantry.home()

	def step(self, dt_s: float) -> None:
		if not self._live_ace:
			self._update_ferret_kinematics(dt_s)
		self.t_s += dt_s
		# Why: firmware integrates; SimulatedGantry.step is the trapezoid stand-in.
		step_g = getattr(self.gantry, "step", None)
		if callable(step_g):
			step_g(dt_s, self.t_s)
		if self._direct_pointer_chase:
			scene = self.exp.feed_ferret_mm(self.true_ferret, time.time())
			self.last_frame_index = scene.frame_index
			return
		tick = getattr(self.camera, "tick", None)
		if callable(tick):
			tick(self.t_s, self.true_ferret)
		# Why: live Ace timestamps are wall clock; sim t_s would never stale-stop.
		scene = self.exp.chase_feed_loop(None if self._live_ace else self.t_s)
		if scene is not None:
			self.last_frame_index = scene.frame_index
			if self._live_ace:
				self._adopt_ace_ferret(scene)

	def snapshot(self) -> dict:
		# Why split: HUD payload is large; keep each builder under 45 lines.
		frame = self.controller._latest
		seen = frame.ferret if frame else TrackState()
		cam = self.cfg.camera
		return {
			"t_s": self.t_s,
			"trial": self.trial.value,
			"arena": self._arena_snapshot(cam),
			"ferret_source": "ace" if self._live_ace else "pointer",
			"animal": self.exp.sphero_status(),
			"ferret_true": _track_dict(self.true_ferret),
			"ferret_camera": _track_dict(self._to_arena_track(seen)),
			"prey": _track_dict(self._prey_track()),
			"camera": self._camera_dict(cam),
			"zaber": self._zaber_dict(),
			"decision": self._decision_dict(),
			"scene": _scene_dict(frame, self.last_frame_index),
			"control_hz": 1000.0 / self.cfg.control_period_ms,
			"policy": self._policy_dict(),
		}

	def _camera_dict(self, cam) -> dict:
		grab = self.camera
		return {
			"model": str(getattr(grab, "model", cam.model)),
			"backend": str(getattr(grab, "backend", "sim")),
			"fps": cam.frame_rate_fps,
			"exposure_us": cam.exposure_us,
			"usb_transfer_ms": cam.usb_transfer_ms,
			"tracking_pipeline_ms": cam.tracking_pipeline_ms,
			"grab_to_host_ms": cam.grab_to_host_s * 1e3,
			"grab_to_track_ms": cam.grab_to_track_s * 1e3,
			"last_grab_to_frame_ms": float(getattr(grab, "last_grab_to_frame_ms", 0.0)),
			"delivered": int(getattr(grab, "delivered", 0)),
			"dropped": int(getattr(grab, "dropped", 0)),
			"strategy": str(getattr(grab, "GrabStrategy", "LatestImageOnly")),
			"pixel_format": str(getattr(grab, "PixelFormat", "Mono8")),
		}

	def _arena_snapshot(self, cam) -> dict:
		ground = self._ground
		if ground is not None:
			return {
				"width_mm": ground.width_mm,
				"height_mm": ground.height_mm,
				"width_px": ground.width_px,
				"height_px": ground.height_px,
				"gsd_mm_per_px": ground.gsd_mm_per_px,
			}
		fov_fn = getattr(self.camera, "fov", None)
		if callable(fov_fn):
			fov = fov_fn()
			return {
				"width_mm": fov.width_mm,
				"height_mm": fov.height_mm,
				"width_px": fov.width_px,
				"height_px": fov.height_px,
				"gsd_mm_per_px": fov.gsd_mm_per_px,
			}
		return _arena_dict(cam)

	def _adopt_ace_ferret(self, scene) -> None:
		# Why: HUD gold ferret is the Ace blob, not a leftover pointer spawn.
		seen = scene.ferret
		if not seen.valid:
			# Why: toy-only frames must clear a previous ghost ferret on the HUD.
			self.true_ferret = TrackState()
			return
		self.true_ferret = TrackState(
			seen.x_mm,
			seen.y_mm,
			seen.speed_mm_s,
			seen.direction_deg,
			True,
			seen.x_px,
			seen.y_px,
		)

	def _zaber_dict(self) -> dict:
		ex, ey, evx, evy = self._cached_encoder()
		px, py, vx, vy = self._encoder_to_arena(ex, ey, evx, evy)
		spd = math.hypot(vx, vy)
		heading = math.degrees(math.atan2(-vy, vx)) if spd > 1 else 0.0
		return {
			"comm": self.cfg.zaber.comm,
			"backend": getattr(self.gantry, "backend", "sim"),
			"rtt_ms": float(getattr(self.gantry, "last_rtt_ms", 0.0)),
			"busy": self.gantry.is_busy(),
			"x_mm": px,
			"y_mm": py,
			"enc_x_mm": ex,
			"enc_y_mm": ey,
			"vx_mm_s": vx,
			"vy_mm_s": vy,
			"speed_mm_s": spd,
			"heading_deg": heading,
			"max_speed_mm_s": self.cfg.zaber.max_speed_mm_s,
			"max_accel_mm_s2": self.cfg.zaber.max_accel_mm_s2,
			"loop_error": self._loop_error,
			**self._travel_dict(),
			"api_calls": _api_call_dicts(self.gantry),
		}

	def _travel_dict(self) -> dict:
		# Why: HUD box is the mapped window (full FOV); enc_* is firmware travel.
		cam = self.cfg.camera
		box = travel_box(self.gantry, cam.width_mm, cam.height_mm)
		return {
			"x_min": 0.0,
			"x_max": cam.width_mm,
			"y_min": 0.0,
			"y_max": cam.height_mm,
			"enc_x_min": box.x_min,
			"enc_x_max": box.x_max,
			"enc_y_min": box.y_min,
			"enc_y_max": box.y_max,
		}

	def _decision_dict(self) -> dict:
		d = self.controller.last_decision
		return {
			"reason": d.reason,
			"threat": d.threat,
			"dist_threat": d.dist_threat,
			"wall_push": d.wall_push,
			"approach_threat": d.approach_threat,
			"gap_error_mm": d.gap_error_mm,
			"enable_motion": d.enable_motion,
			"use_planned_flee": False,
			"vx_mm_s": d.target_vx_mm_s,
			"vy_mm_s": d.target_vy_mm_s,
			"flee_direction_deg": d.flee_direction_deg,
			"compute_ms": self.controller.last_decision_ms,
			"stale_stops": self.controller.stale_stops,
		}

	def _cached_encoder(self) -> tuple[float, float, float, float]:
		# Why: chase_feed already polled; HUD must not add another serial RTT.
		peek_xy = getattr(self.gantry, "peek_xy", None)
		peek_v = getattr(self.gantry, "peek_velocity", None)
		if callable(peek_xy) and callable(peek_v):
			ex, ey = peek_xy()
			evx, evy = peek_v()
			return ex, ey, evx, evy
		ex, ey = self.gantry.get_xy()
		evx, evy = self.gantry.get_velocity()
		return ex, ey, evx, evy

	def _prey_track(self) -> TrackState:
		ex, ey, evx, evy = self._cached_encoder()
		x, y, vx, vy = self._encoder_to_arena(ex, ey, evx, evy)
		spd = math.hypot(vx, vy)
		heading = math.degrees(math.atan2(-vy, vx)) if spd > 1 else 0.0
		return TrackState(x, y, spd, heading, True)

	def _encoder_to_arena(
		self, x: float, y: float, vx: float, vy: float
	) -> tuple[float, float, float, float]:
		cam = self.cfg.camera
		box = travel_box(self.gantry, cam.width_mm, cam.height_mm)
		ax, ay = gantry_to_arena(x, y, box, cam.width_mm, cam.height_mm)
		avx, avy = scale_vel(vx, vy, box, cam.width_mm, cam.height_mm, to_arena=True)
		return ax, ay, avx, avy

	def _to_arena_track(self, t: TrackState) -> TrackState:
		if not t.valid:
			return t
		cam = self.cfg.camera
		box = travel_box(self.gantry, cam.width_mm, cam.height_mm)
		x, y = gantry_to_arena(t.x_mm, t.y_mm, box, cam.width_mm, cam.height_mm)
		return TrackState(x, y, t.speed_mm_s, t.direction_deg, True, t.x_px, t.y_px)

	def _policy_dict(self) -> dict:
		pol = asdict(self.controller._cfg or self.cfg.chase)
		cam = self.cfg.camera
		box = travel_box(self.gantry, cam.width_mm, cam.height_mm)
		s = 0.5 * (cam.width_mm / box.width_mm + cam.height_mm / box.height_mm)
		if s <= 1.01:
			return pol
		# Why: rings are drawn in FOV mm; chase gaps stay in rail mm.
		for key in (
			"preferred_gap_mm",
			"min_gap_mm",
			"max_pull_mm",
			"wall_margin_mm",
			"threat_distance_mm",
			"creep_distance_mm",
		):
			pol[key] = float(pol[key]) * s
		return pol

	def _update_ferret_kinematics(self, dt_s: float) -> None:
		dx = self.true_ferret.x_mm - self._prev_fx
		dy = self.true_ferret.y_mm - self._prev_fy
		if dt_s > 1e-6:
			self.true_ferret.speed_mm_s = math.hypot(dx, dy) / dt_s
			if self.true_ferret.speed_mm_s > 5.0:
				self.true_ferret.direction_deg = math.degrees(math.atan2(-dy, dx))
		self._prev_fx = self.true_ferret.x_mm
		self._prev_fy = self.true_ferret.y_mm


def _arena_dict(cam) -> dict:
	return {
		"width_mm": cam.width_mm,
		"height_mm": cam.height_mm,
		"width_px": cam.width_px,
		"height_px": cam.height_px,
		"gsd_mm_per_px": cam.gsd_mm_per_px,
	}


def _scene_dict(frame, frame_index: int) -> dict:
	return {
		"distance_mm": frame.distance_mm if frame else -1,
		"bearing_deg": frame.bearing_deg if frame else 0,
		"closing_speed_mm_s": frame.closing_speed_mm_s if frame else 0,
		"frame_index": frame_index,
		"ferret_confidence": frame.quality.ferret_confidence if frame else 0.0,
	}


def _track_dict(t: TrackState) -> dict:
	return {
		"x_mm": t.x_mm,
		"y_mm": t.y_mm,
		"x_px": t.x_px,
		"y_px": t.y_px,
		"speed_mm_s": t.speed_mm_s,
		"direction_deg": t.direction_deg,
		"valid": t.valid,
	}


def _ground_for_camera(camera) -> GroundCam | None:
	# Why: only the live Ace serial (or PYLON_SERIAL on a pylon grabber).
	serial = str(getattr(camera, "serial", "") or "")
	if not serial and getattr(camera, "backend", "") == "pylon":
		import os

		serial = os.environ.get("PYLON_SERIAL") or os.environ.get("PYLON_CAMERA") or ""
	return ground_cam_for_serial(serial)


def _api_call_dicts(gantry) -> list[dict]:
	# Why: stub calls are names; sim/hardware expose ApiCall rows via api_log.
	log = getattr(gantry, "api_log", None)
	if callable(log):
		return [asdict(c) for c in log()]
	return []
