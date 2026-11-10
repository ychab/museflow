import logging

import pytest

from museflow.application.utils.discovery import filter_by_artist

from tests.unit.factories.entities.track import TrackFactory


class TestFilterByArtist:
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
    def test__nominal(self, artist: str, credited: list[str], kept: bool) -> None:
        track = TrackFactory.build(artists=credited)

        assert filter_by_artist(artist=artist, tracks=[track]) == ([track] if kept else [])

    def test__rejected__logged(self, caplog: pytest.LogCaptureFixture) -> None:
        with caplog.at_level(logging.DEBUG):
            filter_by_artist(artist="Nova", tracks=[TrackFactory.build(artists=["Novalee"])])

        assert "Artist 'Nova': rejected tracks of ['Novalee']" in caplog.text
