from datetime import UTC
from datetime import datetime
from typing import Final
from typing import Self

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field

# A search returns one ranking, capped around 250 tracks for a prolific artist, and its first tracks are the best
# known: split by release year, each range gets its own ranking, and together they reach far more of the catalogue
# (#203: 290 distinct tracks of the artist instead of 217 for 30 pages, 98 unknown to the user instead of 34).
CATALOGUE_OLDEST_YEAR: Final[int] = 1900
CATALOGUE_DECADES_FROM: Final[int] = 1980  # a single range before it: the older catalogues are small
CATALOGUE_SPANS_FROM: Final[int] = 2000  # 5-year ranges from there: the catalogues are denser
CATALOGUE_SPAN_YEARS: Final[int] = 5


class SpotifySearchArtistQuery(BaseModel):
    model_config = ConfigDict(frozen=True)

    artist: str = Field(min_length=1)
    years: tuple[int, int] | None = None  # release years, both included

    @classmethod
    def by_release_years(cls, artist: str, current_year: int | None = None) -> list[Self]:
        """One query per release year range, newest first, up to `current_year` (this year by default)."""
        current_year = current_year or datetime.now(UTC).year
        ranges = [(CATALOGUE_OLDEST_YEAR, CATALOGUE_DECADES_FROM - 1)]
        ranges += [(start, start + 9) for start in range(CATALOGUE_DECADES_FROM, CATALOGUE_SPANS_FROM, 10)]
        ranges += [
            (start, min(start + CATALOGUE_SPAN_YEARS - 1, current_year))
            for start in range(CATALOGUE_SPANS_FROM, current_year + 1, CATALOGUE_SPAN_YEARS)
        ]
        # Newest first: the recent releases are the likeliest to be unknown, and the candidates keep this order.
        return [cls(artist=artist, years=years) for years in reversed(ranges)]

    def get_query(self) -> str:
        query = f'artist:"{self.artist.replace('"', '\\"')}"'
        if self.years is not None:
            query += f" year:{self.years[0]}-{self.years[1]}"
        return query
