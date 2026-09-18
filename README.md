# gantry-obstacle-sim

Timed hunt simulation of the [pylon-track](https://github.com/codeathon/pylon-track) hunt, with the 1D ODrive chain replaced by a **Zaber XY** carriage.

Simulation code lives in `src/simulation/` so this repo can also hold the real gantry stack later. Imported from [prairie-live#13](https://github.com/codeathon/prairie-live/pull/13).

The ferret is **your mouse pointer**. The prey toy is the gantry, commanded through the same `move_absolute` / `move_velocity` / `stop` shapes as [Zaber Motion Library](https://software.zaber.com/motion-library/api/py). The camera path uses pylon-track’s Basler ace 2 numbers (not the ferret_behavior 7-cam mocap stack).

## What is timed

| Stage | Source | Default |
|---|---|---|
| Sensor | a2A1920-160umPRO, Mono8 1920×1200, 1.2 m, 4 mm, GSD 1.035 mm/px | FOV 1987 × 1242 mm |
| Exposure | `camera_config.json` | 3000 µs |
| Frame rate | pylon-track | 200 fps |
| USB3 transfer | model of 1920×1200 Mono8 | 1.5 ms |
| Tracking | MOG2 + associator budget | 1.2 ms |
| Chase loop | `ChaseController` | 50 Hz (20 ms) |
| Zaber RTT | X-MCC USB CDC | 4 ms |
| Soft keep-away | preferred gap / max engage speed | ~420 mm / ≤480 mm/s |
| Wall margin | edge dodge band | 280 mm |

The grey ghost on the arena is the ferret pose the chase loop has actually received (mid-exposure sample + USB + track). Prey XY is the **encoder** (Zaber `get_position`), as on a gantry.

Chase policy is a **soft keep-away**: hold ~420 mm from the ferret, nudge slightly when pressed, reel back in when too far (so the hunt stays alive), and steer inward near edges/corners. Continuous `move_velocity` only — no discrete flees.

## Run

```bash
pip install -e ".[dev]"
PYTHONPATH=src python -m simulation.web
```

Open http://127.0.0.1:8765 — **S** start trial, **E** end, **R** reset.

```bash
PYTHONPATH=src pytest
```
