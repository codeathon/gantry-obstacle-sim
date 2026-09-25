# gantry-obstacle-sim

Timed hunt simulation of the [pylon-track](https://github.com/codeathon/pylon-track) hunt, with the 1D ODrive chain replaced by a **Zaber XY** carriage.

Simulation code lives in `src/simulation/` so this repo can also hold the real gantry stack later. Imported from [prairie-live#13](https://github.com/codeathon/prairie-live/pull/13).

The **animal** in the Ace FOV is a real ferret (`PREY_ANIMAL=ferret`, default) or a **Sphero Mini** (`PREY_ANIMAL=sphero`). Ace maps that blob to arena mm; the prey toy stays on the Zaber encoder. The Mini driver lives in `src/sphero/` and stays in the tree — sphero mode only starts the BLE seek thread. Without a camera the animal is **your mouse pointer** (delayed grab model). The camera path uses pylon-track’s Basler ace 2 numbers (not the ferret_behavior 7-cam mocap stack).

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

The grey ghost on the arena is the ferret pose the chase loop has actually received (live Ace centroid, or mid-exposure sample + USB + track when the pointer stands in). Prey XY is the **encoder** (Zaber `get_position`), as on a gantry.

Chase policy is a **soft keep-away**: hold ~420 mm from the ferret, nudge slightly when pressed, reel back in when too far (so the hunt stays alive), and steer inward near edges/corners. Continuous `move_velocity` only — no discrete flees.

## Run

```bash
pip install -e ".[dev]"
PYTHONPATH=src python -m simulation.web
```

Open the HUD (or `xdg-open http://127.0.0.1:8765`) — **S** start trial, **E** end, **R** reset.

```bash
PYTHONPATH=src pytest
```

## Real Zaber X-MCC

The web hunt drives the **ferret** from a live Ace blob when `PREY_ACE=1` opens a camera (`LatestImageOnly` → centroid → `pos_mm = pos_px × GSD`). If the Ace is missing, it falls back to the mouse pointer (delayed grab model). The **toy** is commanded through `ZaberGantry` (`move_velocity` / `home` / encoder `get_xy`).

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

Override the JSON with `PYLON_CAMERA_CONFIG` / `PREY_CAMERA_CONFIG`.

**Live hunt** (mouse or ferret in the Ace FOV) is the pylon-track loop: `LatestImageOnly` grab → blob centroid in pixels (toy discarded using the Zaber encoder) → `pos_mm = pos_px × GSD` → 50 Hz keep-away → `move_velocity` on the gantry.

```bash
pip install -e ".[pylon,zaber]"
PREY_ACE=1 PREY_ZABER=1 PYTHONPATH=src python -m simulation.web
```

Same stack without the HUD: `python -m experiment.run --live`.

Missing Ace/X-MCC falls back to the pointer delay model and `SimulatedGantry` so the loop still runs. `PREY_ACE_REQUIRE=1` / `PREY_ZABER_REQUIRE=1` fail instead. Optional `PYLON_SERIAL` selects the camera.

The HUD at http://127.0.0.1:8765 is a spectator: Ace grab and Zaber `move_velocity` run on their own thread.

## Animal (`PREY_ANIMAL`)

Ace is the animal pose. The encoder is the prey pose. The Mini IMU is not used for XY.

| `PREY_ANIMAL` | What happens |
|---|---|
| `ferret` (default) | Ace blob + keep-away. `src/sphero/` is idle (no BLE). |
| `sphero` | Same Ace + keep-away, plus a `sphero-seek` thread that `roll`s toward the prey. |

```bash
pip install -e ".[pylon,zaber,sphero]"
PREY_ANIMAL=sphero PREY_ACE=1 PREY_ZABER=1 PREY_ZABER_REQUIRE=1 \
  SPHERO_NAME=SM-6399 \
  ZABER_PORT=/dev/ttyUSB0 PYTHONPATH=src python -m simulation.web
xdg-open http://127.0.0.1:8765
```

Real ferret (Sphero code stays, runner does not connect):

```bash
PREY_ANIMAL=ferret PREY_ACE=1 PREY_ZABER=1 PREY_ZABER_REQUIRE=1 \
  ZABER_PORT=/dev/ttyUSB0 PYTHONPATH=src python -m simulation.web
```

Aim the Mini tail LED along arena +X once so heading 0 matches Ace +X. `PREY_SPHERO_REQUIRE=1` fails if BLE is missing in sphero mode. Optional `SPHERO_NAME` selects the toy. `SPHERO_STUB=1` keeps the in-memory Mini (tests / no radio). Seek reuses the gantry travel box and wall margin so the ball turns back instead of pinning on the enclosure.

### Mini BLE check (no Ace / gantry)

Wake the ball, then roll a small square (0 / 90 / 180 / 270°) over BLE only:

```bash
pip install -e ".[sphero]"
SPHERO_NAME=SM-6399 PYTHONPATH=src python -m sphero.demo_roll
```

Or: `SPHERO_NAME=SM-6399 SPHERO_LIVE=1 PYTHONPATH=src pytest test/sphero/test_ble_move.py -s`
