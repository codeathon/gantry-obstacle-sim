"""Live hunt entry. Why: not a frame dump — chase_feed like pylon-track."""

from __future__ import annotations

from experiment.run import main as run_main


def main(argv: list[str] | None = None) -> object:
	# Why: PREY_ACE + PREY_ZABER drive retrieve → detect → move_velocity.
	extra = ["--live"]
	if argv:
		extra.extend(argv)
	return run_main(extra)


if __name__ == "__main__":
	import sys

	main(sys.argv[1:])
