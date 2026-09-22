"""Ace+Zaber chase on its own thread.

Why: the web HUD used to call HuntSim.step on the websocket loop. Closing
the browser stopped the hunt; JSON send added latency to RetrieveResult and
move_velocity. This runner is the same path as experiment.run_live.
"""

from __future__ import annotations

import queue
import threading

from simulation.engine import HuntSim, loop_timing


class PipelineRunner:
	"""Only this thread may touch the grabber or the gantry."""

	def __init__(self, sim: HuntSim) -> None:
		self._sim = sim
		self._hud: dict = {}
		self._lock = threading.Lock()
		self._stop = threading.Event()
		self._cmds: queue.SimpleQueue = queue.SimpleQueue()
		self._watchers = 0
		self._thread: threading.Thread | None = None

	def start(self) -> None:
		if self._thread is not None:
			return
		self._stop.clear()
		self._thread = threading.Thread(
			target=self._run, name="ace-zaber", daemon=True
		)
		self._thread.start()

	def stop(self) -> None:
		self._stop.set()
		if self._thread is None:
			return
		self._thread.join(timeout=2.0)
		self._thread = None

	def watch(self, delta: int) -> None:
		# Why: no browser → skip snapshot so HUD on/off matches run_live.
		with self._lock:
			self._watchers = max(0, self._watchers + delta)

	def hud(self) -> dict:
		with self._lock:
			return self._hud

	def post(self, msg: dict) -> None:
		self._cmds.put(msg)

	def _run(self) -> None:
		step_s, _, idle_s = loop_timing(self._sim.gantry)
		# Why: hardware yield is run_live's 5 ms; sim keeps 1 ms physics.
		period = idle_s if idle_s > 0 else step_s
		while not self._stop.is_set():
			self._tick(step_s)
			if self._stop.wait(period):
				break

	def _tick(self, step_s: float) -> None:
		self._drain()
		try:
			self._sim.step(step_s)
		except Exception as exc:
			# Why: one BADDATA used to cancel the hunt loop with no traceback.
			self._sim._loop_error = str(exc)
		with self._lock:
			watch = self._watchers
		if watch:
			self._publish()

	def _publish(self) -> None:
		snap = self._sim.snapshot()
		with self._lock:
			self._hud = snap

	def _drain(self) -> None:
		while True:
			try:
				msg = self._cmds.get_nowait()
			except queue.Empty:
				return
			apply_client(self._sim, msg)


def apply_client(sim: HuntSim, msg: dict) -> None:
	# Why: pointer/trial must run on the ace-zaber thread (zaber_motion).
	kind = msg.get("type")
	if kind == "pointer":
		sim.set_pointer(float(msg["x_mm"]), float(msg["y_mm"]))
	elif kind == "trial":
		sim.set_trial(str(msg.get("cmd", "")))
