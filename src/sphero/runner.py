"""BLE seek on its own thread. Why: roll must not sit on ace-zaber."""

from __future__ import annotations

import threading

from sphero.seek import seek_command
from vision.tracking_frame import TrackingFrame


class SpheroRunner:
	def __init__(
		self,
		toy: object | None = None,
		period_s: float = 0.08,
		factory=None,
	) -> None:
		self._toy = toy
		self._factory = factory
		self._period_s = period_s
		self._lock = threading.Lock()
		self._scene: TrackingFrame | None = None
		self._stop = threading.Event()
		self._thread: threading.Thread | None = None
		# Why: same mapped gantry window; Mini pose is arena mm.
		self._bounds = None
		self._wall_margin_mm = 0.0

	def set_travel(self, bounds, wall_margin_mm: float) -> None:
		# Why: apply FOV/rail box before the first roll so it cannot leave.
		self._bounds = bounds
		self._wall_margin_mm = float(wall_margin_mm)

	def start(self) -> None:
		if self._thread is not None:
			return
		self._stop.clear()
		if self._toy is not None:
			connect = getattr(self._toy, "connect", None)
			if callable(connect) and not getattr(self._toy, "connected", True):
				connect()
		self._thread = threading.Thread(
			target=self._run, name="sphero-seek", daemon=True
		)
		self._thread.start()

	def stop(self) -> None:
		self._stop.set()
		if self._thread is not None:
			self._thread.join(timeout=2.0)
			self._thread = None
		stop = getattr(self._toy, "stop", None)
		if callable(stop):
			stop()
		close = getattr(self._toy, "close", None)
		if callable(close):
			close()

	def offer(self, scene: TrackingFrame) -> None:
		# Why: chase_feed only swaps a pointer; BLE work stays on sphero-seek.
		with self._lock:
			self._scene = scene

	def _run(self) -> None:
		# Why: find_toy uses asyncio.run; this thread has no uvicorn loop.
		if self._toy is None and self._factory is not None:
			self._toy = self._factory()
		while not self._stop.is_set():
			self._tick()
			if self._stop.wait(self._period_s):
				break

	def _tick(self) -> None:
		with self._lock:
			scene = self._scene
		if scene is None or self._toy is None:
			return
		cmd = seek_command(
			scene.ferret,
			scene.prey,
			scene.trial_phase,
			bounds=self._bounds,
			wall_margin_mm=self._wall_margin_mm,
		)
		if cmd is None:
			self._toy.stop()
			return
		self._toy.roll(cmd[0], cmd[1], duration=max(self._period_s, 0.5))
