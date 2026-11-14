from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field

# A search returns one ranking, capped around 250 tracks for a prolific artist, and its first tracks are the best
# known: split by release year, each range gets its own ranking, and together they reach far more of the catalogue
# (#203: 290 distinct tracks of the artist instead of 217 for 30 pages, 98 unknown to the user instead of 34).
CATALOGUE_OLDEST_YEAR = 1900
CATALOGUE_DECADES_FROM = 1980  # a single range before it: the older catalogues are small
CATALOGUE_SPANS_FROM = 2000  # 5-year ranges from there: the catalogues are denser
CATALOGUE_SPAN_YEARS = 5


class SpotifySearchArtistQuery(BaseModel):
    model_config = ConfigDict(frozen=True)

    artist: str = Field(min_length=1)
    years: tuple[int, int] | None = None  # release years, both included

    def get_query(self) -> str:
        query = f'artist:"{self.artist.replace('"', '\\"')}"'
        if self.years is not None:
            query += f" year:{self.years[0]}-{self.years[1]}"
        return query


def get_release_year_ranges(current_year: int) -> list[tuple[int, int]]:
    """The release year ranges an artist's catalogue is searched by, newest first, up to `current_year`."""
    ranges = [(CATALOGUE_OLDEST_YEAR, CATALOGUE_DECADES_FROM - 1)]
    ranges += [(start, start + 9) for start in range(CATALOGUE_DECADES_FROM, CATALOGUE_SPANS_FROM, 10)]
    ranges += [
        (start, min(start + CATALOGUE_SPAN_YEARS - 1, current_year))
        for start in range(CATALOGUE_SPANS_FROM, current_year + 1, CATALOGUE_SPAN_YEARS)
    ]
    # Newest first: the recent releases are the likeliest to be unknown, and the candidates keep this order.
    return ranges[::-1]
