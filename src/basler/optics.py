"""Ace 2 optics. Why: ferret_tracker.h constants, not inventing a new GSD."""

# a2A1920-160umPRO at 1.2 m with 4 mm lens — pylon-track ferret_tracker.h.
ACE_MODEL = "a2A1920-160umPRO"
GSD_MM_PX = 1.035
MOUNT_HEIGHT_MM = 1200.0
LENS_MM = 4.0
FPS = 200.0
# Why: MOG2 background learning is ~30 s at the Ace frame rate.
WARMUP_FRAMES = int(FPS * 30)
GRAB_STRATEGY = "LatestImageOnly"
