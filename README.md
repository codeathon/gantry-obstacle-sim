# gantry-obstacle-sim

Timed hunt simulation of the [pylon-track](https://github.com/codeathon/pylon-track) hunt, with the 1D ODrive chain replaced by a **Zaber XY** carriage.

Simulation code lives in `src/simulation/` so this repo can also hold the real gantry stack later. Imported from [prairie-live#13](https://github.com/codeathon/prairie-live/pull/13).

The ferret is **your mouse pointer**. The prey toy is the gantry, commanded through the same `move_absolute` / `move_velocity` / `stop` shapes as [Zaber Motion Library](https://software.zaber.com/motion-library/api/py). The camera path uses pylon-track’s Basler ace 2 numbers (not the ferret_behavior 7-cam mocap stack).

## What is timed

| Stage | Source | Default |
|---|---|---|
| Sensor | a2A1920-160umPRO, Mono8 1920×1200, 1.2 m, 4 mm, GSD 1.035 mm/px | FOV 1987 × 1242 mm |
| Exposure | `config/camera_config.json` (pylon-track) | 3000 µs |
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

## Real Zaber X-MCC

The web hunt still drives the **ferret** from the mouse pointer (delayed Ace grab model). The **toy** is commanded through `ZaberGantry` (`move_velocity` / `home` / encoder `get_xy`). A live Basler Ace still needs an animal in the FOV, so the camera path stays simulated until then.

| How to enable | What happens |
|---|---|
| `PREY_ZABER=1` or `ZABER_PORT=/dev/ttyUSB0` or `config/sim.json` `zaber.use_hardware` | Open USB CDC, `detect_devices`, optional lockstep X |
| Missing `zaber-motion` wheel or unplugged X-MCC | Fall back to `SimulatedGantry` (web hunt still runs) |
| `PREY_ZABER_REQUIRE=1` | Raise instead of falling back |

```bash
pip install -e ".[zaber]"
PREY_ZABER=1 PYTHONPATH=src python -m simulation.web
```

Optional JSON keys under `zaber`: `port`, `device_index`, `x_axis` (1), `y_axis` (2), `lockstep_group` (0 = no lockstep), `poll_min_ms` (encoder cache so the 1 ms sim loop does not hammer serial).

## Basler Ace 2 (pylon-track)

GenICam AOI, exposure, gain, and fps are copied from [pylon-track `camera_config.json`](https://github.com/codeathon/pylon-track/blob/main/src/camera/camera_config.json) into `config/camera_config.json`. Hunt sim FOV is that AOI × GSD (`ferret_tracker.h`: 1.035 mm/px at 1.2 m, 4 mm). C++ `CameraSettings` struct defaults (1920×960 crop, 5000 µs) stay as dataclass defaults; `AceCamera()` and `load_sim_config()` load the JSON.

Override the JSON with `PYLON_CAMERA_CONFIG` / `PREY_CAMERA_CONFIG`. A live Ace still needs an animal in the FOV — this repo still uses the delayed pixel model until then.

To grab real Mono8 frames (mouse or ferret in the arena):

```bash
pip install -e ".[pylon]"
PREY_ACE=1 PYTHONPATH=src python -m experiment.grab_frames --count 16 --out captures
```

`EnumerateDevices` + `StartGrabbing(LatestImageOnly)` + `RetrieveResult`. FOV is the live `Width`/`Height` × GSD (written to `captures/fov.json`). Missing pypylon or unplugged Ace falls back to the stub unless `PREY_ACE_REQUIRE=1`. Optional `PYLON_SERIAL` selects the camera.
