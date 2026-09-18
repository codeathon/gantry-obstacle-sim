"""Grab Ace frames to PGM. Why: mouse-in-rig captures without the hunt loop."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from basler.factory import open_grabber
from basler.fov import save_mono8_pgm
from basler.types import CameraFov


def main(argv: list[str] | None = None) -> list[Path]:
	args = _parse(argv)
	out = Path(args.out)
	out.mkdir(parents=True, exist_ok=True)
	cam = open_grabber()
	cam.open()
	cam.configure()
	fov = cam.fov() if hasattr(cam, "fov") else None
	_write_fov(out / "fov.json", fov, getattr(cam, "backend", "stub"))
	cam.start_grabbing()
	try:
		return _save_frames(cam, out, args.count)
	finally:
		cam.close()


def _save_frames(cam, out: Path, count: int) -> list[Path]:
	written: list[Path] = []
	for i in range(count):
		frame = cam.retrieve_frame()
		if frame is None:
			continue
		path = out / f"frame_{frame.frame_index:04d}.pgm"
		save_mono8_pgm(path, frame)
		written.append(path)
	return written


def _write_fov(path: Path, fov: CameraFov | None, backend: str) -> None:
	payload = {"backend": backend}
	if fov is not None:
		payload.update(
			{
				"model": fov.model,
				"width_px": fov.width_px,
				"height_px": fov.height_px,
				"offset_x": fov.offset_x,
				"offset_y": fov.offset_y,
				"gsd_mm_per_px": fov.gsd_mm_per_px,
				"width_mm": fov.width_mm,
				"height_mm": fov.height_mm,
			}
		)
	path.write_text(json.dumps(payload, indent="\t") + "\n", encoding="utf-8")
	print(
		f"{backend} {payload.get('model', '')} "
		f"{payload.get('width_px', 0)}x{payload.get('height_px', 0)} px  "
		f"FOV {payload.get('width_mm', 0):.1f} x {payload.get('height_mm', 0):.1f} mm"
	)


def _parse(argv: list[str] | None) -> argparse.Namespace:
	p = argparse.ArgumentParser(description="Grab Mono8 Ace frames (PGM)")
	p.add_argument("--count", type=int, default=8)
	p.add_argument("--out", default="captures")
	return p.parse_args(argv)


if __name__ == "__main__":
	main()
