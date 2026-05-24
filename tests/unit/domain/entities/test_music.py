import uuid

import pytest

from museflow.domain.entities.music import Track
from museflow.domain.entities.music import TrackArtist
from museflow.domain.entities.music import TrackSuggested


class TestTrackArtist:
    def test__name__none(self) -> None:
        with pytest.raises(ValueError, match="TrackArtist.name must not be empty"):
            TrackArtist(name="", provider_id="some-id")

    def test__provider_id__none(self) -> None:
        with pytest.raises(ValueError, match="TrackArtist.provider_id must not be empty"):
            TrackArtist(name="Queen", provider_id="")


class TestTrack:
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

    def test__name__none(self) -> None:
        with pytest.raises(ValueError, match="Track.name must not be empty"):
            Track(
                user_id=uuid.uuid4(),
                name="",
                provider_id="spotify:track:123",
                artists=[TrackArtist(name="Queen", provider_id="spotify:artist:456")],
                duration_ms=180_000,
            )

    def test__provider_id__none(self) -> None:
        with pytest.raises(ValueError, match="Track.provider_id must not be empty"):
            Track(
                user_id=uuid.uuid4(),
                name="Bohemian Rhapsody",
                provider_id="",
                artists=[TrackArtist(name="Queen", provider_id="spotify:artist:456")],
                duration_ms=180_000,
            )

    def test__artists__none(self) -> None:
        with pytest.raises(ValueError, match="Track must have at least one artist"):
            Track(
                user_id=uuid.uuid4(),
                name="Bohemian Rhapsody",
                provider_id="spotify:track:123",
                artists=[],
                duration_ms=180_000,
            )

    def test__artist__name__none(self) -> None:
        with pytest.raises(ValueError, match="TrackArtist.name must not be empty"):
            Track(
                user_id=uuid.uuid4(),
                name="Bohemian Rhapsody",
                provider_id="spotify:track:123",
                artists=[TrackArtist(name="", provider_id="spotify:artist:456")],
                duration_ms=180_000,
            )

    def test__artist__provider_id__none(self) -> None:
        with pytest.raises(ValueError, match="TrackArtist.provider_id must not be empty"):
            Track(
                user_id=uuid.uuid4(),
                name="Bohemian Rhapsody",
                provider_id="spotify:track:123",
                artists=[TrackArtist(name="Queen", provider_id="")],
                duration_ms=180_000,
            )


class TestTrackSuggested:
    def test__name__none(self) -> None:
        with pytest.raises(ValueError, match="TrackSuggested.name must not be empty"):
            TrackSuggested(name="", artists=["Queen"], score=0.5)

    def test__artists__none(self) -> None:
        with pytest.raises(ValueError, match="TrackSuggested must have at least one artist"):
            TrackSuggested(name="Bohemian Rhapsody", artists=[], score=0.5)
