from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field


class SpotifySearchArtistQuery(BaseModel):
    model_config = ConfigDict(frozen=True)

    artist: str = Field(min_length=1)

    def get_query(self) -> str:
        return f'artist:"{self.artist.replace('"', '\\"')}"'
