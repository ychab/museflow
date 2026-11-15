import logging

import pytest

from museflow.application.utils.discovery import filter_by_artist
from museflow.application.utils.discovery import is_live_or_medley
from museflow.application.utils.discovery import rank_favourite_artists

from tests.unit.factories.entities.track import TrackFactory
from tests.unit.factories.value_objects.stats import ArtistStatsFactory


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


class TestRankFavouriteArtists:
    def test__nominal(self) -> None:
        """Rated at or above the mean first, by smoothed rating then plays; then the unrated ones, by plays."""
        all_stats = [
            ArtistStatsFactory.build(artist="Unrated Less Played", plays_count=10),
            ArtistStatsFactory.build(artist="Rated Below Mean", plays_count=500, rated_count=2, rated_sum=8),
            ArtistStatsFactory.build(artist="Rated Once", plays_count=1, rated_count=1, rated_sum=9),
            ArtistStatsFactory.build(artist="Never Played", plays_count=0),
            ArtistStatsFactory.build(artist="Unrated Most Played", plays_count=50),
            ArtistStatsFactory.build(artist="Rated Twice", plays_count=1, rated_count=2, rated_sum=18),
            ArtistStatsFactory.build(artist="Rated Once Played More", plays_count=5, rated_count=1, rated_sum=9),
        ]

        # Mean 44 / 6 ≈ 7.33: two 9s smooth higher than one, a tie goes to the most played.
        assert rank_favourite_artists(all_stats, confidence=1) == [
            "Rated Twice",
            "Rated Once Played More",
            "Rated Once",
            "Unrated Most Played",
            "Unrated Less Played",
        ]

    def test__ratings__all_at_the_mean__kept(self) -> None:
        all_stats = [
            ArtistStatsFactory.build(artist="Less Played", plays_count=1, rated_count=1, rated_sum=8),
            ArtistStatsFactory.build(artist="More Played", plays_count=9, rated_count=1, rated_sum=8),
        ]

        assert rank_favourite_artists(all_stats, confidence=5) == ["More Played", "Less Played"]


class TestIsLiveOrMedley:
    @pytest.mark.parametrize(
        ("name", "album_name", "expected"),
        [
            pytest.param("Sin Sentimientos - En Vivo", "12 Años", True, id="live_dash_spanish"),
            pytest.param("Mi Pueblo (Live)", None, True, id="live_brackets"),
            pytest.param("Or Nah - Live at the Village", None, True, id="live_at"),
            pytest.param("Neon Harbor", "Live in Paris", True, id="live_album"),
            pytest.param("Tania / El Caminante / Nadando", None, True, id="medley_chained_titles"),
            pytest.param("Summer Medley", None, True, id="medley_named"),
            pytest.param("Live Your Life", "Paper Trail", False, id="live_word_of_the_title"),
            pytest.param("Mr. Williams / Where Is the Love", None, False, id="two_titles"),
            pytest.param("Delivery", None, False, id="live_inside_a_word"),
        ],
    )
    def test__nominal(self, name: str, album_name: str | None, expected: bool) -> None:
        track = TrackFactory.build(name=name, album_name=album_name)

        assert is_live_or_medley(track) is expected
