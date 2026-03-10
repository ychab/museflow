import uuid

from museflow.domain.entities.music import Track
from museflow.domain.entities.music import TrackArtist


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
