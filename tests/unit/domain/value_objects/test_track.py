from museflow.domain.value_objects.track import TrackKnownIdentifiers

from tests.unit.factories.entities.track import TrackFactory


class TestTrackKnowIdentifiers:
    def test__is_known__fingerprint(self) -> None:
        fingerprint = "bohemian-rhapsody|queen"

        track = TrackFactory.build(fingerprint=fingerprint)
        known_identifiers = TrackKnownIdentifiers(fingerprints=frozenset([fingerprint]))

        assert known_identifiers.is_known(track) is True

    def test__is_not_known(self) -> None:
        track = TrackFactory.build(fingerprint="bar")
        known_identifiers = TrackKnownIdentifiers(fingerprints=frozenset(["foo"]))

        assert known_identifiers.is_known(track) is False
