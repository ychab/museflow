import uuid

import pytest

from museflow.domain.entities.music import Artist
from museflow.domain.entities.music import Track
from museflow.domain.entities.music import TrackArtist


class TestArtist:
    @pytest.mark.parametrize(
        ("genres", "expected"),
        [
            pytest.param(["Pop", "Rock"], ["pop", "rock"], id="mixed_case"),
            pytest.param(["POP", "ROCK"], ["pop", "rock"], id="all_upper"),
            pytest.param(["pop", "rock"], ["pop", "rock"], id="already_lower"),
            pytest.param(["Variété française"], ["variete francaise"], id="unidecode"),
            pytest.param(["Hip-Hop", "R&B"], ["hip-hop", "r&b"], id="special_chars"),
            pytest.param([], [], id="empty"),
        ],
    )
    def test__genres__normalized(self, genres: list[str], expected: list[str]) -> None:
        artist = Artist(
            user_id=uuid.uuid4(),
            name="foo",
            provider_id="bar",
            genres=genres,
        )
        assert artist.genres == expected


class TestTrack:
    @pytest.mark.parametrize(
        ("genres", "expected"),
        [
            pytest.param(["Pop", "Rock"], ["pop", "rock"], id="mixed_case"),
            pytest.param(["POP", "ROCK"], ["pop", "rock"], id="all_upper"),
            pytest.param(["pop", "rock"], ["pop", "rock"], id="already_lower"),
            pytest.param(["Variété française"], ["variete francaise"], id="unidecode"),
            pytest.param(["Hip-Hop", "R&B"], ["hip-hop", "r&b"], id="special_chars"),
            pytest.param([], [], id="empty"),
        ],
    )
    def test__genres__normalized(
        self,
        genres: list[str],
        expected: list[str],
    ) -> None:
        track = Track(
            user_id=uuid.uuid4(),
            name="foo",
            provider_id="bar",
            artists=[TrackArtist(name="foo", provider_id="baz")],
            duration_ms=180_000,
            genres=genres,
        )
        assert track.genres == expected

    def test__genres__normalized__no_break_fingerprint(self) -> None:
        track = Track(
            user_id=uuid.uuid4(),
            name="Bohemian Rhapsody",
            provider_id="bar",
            artists=[TrackArtist(name="Queen", provider_id="baz")],
            duration_ms=354_000,
            genres=["Rock", "Arena Rock"],
        )
        assert track.genres == ["rock", "arena rock"]
        assert track.fingerprint != ""

    def test__fingerprint__provided(self) -> None:
        track = Track(
            user_id=uuid.uuid4(),
            name="foo",
            provider_id=str(uuid.uuid4()),
            artists=[TrackArtist(name="bar", provider_id=str(uuid.uuid4()))],
            duration_ms=3 * 60,
            fingerprint="baz",
        )
        assert track.fingerprint == "baz"

    def test__fingerprint__generated(self) -> None:
        track = Track(
            user_id=uuid.uuid4(),
            name="foo",
            provider_id=str(uuid.uuid4()),
            artists=[TrackArtist(name="foo", provider_id=str(uuid.uuid4()))],
            duration_ms=3 * 60,
        )
        assert track.fingerprint != ""
