"""pylon-track ObjectAssociator: ferret area prior + track continuity."""

from vision.associator import Blob, ObjectAssociator, VisionPriors


def test_picks_ferret_sized_blob_over_small_leftover() -> None:
	assoc = ObjectAssociator(
		VisionPriors(ferret_area_px_min=20.0, ferret_area_px_max=80.0)
	)
	toy = Blob(20.0, 16.0, area_px=8.0)
	ferret = Blob(6.0, 16.0, area_px=40.0)
	hit = assoc.pick_ferret([toy, ferret])
	assert hit is ferret


def test_proximity_keeps_the_same_ferret() -> None:
	# Why: two ferret-sized blobs — continuity wins like pylon-track.
	assoc = ObjectAssociator(
		VisionPriors(ferret_area_px_min=10.0, ferret_area_px_max=80.0)
	)
	near = Blob(10.0, 10.0, area_px=30.0)
	far = Blob(80.0, 80.0, area_px=30.0)
	hit = assoc.pick_ferret([far, near], prior_px=(11.0, 9.0))
	assert hit is near


def test_compact_prior_picks_mini_over_gantry() -> None:
	# Why: default mid-band score treated the XXY carriage as the ferret.
	assoc = ObjectAssociator(
		VisionPriors(
			ferret_area_px_min=80.0,
			ferret_area_px_max=8000.0,
			prefer_compact=True,
			ferret_area_px_pref=1600.0,
		)
	)
	gantry = Blob(80.0, 40.0, area_px=7000.0)
	mini = Blob(20.0, 40.0, area_px=1500.0)
	assert assoc.pick_ferret([gantry, mini]) is mini


def test_rejects_blobs_outside_the_ferret_area_band() -> None:
	# Why: gantry-beam leftovers sit outside the live Ace ferret area band.
	assoc = ObjectAssociator()
	small = Blob(4.0, 4.0, area_px=9.0)
	assert assoc.pick_ferret([small]) is None
	assert assoc.pick_ferret([]) is None
