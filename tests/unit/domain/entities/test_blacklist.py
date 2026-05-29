import uuid

import pytest

from museflow.domain.entities.blacklist import BlacklistedArtist
from museflow.domain.entities.blacklist import BlacklistedTrack
from museflow.domain.utils.text import generate_fingerprint
from museflow.domain.utils.text import normalize_text
from museflow.domain.value_objects.blacklist import UserBlacklist

from tests.unit.factories.entities.blacklist import BlacklistedArtistFactory
from tests.unit.factories.entities.blacklist import BlacklistedTrackFactory


class TestBlacklistedArtist:
    def test__fingerprint_computed_when_empty(self) -> None:
        artist = BlacklistedArtist(id=uuid.uuid4(), user_id=uuid.uuid4(), artist_name="Taylor Swift")
        assert artist.fingerprint == normalize_text("Taylor Swift")

    def test__fingerprint_preserved_when_provided(self) -> None:
        artist = BlacklistedArtist(
            id=uuid.uuid4(), user_id=uuid.uuid4(), artist_name="Taylor Swift", fingerprint="custom"
        )
        assert artist.fingerprint == "custom"

    def test__empty_artist_name_raises(self) -> None:
        with pytest.raises(ValueError, match="artist_name must not be empty"):
            BlacklistedArtist(id=uuid.uuid4(), user_id=uuid.uuid4(), artist_name="")


class TestBlacklistedTrack:
    def test__fingerprint_computed_when_empty(self) -> None:
        track = BlacklistedTrack(
            id=uuid.uuid4(), user_id=uuid.uuid4(), name="Shake It Off", artist_name="Taylor Swift"
        )
        assert track.fingerprint == generate_fingerprint("Shake It Off", ["Taylor Swift"])

    def test__fingerprint_preserved_when_provided(self) -> None:
        track = BlacklistedTrack(
            id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            name="Shake It Off",
            artist_name="Taylor Swift",
            fingerprint="custom",
        )
        assert track.fingerprint == "custom"

    def test__empty_name_raises(self) -> None:
        with pytest.raises(ValueError, match="name must not be empty"):
            BlacklistedTrack(id=uuid.uuid4(), user_id=uuid.uuid4(), name="", artist_name="Taylor Swift")

    def test__empty_artist_name_raises(self) -> None:
        with pytest.raises(ValueError, match="artist_name must not be empty"):
            BlacklistedTrack(id=uuid.uuid4(), user_id=uuid.uuid4(), name="Shake It Off", artist_name="")


class TestUserBlacklist:
    def test__is_empty_when_no_entries(self) -> None:
        assert UserBlacklist().is_empty is True

    def test__is_empty_false_when_artists(self) -> None:
        blacklist = UserBlacklist(artists=[BlacklistedArtistFactory.build()])
        assert blacklist.is_empty is False

    def test__is_empty_false_when_tracks(self) -> None:
        blacklist = UserBlacklist(tracks=[BlacklistedTrackFactory.build()])
        assert blacklist.is_empty is False

    def test__artist_names(self) -> None:
        artist = BlacklistedArtistFactory.build(artist_name="Taylor Swift")
        blacklist = UserBlacklist(artists=[artist])
        assert blacklist.artist_names == ["Taylor Swift"]

    def test__artist_fingerprints(self) -> None:
        artist = BlacklistedArtistFactory.build(artist_name="Taylor Swift", fingerprint="")
        blacklist = UserBlacklist(artists=[artist])
        assert blacklist.artist_fingerprints == {normalize_text("Taylor Swift")}

    def test__track_fingerprints(self) -> None:
        track = BlacklistedTrackFactory.build(name="Shake It Off", artist_name="Taylor Swift", fingerprint="")
        blacklist = UserBlacklist(tracks=[track])
        assert blacklist.track_fingerprints == {generate_fingerprint("Shake It Off", ["Taylor Swift"])}

    def test__track_display_strings(self) -> None:
        track = BlacklistedTrackFactory.build(name="Shake It Off", artist_name="Taylor Swift")
        blacklist = UserBlacklist(tracks=[track])
        assert blacklist.track_display_strings == ["Shake It Off by Taylor Swift"]
