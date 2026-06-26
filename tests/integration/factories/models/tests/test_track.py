import uuid

import pytest

from tests.integration.factories.models.track import TrackModelFactory
from tests.integration.factories.models.user import UserModelFactory


class TestTrackModelFactory:
    async def test__user__default(self) -> None:
        track_db = await TrackModelFactory.create_async()
        assert track_db.user_id is not None

    async def test__user__provided(self) -> None:
        user_db = await UserModelFactory.create_async()
        track_db = await TrackModelFactory.create_async(user_id=user_db.id)
        assert track_db.user_id == user_db.id

    async def test__get_or_create__get(self) -> None:
        track_existing_db = await TrackModelFactory.create_async()

        track_db, created = await TrackModelFactory.get_or_create(
            user_id=track_existing_db.user_id,
            fingerprint=track_existing_db.fingerprint,
        )
        assert track_db.id == track_existing_db.id
        assert track_db.fingerprint == track_existing_db.fingerprint
        assert created is False

    async def test__get_or_create__create(self) -> None:
        user_db = await UserModelFactory.create_async()
        fingerprint = str(uuid.uuid4())

        track_db, created = await TrackModelFactory.get_or_create(
            user_id=user_db.id,
            fingerprint=fingerprint,
        )
        assert track_db.id is not None
        assert track_db.fingerprint == fingerprint
        assert created is True

    @pytest.mark.parametrize(
        ("user_id", "fingerprint"),
        [
            ("", ""),
            ("foo-bar-baz", ""),
            ("", "foo-bar-baz"),
        ],
    )
    async def test__get_or_create__exception(self, user_id: uuid.UUID, fingerprint: str) -> None:
        with pytest.raises(ValueError, match="You must provide 'user_id' and 'fingerprint' for uniqueness."):
            await TrackModelFactory.get_or_create(user_id=user_id, fingerprint=fingerprint)
