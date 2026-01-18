import pytest

from tests.unit.factories.music import TopArtistFactory
from tests.unit.factories.music import TopTrackFactory


class TestTopArtistFactory:
    @pytest.mark.parametrize(("name", "expected_slug"), [("Yé Ho", "ye-ho")])
    def test__slug(self, name: str, expected_slug: str) -> None:
        top_artist = TopArtistFactory.build(name=name)
        assert top_artist.slug == expected_slug


class TestTopTrackFactory:
    @pytest.mark.parametrize(("name", "expected_slug"), [("Yé Ho", "ye-ho")])
    def test__slug(self, name: str, expected_slug: str) -> None:
        top_track = TopTrackFactory.build(name=name)
        assert top_track.slug == expected_slug
