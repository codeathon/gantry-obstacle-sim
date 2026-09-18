"""Full hunt entry. Why: pylon-track arena_experiment analogue."""

from __future__ import annotations

from basler.camera import AceCamera
from experiment.orchestrator import Experiment
from zaber.factory import open_gantry


def main() -> Experiment:
	# Why: open_gantry + AceCamera + Experiment.run; only place that binds both.
	gantry = open_gantry(None)
	exp = Experiment(gantry, AceCamera())
	exp.run(cycles=1)
	return exp


if __name__ == "__main__":
	main()
