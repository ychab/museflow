from typing import Any

import pytest

from museflow.application.inputs.explore import ExploreArtistsConfigInput


class TestExploreArtistsConfigInput:
    @pytest.mark.parametrize(
        "field",
        ["max_attempts", "artist_tracks_concurrency", "artists_limit", "artists_per_attempt"],
    )
    @pytest.mark.parametrize("value", [0, -1])
    def test__below_one(self, field: str, value: int) -> None:
        kwargs: dict[str, Any] = {field: value}

        with pytest.raises(ValueError, match=f"{field} must be at least 1"):
            ExploreArtistsConfigInput(**kwargs)
