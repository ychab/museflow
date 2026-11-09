from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field


class SpotifySearchTrackQuery(BaseModel):
    model_config = ConfigDict(frozen=True)

    track: str = Field(min_length=1)
    artists: list[str] = Field(default_factory=list)
    is_new: bool = False
    is_underground: bool = False

    def get_query(self) -> str:
        parts = [f'track:"{self._escape(self.track)}"']

        # Spotify ignores OR (a query with it returns nothing) and several artist filters must all match:
        # filter on the primary artist only, the reconciler checks the others.
        if self.artists:
            parts.append(f'artist:"{self._escape(self.artists[0])}"')

        parts.extend(self._get_tags())
        return " ".join(parts)

    def get_free_text_query(self) -> str:
        """The track and primary artist as plain words, matched in any field: looser than the field filters."""
        words = " ".join(word.replace('"', " ") for word in [self.track, *self.artists[:1]])
        return " ".join([" ".join(words.split()), *self._get_tags()])

    def _escape(self, val: str) -> str:
        return val.replace('"', '\\"')

    def _get_tags(self) -> list[str]:
        tags = []
        if self.is_new:
            tags.append("tag:new")
        if self.is_underground:
            tags.append("tag:hipster")
        return tags
