from museflow.domain.value_objects.music import TrackKnowIdentifiers

from tests.unit.factories.entities.music import TrackFactory


class TestTrackKnowIdentifiers:
    def test__is_known__isrc(self) -> None:
        isrc = "GBUM71029604"

        track = TrackFactory.build(isrc=isrc)
        known_identifiers = TrackKnowIdentifiers(
            isrcs=frozenset([isrc]),
            fingerprints=frozenset(),
        )

        assert known_identifiers.is_known(track) is True

    def test__is_known__fingerprint(self) -> None:
        fingerprint = "bohemian-rhapsody|queen"

        track = TrackFactory.build(fingerprint=fingerprint)
        known_identifiers = TrackKnowIdentifiers(
            isrcs=frozenset(),
            fingerprints=frozenset([fingerprint]),
        )

        assert known_identifiers.is_known(track) is True

    def test__is_not_known(self) -> None:
        track = TrackFactory.build(isrc="bar", fingerprint="bar")
        known_identifiers = TrackKnowIdentifiers(
            isrcs=frozenset(["foo"]),
            fingerprints=frozenset(["foo"]),
        )

        assert known_identifiers.is_known(track) is False
