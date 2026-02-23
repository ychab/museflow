import pytest

from spotifagent.domain.entities.spotify import SpotifyAccountUpdate


class TestSpotifyAccountUpdate:
    def test_validate_one_field_set__nominal(self) -> None:
        spotify_account_update = SpotifyAccountUpdate(token_type="bearer")
        assert spotify_account_update.token_type == "bearer"

    def test_validate_one_field_set__error(self) -> None:
        with pytest.raises(ValueError, match="At least one field must be provided for update"):
            SpotifyAccountUpdate()
