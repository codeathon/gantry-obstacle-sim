"""Bleak find_toy uses asyncio.run; that cannot run on uvicorn's loop."""

from __future__ import annotations

import asyncio
import threading

from sphero import ble_hw


def test_connect_ble_hops_off_running_loop(monkeypatch) -> None:
	seen: list[str] = []

	def fake_locked():
		seen.append(threading.current_thread().name)
		return object()

	monkeypatch.setattr(ble_hw, "_connect_ble_locked", fake_locked)

	async def inside_uvicorn():
		return ble_hw.connect_ble()

	toy = asyncio.run(inside_uvicorn())
	assert toy is not None
	assert seen == ["sphero-ble-open"]


def test_scan_retries_then_connects(monkeypatch) -> None:
	# Why: one missed advertisement used to drop the hunt onto SpheroStub.
	from sphero.ble_hw import _scan_toy

	n = {"i": 0}

	class Scan:
		def find_toy(self, toy_name=None):
			n["i"] += 1
			if n["i"] < 2:
				raise RuntimeError()
			return "SM-6399"

	monkeypatch.setattr("time.sleep", lambda _s: None)
	assert _scan_toy(Scan(), "SM-6399") == "SM-6399"


def test_connect_ble_stays_on_bare_thread(monkeypatch) -> None:
	# Why: demo_roll and sphero-seek have no loop; keep GATT on that thread.
	seen: list[str] = []

	def fake_locked():
		seen.append(threading.current_thread().name)
		return object()

	monkeypatch.setattr(ble_hw, "_connect_ble_locked", fake_locked)
	ble_hw.connect_ble()
	assert seen == [threading.current_thread().name]
