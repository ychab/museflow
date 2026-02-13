import pytest

from tests.integration.factories.music import ArtistModelFactory
from tests.integration.factories.music import TrackModelFactory
from tests.integration.factories.users import UserModelFactory


class TestArtistModelFactory:
    @pytest.mark.parametrize(("name", "expected_slug"), [("Yé Ho", "ye-ho")])
    async def test__slug(self, name: str, expected_slug: str) -> None:
        artist_db = await ArtistModelFactory.create_async(name=name)
        assert artist_db.slug == expected_slug

    async def test__user__default(self) -> None:
        artist_db = await ArtistModelFactory.create_async()
        assert artist_db.user_id is not None

    async def test__user__provided(self) -> None:
        user_db = await UserModelFactory.create_async()
        artist_db = await ArtistModelFactory.create_async(user_id=user_db.id)
        assert artist_db.user_id == user_db.id


class TestTrackModelFactory:
    @pytest.mark.parametrize(("name", "expected_slug"), [("Yé Ho", "ye-ho")])
    async def test__slug(self, name: str, expected_slug: str) -> None:
        track_db = await TrackModelFactory.create_async(name=name)
        assert track_db.slug == expected_slug

    async def test__user__default(self) -> None:
        track_db = await TrackModelFactory.create_async()
        assert track_db.user_id is not None

    async def test__user__provided(self) -> None:
        user_db = await UserModelFactory.create_async()
        track_db = await TrackModelFactory.create_async(user_id=user_db.id)
        assert track_db.user_id == user_db.id
