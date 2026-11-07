from pydantic import Field

from museflow.application.inputs.base import BaseInput


class BlacklistArtistEntryInput(BaseInput):
    artist_name: str = Field(min_length=1)


class BlacklistTrackEntryInput(BaseInput):
    name: str = Field(min_length=1)
    artist_name: str = Field(min_length=1)


class BlacklistImportInput(BaseInput):
    """The blacklist file: `blacklist export` writes it, `blacklist import` reads it."""

    artists: list[BlacklistArtistEntryInput] = []
    tracks: list[BlacklistTrackEntryInput] = []
