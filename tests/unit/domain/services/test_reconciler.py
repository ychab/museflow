import logging

import pytest

from museflow.domain.services.reconciler import Reconciler

from tests.unit.factories.entities.track import TrackFactory


class TestReconciler:
    @pytest.mark.parametrize(
        ("artist", "credited", "kept"),
        [
            pytest.param("Nova", ["Nova"], True, id="exact"),
            pytest.param("Beyoncé", ["BEYONCE"], True, id="case_and_accent"),
            pytest.param("Nova", ["A Guest Band", "Nova"], True, id="featured"),
            pytest.param("Nova", ["Novalee"], False, id="longer_name"),
            pytest.param("Nova Kane", ["Nova"], False, id="shorter_name"),
        ],
    )
    def test__filter_by_artist(self, reconciler: Reconciler, artist: str, credited: list[str], kept: bool) -> None:
        track = TrackFactory.build(artists=credited)

        assert reconciler.filter_by_artist(artist=artist, candidates=[track]) == ([track] if kept else [])

    def test__filter_by_artist__rejected__logged(
        self,
        reconciler: Reconciler,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        with caplog.at_level(logging.DEBUG):
            reconciler.filter_by_artist(artist="Nova", candidates=[TrackFactory.build(artists=["Novalee"])])

        assert "Artist 'Nova': rejected candidates of ['Novalee']" in caplog.text
