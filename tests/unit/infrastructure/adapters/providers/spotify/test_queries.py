import pytest

from museflow.infrastructure.adapters.providers.spotify.queries import SpotifySearchArtistQuery


class TestSpotifySearchArtistQuery:
    def test__query__escaped(self) -> None:
        assert SpotifySearchArtistQuery(artist='The "Band"').get_query() == 'artist:"The \\"Band\\""'

    def test__query__years(self) -> None:
        query = SpotifySearchArtistQuery(artist="The Band", years=(2000, 2004))

        assert query.get_query() == 'artist:"The Band" year:2000-2004'

    @pytest.mark.parametrize(
        ("current_year", "newest"),
        [
            pytest.param(2026, [(2025, 2026), (2020, 2024)], id="span_started"),
            pytest.param(2029, [(2025, 2029), (2020, 2024)], id="span_full"),
            pytest.param(2030, [(2030, 2030), (2025, 2029)], id="span_new"),
        ],
    )
    def test__by_release_years(self, current_year: int, newest: list[tuple[int, int]]) -> None:
        queries = SpotifySearchArtistQuery.by_release_years(artist="The Band", current_year=current_year)

        assert {query.artist for query in queries} == {"The Band"}
        ranges = [query.years for query in queries]
        # Newest first, up to the current year; then the 5-year ranges, the decades, and one range before them.
        assert ranges[:2] == newest
        assert ranges[-5:] == [(2005, 2009), (2000, 2004), (1990, 1999), (1980, 1989), (1900, 1979)]
        # Contiguous: no year left out between two ranges.
        assert all(older[1] + 1 == newer[0] for newer, older in zip(ranges, ranges[1:], strict=False))  # type: ignore[index]
