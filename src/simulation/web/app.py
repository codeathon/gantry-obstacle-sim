"""FastAPI spectator HUD. Why: Ace+Zaber run on PipelineRunner, not this loop."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from simulation.engine import HuntSim, loop_timing
from simulation.pipeline_runner import PipelineRunner

STATIC = Path(__file__).resolve().parent / "static"


@asynccontextmanager
async def _lifespan(app: FastAPI):
	try:
		yield
	finally:
		shutdown_app(app)


def create_app() -> FastAPI:
	app = FastAPI(title="Prey gantry hunt sim", lifespan=_lifespan)
	sim = HuntSim()
	# Why: warmup idles chase; Ace blob and pointer hunts must start without S.
	sim.set_trial("start")
	runner = PipelineRunner(sim)
	runner.start()
	app.state.sim = sim
	app.state.runner = runner
	app.mount("/static", StaticFiles(directory=STATIC), name="static")

	@app.get("/")
	async def index() -> FileResponse:
		return FileResponse(STATIC / "index.html")

	@app.websocket("/ws")
	async def ws_endpoint(ws: WebSocket) -> None:
		await ws.accept()
		await _hud_session(ws, runner)

	return app


def shutdown_app(app: FastAPI) -> None:
	# Why: stop ace-zaber before closing the serial port / pylon grabber.
	runner = getattr(app.state, "runner", None)
	if runner is not None:
		runner.stop()
		app.state.runner = None
	sim = getattr(app.state, "sim", None)
	if sim is not None:
		sim.exp.shutdown()


async def _hud_session(ws: WebSocket, runner: PipelineRunner) -> None:
	# Why: subscribe only copies last chase state; disconnect must not stop hunt.
	runner.watch(1)
	task = asyncio.create_task(_hud_loop(ws, runner))
	try:
		while True:
			msg = await ws.receive_json()
			runner.post(msg)
	except WebSocketDisconnect:
		pass
	finally:
		task.cancel()
		runner.watch(-1)


async def _hud_loop(ws: WebSocket, runner: PipelineRunner) -> None:
	_, send_every, _ = loop_timing(runner._sim.gantry)
	while True:
		await asyncio.sleep(send_every)
		snap = runner.hud()
		if snap:
			await ws.send_json(snap)


def main() -> None:
	import uvicorn

	uvicorn.run(
		"simulation.web.app:create_app",
		factory=True,
		host="0.0.0.0",
		port=8765,
		reload=False,
	)


if __name__ == "__main__":
	main()
