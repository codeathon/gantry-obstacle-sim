"""Soft-limit geometry. Why: clip in mm before any SDK call so walls are software."""

from __future__ import annotations


def clip_xy(
	x_mm: float,
	y_mm: float,
	x_min: float,
	x_max: float,
	y_min: float,
	y_max: float,
) -> tuple[float, float]:
	# Why: keep commands inside the arena so the carriage never hits hard limits.
	return (
		min(max(x_mm, x_min), x_max),
		min(max(y_mm, y_min), y_max),
	)


def point_in_workspace(
	x_mm: float,
	y_mm: float,
	x_min: float,
	x_max: float,
	y_min: float,
	y_max: float,
) -> bool:
	# Why: coverage/smoke scripts skip points outside the hunt rectangle.
	return x_min <= x_mm <= x_max and y_min <= y_mm <= y_max
