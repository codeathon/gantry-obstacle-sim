"""Full hunt entry. Why: pylon-track arena_experiment analogue."""

from __future__ import annotations

import argparse

from basler.factory import open_grabber
from experiment.orchestrator import Experiment
from simulation.config import load_sim_config
from vision.pipeline import TrackingPipeline
from zaber.factory import open_gantry


def main(argv: list[str] | None = None) -> Experiment:
	args = _parse(argv if argv is not None else ["--cycles", "1"])
	cfg = load_sim_config()
	gantry = open_gantry(cfg)
	grabber = open_grabber()
	exp = Experiment(
		gantry,
		grabber,
		cfg=cfg.chase,
		width_mm=cfg.camera.width_mm,
		height_mm=cfg.camera.height_mm,
		period_ms=cfg.control_period_ms,
		stale_ms=cfg.stale_frame_ms,
		pipeline=TrackingPipeline(cfg.camera.gsd_mm_per_px, cfg.camera.frame_rate_fps),
	)
	if args.live:
		# Why: LatestImageOnly retrieve → detect mouse → 50 Hz move_velocity.
		exp.run_live(duration_s=args.duration)
	else:
		exp.run(cycles=args.cycles)
	return exp


def _parse(argv: list[str]) -> argparse.Namespace:
	p = argparse.ArgumentParser(description="Prey gantry hunt (Ace + Zaber)")
	p.add_argument("--live", action="store_true")
	p.add_argument("--duration", type=float, default=0.0)
	p.add_argument("--cycles", type=int, default=1)
	return p.parse_args(argv)


if __name__ == "__main__":
	import sys

	main(sys.argv[1:])
