import logging

import pytest

from museflow.domain.services.reconciler import Reconciler

from tests.unit.factories.entities.track import TrackFactory
from tests.unit.factories.entities.track import TrackSuggestedFactory


@pytest.mark.parametrize("reconciler", [{"match_threshold": 80.0}], indirect=True)
class TestReconciler:
    def test__reconcile__no_candidate(self, reconciler: Reconciler, caplog: pytest.LogCaptureFixture) -> None:
        track_suggested = TrackSuggestedFactory.build(name="Bohemian Rhapsody", artists=["Queen"])

        with caplog.at_level(logging.DEBUG):
            result = reconciler.reconcile(track_suggested=track_suggested, candidates=[])

        assert result is None
        assert caplog.messages == [
            "Reconciliation failed for 'Queen - Bohemian Rhapsody'. Best score: -1.0. No candidate",
        ]

    def test__reconcile__no_matching_candidates(
        self,
        reconciler: Reconciler,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        track_suggested = TrackSuggestedFactory.build(name="Bohemian Rhapsody", artists=["Queen"])
        candidates = [
            TrackFactory.build(name="Under Pressure", artists=["David Bowie"]),
            TrackFactory.build(name="Bohemian Rhapsody (Nightmare)", artists=["Queen"]),
            TrackFactory.build(name="Somebody To Love", artists=["Queen"]),
        ]

        with caplog.at_level(logging.DEBUG):
            result = reconciler.reconcile(track_suggested=track_suggested, candidates=candidates)

        assert result is None
        assert caplog.messages == [
            "Reconciliation failed for 'Queen - Bohemian Rhapsody'. Best score: 0.0. "
            "Closest candidate: 'Queen - Bohemian Rhapsody (Nightmare)' (track: 77.3, artist: 100.0)",
        ]

    def test__reconcile__exact_match(self, reconciler: Reconciler) -> None:
        track_suggested = TrackSuggestedFactory.build(name="Bohemian Rhapsody", artists=["Queen"])

        expected_match = TrackFactory.build(name=track_suggested.name, artists=track_suggested.artists)
        candidates = [
            TrackFactory.build(name="Under Pressure", artists=["Queen"]),
            expected_match,
        ]

        result = reconciler.reconcile(track_suggested=track_suggested, candidates=candidates)
        assert result is not None
        track_reconciled, score = result
        assert track_reconciled is expected_match
        assert 0.0 < score <= 1.0

    def test__reconcile__fuzzy_text_match__ignores_noise(self, reconciler: Reconciler) -> None:
        track_suggested = TrackSuggestedFactory.build(name="Strobe", artists=["deadmau5"])

        expected_match = TrackFactory.build(name="Strobe - Radio Edit", artists=["deadmau5"])

        result = reconciler.reconcile(track_suggested=track_suggested, candidates=[expected_match])
        assert result is not None
        track_reconciled, score = result
        assert track_reconciled is expected_match
        assert 0.0 < score <= 1.0

    def test__reconcile__best_text_match_wins(self, reconciler: Reconciler) -> None:
        track_suggested = TrackSuggestedFactory.build(name="Bohemian Rhapsody", artists=["Queen"])

        close_match = TrackFactory.build(name="Bohemian Rhapsody", artists=["Queen"])
        poor_match = TrackFactory.build(name="Bohemian Rhapsody (Karaoke Version)", artists=["Unknown Artist"])

        result = reconciler.reconcile(track_suggested=track_suggested, candidates=[poor_match, close_match])
        assert result is not None
        track_reconciled, score = result
        assert track_reconciled is close_match
        assert 0.0 < score <= 1.0
