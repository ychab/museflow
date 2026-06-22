from museflow.domain.value_objects.track import TrackKnowIdentifiers

from tests.unit.factories.entities.track import TrackFactory


class TestTrackKnowIdentifiers:
    def test__is_known__fingerprint(self) -> None:
        fingerprint = "bohemian-rhapsody|queen"

        track = TrackFactory.build(fingerprint=fingerprint)
        known_identifiers = TrackKnowIdentifiers(fingerprints=frozenset([fingerprint]))

        assert known_identifiers.is_known(track) is True

    def test__is_not_known(self) -> None:
        track = TrackFactory.build(fingerprint="bar")
        known_identifiers = TrackKnowIdentifiers(fingerprints=frozenset(["foo"]))

        assert known_identifiers.is_known(track) is False
