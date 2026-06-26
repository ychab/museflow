import uuid

import pytest

from museflow.domain.entities.track import ProviderLink
from museflow.domain.entities.track import Track
from museflow.domain.entities.track import TrackSuggested
from museflow.domain.types import MusicProvider


class TestTrack:
    def test__fingerprint__provided(self) -> None:
        track = Track(
            user_id=uuid.uuid4(),
            name="foo",
            provider_links=[ProviderLink(provider=MusicProvider.SPOTIFY, provider_id=str(uuid.uuid4()))],
            artists=["bar"],
            fingerprint="baz",
        )
        assert track.fingerprint == "baz"

    def test__fingerprint__generated(self) -> None:
        track = Track(
            user_id=uuid.uuid4(),
            name="foo",
            provider_links=[ProviderLink(provider=MusicProvider.SPOTIFY, provider_id=str(uuid.uuid4()))],
            artists=["foo"],
        )
        assert track.fingerprint != ""

    def test__fingerprint__uses_primary_artist_only(self) -> None:
        track_single = Track(
            user_id=uuid.uuid4(),
            name="Song",
            provider_links=[ProviderLink(provider=MusicProvider.SPOTIFY, provider_id="id1")],
            artists=["Main Artist"],
        )
        track_feat = Track(
            user_id=uuid.uuid4(),
            name="Song",
            provider_links=[ProviderLink(provider=MusicProvider.SPOTIFY, provider_id="id2")],
            artists=["Main Artist", "Featured Artist"],
        )
        assert track_single.fingerprint == track_feat.fingerprint

    def test__name__none(self) -> None:
        with pytest.raises(ValueError, match="Track.name must not be empty"):
            Track(
                user_id=uuid.uuid4(),
                name="",
                provider_links=[ProviderLink(provider=MusicProvider.SPOTIFY, provider_id="spotify:track:123")],
                artists=["Queen"],
            )

    def test__provider_links__empty(self) -> None:
        with pytest.raises(ValueError, match="Track must have at least one provider link"):
            Track(user_id=uuid.uuid4(), name="Bohemian Rhapsody", provider_links=[], artists=["Queen"])

    def test__artists__none(self) -> None:
        with pytest.raises(ValueError, match="Track must have at least one artist"):
            Track(
                user_id=uuid.uuid4(),
                name="Bohemian Rhapsody",
                provider_links=[ProviderLink(provider=MusicProvider.SPOTIFY, provider_id="spotify:track:123")],
                artists=[],
            )


class TestTrackSuggested:
    def test__name__none(self) -> None:
        with pytest.raises(ValueError, match="TrackSuggested.name must not be empty"):
            TrackSuggested(name="", artists=["Queen"], score=0.5)

    def test__artists__none(self) -> None:
        with pytest.raises(ValueError, match="TrackSuggested must have at least one artist"):
            TrackSuggested(name="Bohemian Rhapsody", artists=[], score=0.5)
