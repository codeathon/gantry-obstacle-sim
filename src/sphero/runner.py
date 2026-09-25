"""BLE seek on its own thread. Why: roll must not sit on ace-zaber."""

from __future__ import annotations

import threading

from sphero.seek import seek_command
from vision.tracking_frame import TrackingFrame


class SpheroRunner:
	def __init__(self, toy: object, period_s: float = 0.08) -> None:
		self._toy = toy
		self._period_s = period_s
		self._lock = threading.Lock()
		self._scene: TrackingFrame | None = None
		self._stop = threading.Event()
		self._thread: threading.Thread | None = None

	def start(self) -> None:
		if self._thread is not None:
			return
		self._stop.clear()
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
		while not self._stop.is_set():
			self._tick()
			if self._stop.wait(self._period_s):
				break

	def _tick(self) -> None:
		with self._lock:
			scene = self._scene
		if scene is None:
			return
		cmd = seek_command(scene.ferret, scene.prey, scene.trial_phase)
		if cmd is None:
			self._toy.stop()
			return
		self._toy.roll(cmd[0], cmd[1], duration=max(self._period_s, 0.5))
