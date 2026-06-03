import uuid

from museflow.domain.entities.discovery import DiscoveryPlaylistTrack
from museflow.domain.types import MusicProvider
from museflow.domain.utils.text import generate_fingerprint


class TestDiscoveryPlaylistTrackEntity:
    def test__fingerprint__computed_when_empty(self) -> None:
        track = DiscoveryPlaylistTrack(
            playlist_id=uuid.uuid4(),
            provider=MusicProvider.SPOTIFY,
            provider_id="abc123",
            track_name="Bohemian Rhapsody",
            artist_names=["Queen"],
            position=0,
        )
        expected = generate_fingerprint("Bohemian Rhapsody", ["Queen"])
        assert track.fingerprint == expected

    def test__fingerprint__not_recomputed_when_already_set(self) -> None:
        custom_fingerprint = "my-custom-fingerprint"
        track = DiscoveryPlaylistTrack(
            playlist_id=uuid.uuid4(),
            provider=MusicProvider.SPOTIFY,
            provider_id="abc123",
            track_name="Bohemian Rhapsody",
            artist_names=["Queen"],
            position=0,
            fingerprint=custom_fingerprint,
        )
        assert track.fingerprint == custom_fingerprint
