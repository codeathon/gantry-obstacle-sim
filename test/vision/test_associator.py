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


def _mini_assoc() -> ObjectAssociator:
	# Why: live Mini priors from HuntSim when PREY_ANIMAL=sphero.
	return ObjectAssociator(
		VisionPriors(
			ferret_area_px_min=80.0,
			ferret_area_px_max=8000.0,
			prefer_compact=True,
			ferret_area_px_pref=1600.0,
		)
	)


def test_compact_prior_picks_mini_over_gantry() -> None:
	# Why: default mid-band score treated the XXY carriage as the ferret.
	gantry = Blob(80.0, 40.0, area_px=7000.0)
	mini = Blob(20.0, 40.0, area_px=1500.0)
	assert _mini_assoc().pick_ferret([gantry, mini]) is mini


def test_compact_mini_near_encoder_beats_leftover_gantry() -> None:
	# Why: lure parks the encoder on the Mini; leftover beam must not steal the ID.
	gantry = Blob(80.0, 40.0, area_px=7000.0)
	mini = Blob(20.0, 40.0, area_px=1500.0)
	stuck = (80.0, 40.0)
	hit = _mini_assoc().pick_ferret(
		[gantry, mini], prior_px=stuck, prey_px=(22.0, 41.0)
	)
	assert hit is mini


def test_compact_picks_far_mini_when_encoder_is_on_gantry() -> None:
	gantry = Blob(80.0, 40.0, area_px=7000.0)
	mini = Blob(20.0, 40.0, area_px=1500.0)
	assert _mini_assoc().pick_ferret([gantry, mini], prey_px=(80.0, 40.0)) is mini


def test_compact_rejects_lone_large_gantry() -> None:
	# Why: empty arena except a beam leftover — do not invent a Mini.
	gantry = Blob(80.0, 40.0, area_px=7000.0)
	assoc = _mini_assoc()
	assert assoc.pick_ferret([gantry], prey_px=(80.0, 40.0)) is None
	assert assoc.pick_ferret([gantry]) is None


def test_rejects_blobs_outside_the_ferret_area_band() -> None:
	# Why: gantry-beam leftovers sit outside the live Ace ferret area band.
	assoc = ObjectAssociator()
	small = Blob(4.0, 4.0, area_px=9.0)
	assert assoc.pick_ferret([small]) is None
	assert assoc.pick_ferret([]) is None
