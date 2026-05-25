import pytest

from museflow.domain.services.reconciler import TrackReconciler

from tests.unit.factories.entities.music import TrackFactory
from tests.unit.factories.entities.music import TrackSuggestedFactory


@pytest.mark.parametrize("track_reconciler", [{"match_threshold": 80.0, "score_minimum": 60.0}], indirect=True)
class TestTrackReconciler:
    def test__reconcile__no_candidate(self, track_reconciler: TrackReconciler) -> None:
        result = track_reconciler.reconcile(track_suggested=TrackSuggestedFactory.build(), candidates=[])
        assert result is None

    def test__reconcile__no_matching_candidates(self, track_reconciler: TrackReconciler) -> None:
        track_suggested = TrackSuggestedFactory.build(name="Bohemian Rhapsody", artists=["Queen"])
        candidates = [
            TrackFactory.build(name="Under Pressure", artists=["Queen", "David Bowie"]),
            TrackFactory.build(name="Somebody To Love", artists=["Queen"]),
        ]

        result = track_reconciler.reconcile(track_suggested=track_suggested, candidates=candidates)
        assert result is None

    def test__reconcile__exact_match(self, track_reconciler: TrackReconciler) -> None:
        track_suggested = TrackSuggestedFactory.build(name="Bohemian Rhapsody", artists=["Queen"])

        expected_match = TrackFactory.build(name=track_suggested.name, artists=track_suggested.artists)
        candidates = [
            TrackFactory.build(name="Under Pressure", artists=["Queen"]),
            expected_match,
        ]

        result = track_reconciler.reconcile(track_suggested=track_suggested, candidates=candidates)
        assert result is not None
        track_reconciled, score = result
        assert track_reconciled is expected_match
        assert 0.0 < score <= 1.0

    def test__reconcile__fuzzy_text_match__ignores_noise(self, track_reconciler: TrackReconciler) -> None:
        track_suggested = TrackSuggestedFactory.build(name="Strobe", artists=["deadmau5"])

        expected_match = TrackFactory.build(name="Strobe - Radio Edit", artists=["deadmau5"])

        result = track_reconciler.reconcile(track_suggested=track_suggested, candidates=[expected_match])
        assert result is not None
        track_reconciled, score = result
        assert track_reconciled is expected_match
        assert 0.0 < score <= 1.0

    def test__reconcile__best_text_match_wins(self, track_reconciler: TrackReconciler) -> None:
        track_suggested = TrackSuggestedFactory.build(name="Bohemian Rhapsody", artists=["Queen"])

        close_match = TrackFactory.build(name="Bohemian Rhapsody", artists=["Queen"])
        poor_match = TrackFactory.build(name="Bohemian Rhapsody (Karaoke Version)", artists=["Unknown Artist"])

        result = track_reconciler.reconcile(track_suggested=track_suggested, candidates=[poor_match, close_match])
        assert result is not None
        track_reconciled, score = result
        assert track_reconciled is close_match
        assert 0.0 < score <= 1.0
