import pytest

from museflow.domain.services.reconciler import TrackReconciler
from museflow.domain.types import AlbumType

from tests.unit.factories.entities.music import AlbumFactory
from tests.unit.factories.entities.music import TrackArtistFactory
from tests.unit.factories.entities.music import TrackFactory
from tests.unit.factories.entities.music import TrackSuggestedFactory


@pytest.mark.parametrize("track_reconciler", [{"match_threshold": 80.0, "score_minimum": 60.0}], indirect=True)
class TestTrackReconciler:
    def test__reconcile__no_candidate(self, track_reconciler: TrackReconciler) -> None:
        result = track_reconciler.reconcile(track_suggested=TrackSuggestedFactory.build(), candidates=[])
        assert result is None

    def test__reconcile__no_matching_candidates(self, track_reconciler: TrackReconciler) -> None:
        track_suggested = TrackSuggestedFactory.build(name="Bohemian Rhapsody", artists=["Queen"], duration_ms=354000)
        candidates = [
            TrackFactory.build(
                name="Under Pressure",
                artists=[
                    TrackArtistFactory.build(name="Queen"),
                    TrackArtistFactory.build(name="David Bowie"),
                ],
                duration_ms=240000,
            ),
            TrackFactory.build(
                name="Somebody To Love",
                artists=[TrackArtistFactory.build(name="Queen")],
                duration_ms=300000,
            ),
        ]

        result = track_reconciler.reconcile(track_suggested=track_suggested, candidates=candidates)
        assert result is None

    def test__reconcile__exact_match(self, track_reconciler: TrackReconciler) -> None:
        track_suggested = TrackSuggestedFactory.build(name="Bohemian Rhapsody", artists=["Queen"], duration_ms=354000)

        expected_match = TrackFactory.build(
            name=track_suggested.name,
            artists=TrackArtistFactory.batch(size=1, name=track_suggested.artists[0]),
            duration_ms=track_suggested.duration_ms,
        )
        candidates = [
            TrackFactory.build(
                name="Under Pressure",
                artists=TrackArtistFactory.batch(size=1, name="Queen"),
                duration_ms=240000,
            ),
            expected_match,
        ]

        result = track_reconciler.reconcile(track_suggested=track_suggested, candidates=candidates)
        assert result is not None
        track_reconciled, score = result
        assert track_reconciled is expected_match
        assert 0.0 < score <= 1.0

    def test__reconcile__fuzzy_text_match__ignores_noise(self, track_reconciler: TrackReconciler) -> None:
        # Last.fm suggests a clean name
        track_suggested = TrackSuggestedFactory.build(name="Strobe", artists=["deadmau5"], duration_ms=637000)

        # Spotify returns a noisy name
        expected_match = TrackFactory.build(
            name="Strobe - Radio Edit",
            artists=TrackArtistFactory.batch(size=1, name="deadmau5"),
            duration_ms=637000,
        )

        result = track_reconciler.reconcile(track_suggested=track_suggested, candidates=[expected_match])
        assert result is not None
        track_reconciled, score = result
        assert track_reconciled is expected_match
        assert 0.0 < score <= 1.0

    def test__reconcile__tie_breaker__duration__big_bonus(self, track_reconciler: TrackReconciler) -> None:
        track_suggested = TrackSuggestedFactory.build(name="Strobe", artists=["deadmau5"], duration_ms=637000)

        radio_edit = TrackFactory.build(
            name="Strobe",
            artists=TrackArtistFactory.batch(size=1, name="deadmau5"),
            duration_ms=210000,
            popularity=0,
            album=None,
        )
        original_mix = TrackFactory.build(
            name="Strobe",
            artists=TrackArtistFactory.batch(size=1, name="deadmau5"),
            duration_ms=track_suggested.duration_ms,  # Exact duration match
            popularity=0,
            album=None,
        )

        result = track_reconciler.reconcile(track_suggested=track_suggested, candidates=[radio_edit, original_mix])
        assert result is not None
        track_reconciled, score = result
        assert track_reconciled is original_mix
        assert 0.0 < score <= 1.0

    def test__reconcile__tie_breaker__duration__small_bonus(self, track_reconciler: TrackReconciler) -> None:
        track_suggested = TrackSuggestedFactory.build(name="Starlight", artists=["Muse"], duration_ms=240000)

        live_mix = TrackFactory.build(
            name="Starlight",
            artists=TrackArtistFactory.batch(size=1, name="Muse"),
            duration_ms=300000,  # Live version, way too long (300,000 ms -> 60s diff -> No bonus)
            popularity=0,
            album=None,
        )
        slight_diff_mix = TrackFactory.build(
            name="Starlight",
            artists=TrackArtistFactory.batch(size=1, name="Muse"),
            duration_ms=233000,  # Slightly different master, 7 seconds shorter (233,000 ms -> 7s diff -> +5.0 bonus)
            popularity=0,
            album=None,
        )

        result = track_reconciler.reconcile(
            track_suggested=track_suggested,
            candidates=[live_mix, slight_diff_mix],
        )
        assert result is not None
        track_reconciled, score = result
        assert track_reconciled is slight_diff_mix
        assert 0.0 < score <= 1.0

    def test__reconcile__tie_breaker__album_type__compilation(self, track_reconciler: TrackReconciler) -> None:
        track_suggested = TrackSuggestedFactory.build(name="Creep", artists=["Radiohead"], duration_ms=238000)

        compilation = TrackFactory.build(
            name=track_suggested.name,
            artists=TrackArtistFactory.batch(size=1, name=track_suggested.artists[0]),
            duration_ms=track_suggested.duration_ms,
            album=AlbumFactory.build(album_type=AlbumType.COMPILATION),
        )
        studio_album = TrackFactory.build(
            name=track_suggested.name,
            artists=TrackArtistFactory.batch(size=1, name=track_suggested.artists[0]),
            duration_ms=track_suggested.duration_ms,
            album=AlbumFactory.build(album_type=AlbumType.ALBUM),  # Album wins over compilation
        )

        result = track_reconciler.reconcile(
            track_suggested=track_suggested,
            candidates=[compilation, studio_album],
        )
        assert result is not None
        track_reconciled, score = result
        assert track_reconciled is studio_album
        assert 0.0 < score <= 1.0

    def test__reconcile__tie_breaker__album_type__ep(self, track_reconciler: TrackReconciler) -> None:
        track_suggested = TrackSuggestedFactory.build(
            name="Dog Days Are Over", artists=["Florence"], duration_ms=252000
        )

        single_release = TrackFactory.build(
            name=track_suggested.name,
            artists=TrackArtistFactory.batch(size=1, name=track_suggested.artists[0]),
            duration_ms=track_suggested.duration_ms,
            popularity=0,
            album=AlbumFactory.build(album_type=AlbumType.SINGLE),  # Single (-5.0 penalty)
        )
        ep_release = TrackFactory.build(
            name=track_suggested.name,
            artists=TrackArtistFactory.batch(size=1, name=track_suggested.artists[0]),
            duration_ms=track_suggested.duration_ms,
            popularity=0,
            album=AlbumFactory.build(album_type=AlbumType.EP),  # EP (-2.0 penalty)
        )

        result = track_reconciler.reconcile(
            track_suggested=track_suggested,
            candidates=[single_release, ep_release],
        )
        assert result is not None
        track_reconciled, score = result
        assert track_reconciled is ep_release
        assert 0.0 < score <= 1.0

    def test__reconcile__tie_breaker__popularity(self, track_reconciler: TrackReconciler) -> None:
        track_suggested = TrackSuggestedFactory.build(name="Creep", artists=["Radiohead"], duration_ms=238000)

        low_pop_release = TrackFactory.build(
            name=track_suggested.name,
            artists=TrackArtistFactory.batch(size=1, name=track_suggested.artists[0]),
            duration_ms=track_suggested.duration_ms,
            album=AlbumFactory.build(album_type=AlbumType.ALBUM),
            popularity=20,
        )
        high_pop_release = TrackFactory.build(
            name=track_suggested.name,
            artists=TrackArtistFactory.batch(size=1, name=track_suggested.artists[0]),
            duration_ms=track_suggested.duration_ms,
            album=AlbumFactory.build(album_type=AlbumType.ALBUM),
            popularity=85,  # Most popular
        )

        result = track_reconciler.reconcile(
            track_suggested=track_suggested,
            candidates=[low_pop_release, high_pop_release],
        )
        assert result is not None
        track_reconciled, score = result
        assert track_reconciled is high_pop_release
        assert 0.0 < score <= 1.0
