import pytest

from tests.integration.factories.music import TopArtistModelFactory
from tests.integration.factories.music import TopTrackModelFactory
from tests.integration.factories.users import UserModelFactory


class TestTopArtistModelFactory:
    @pytest.mark.parametrize(("name", "expected_slug"), [("Yé Ho", "ye-ho")])
    async def test__slug(self, name: str, expected_slug: str) -> None:
        top_artist_db = await TopArtistModelFactory.create_async(name=name)
        assert top_artist_db.slug == expected_slug

    async def test__user__default(self) -> None:
        top_artist_db = await TopArtistModelFactory.create_async()
        assert top_artist_db.user_id is not None

    async def test__user__provided(self) -> None:
        user_db = await UserModelFactory.create_async()
        top_artist_db = await TopArtistModelFactory.create_async(user_id=user_db.id)
        assert top_artist_db.user_id == user_db.id


class TestTopTrackModelFactory:
    @pytest.mark.parametrize(("name", "expected_slug"), [("Yé Ho", "ye-ho")])
    async def test__slug(self, name: str, expected_slug: str) -> None:
        top_track_db = await TopTrackModelFactory.create_async(name=name)
        assert top_track_db.slug == expected_slug

    async def test__user__default(self) -> None:
        top_track_db = await TopTrackModelFactory.create_async()
        assert top_track_db.user_id is not None

    async def test__user__provided(self) -> None:
        user_db = await UserModelFactory.create_async()
        top_track_db = await TopTrackModelFactory.create_async(user_id=user_db.id)
        assert top_track_db.user_id == user_db.id
