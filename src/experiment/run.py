"""Full hunt entry. Why: pylon-track arena_experiment analogue."""

from __future__ import annotations

from basler.camera import AceCamera
from experiment.orchestrator import Experiment
from simulation.config import load_sim_config
from zaber.factory import open_gantry


def main() -> Experiment:
	# Why: same factory as HuntSim so PREY_ZABER can drive the toy.
	gantry = open_gantry(load_sim_config())
	exp = Experiment(gantry, AceCamera())
	exp.run(cycles=1)
	return exp


if __name__ == "__main__":
	main()
