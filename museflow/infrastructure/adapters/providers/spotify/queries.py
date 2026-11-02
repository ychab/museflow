from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field


class SpotifySearchTrackQuery(BaseModel):
    model_config = ConfigDict(frozen=True)

    track: str = Field(min_length=1)
    artists: list[str] = Field(default_factory=list)
    is_new: bool = False
    is_underground: bool = False

    def _escape(self, val: str) -> str:
        return val.replace('"', '\\"')

    def get_query(self) -> str:
        parts = [f'track:"{self._escape(self.track)}"']

        # Spotify ignores OR (a query with it returns nothing) and several artist filters must all match:
        # filter on the primary artist only, the reconciler checks the others.
        if self.artists:
            parts.append(f'artist:"{self._escape(self.artists[0])}"')

        if self.is_new:
            parts.append("tag:new")

        if self.is_underground:
            parts.append("tag:hipster")

        return " ".join(parts)
