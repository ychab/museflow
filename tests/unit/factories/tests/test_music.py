import pytest

from tests.unit.factories.music import ArtistFactory
from tests.unit.factories.music import TrackFactory


class TestArtistFactory:
    @pytest.mark.parametrize(("name", "expected_slug"), [("Yé Ho", "ye-ho")])
    def test__slug(self, name: str, expected_slug: str) -> None:
        artist = ArtistFactory.build(name=name)
        assert artist.slug == expected_slug


class TestTrackFactory:
    @pytest.mark.parametrize(("name", "expected_slug"), [("Yé Ho", "ye-ho")])
    def test__slug(self, name: str, expected_slug: str) -> None:
        track = TrackFactory.build(name=name)
        assert track.slug == expected_slug
