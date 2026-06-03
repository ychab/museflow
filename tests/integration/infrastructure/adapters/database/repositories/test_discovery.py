import uuid

from sqlalchemy import func
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import pytest

from museflow.application.ports.repositories.discovery import DiscoveryPlaylistRepository
from museflow.domain.entities.user import User
from museflow.domain.exceptions import DiscoveryPlaylistNotFoundError
from museflow.infrastructure.adapters.database.models.discovery import DiscoveryPlaylist as DiscoveryPlaylistModel
from museflow.infrastructure.adapters.database.models.discovery import (
    DiscoveryPlaylistTrack as DiscoveryPlaylistTrackModel,
)

from tests.integration.factories.models.discovery import DiscoveryPlaylistModelFactory
from tests.integration.factories.models.discovery import DiscoveryPlaylistTrackModelFactory
from tests.integration.factories.models.taste import TasteProfileModelFactory
from tests.unit.factories.entities.discovery import DiscoveryPlaylistFactory
from tests.unit.factories.entities.discovery import DiscoveryPlaylistTrackFactory


class TestDiscoveryPlaylistSQLRepository:
    async def test__save__creates_playlist_and_tracks(
        self,
        async_session_db: AsyncSession,
        user: User,
        discovery_playlist_repository: DiscoveryPlaylistRepository,
    ) -> None:
        taste_profile_db = await TasteProfileModelFactory.create_async(user_id=user.id)

        playlist_id = uuid.uuid4()
        track = DiscoveryPlaylistTrackFactory.build(
            playlist_id=playlist_id,
            position=0,
            artist_names=["Test Artist"],
        )
        playlist = DiscoveryPlaylistFactory.build(
            id=playlist_id,
            user_id=user.id,
            profile_id=taste_profile_db.id,
            tracks=[track],
        )

        saved = await discovery_playlist_repository.save(playlist)

        assert saved.id == playlist.id
        assert saved.user_id == user.id
        assert saved.name == playlist.name

        playlist_count = (
            await async_session_db.execute(
                select(func.count())
                .select_from(DiscoveryPlaylistModel)
                .where(DiscoveryPlaylistModel.id == playlist.id)
            )
        ).scalar()
        assert playlist_count == 1

        track_count = (
            await async_session_db.execute(
                select(func.count())
                .select_from(DiscoveryPlaylistTrackModel)
                .where(DiscoveryPlaylistTrackModel.playlist_id == playlist.id)
            )
        ).scalar()
        assert track_count == 1

    async def test__save__includes_tracks_in_result(
        self,
        user: User,
        discovery_playlist_repository: DiscoveryPlaylistRepository,
    ) -> None:
        taste_profile_db = await TasteProfileModelFactory.create_async(user_id=user.id)

        playlist_id = uuid.uuid4()
        track_1 = DiscoveryPlaylistTrackFactory.build(playlist_id=playlist_id, position=0, artist_names=["Artist One"])
        track_2 = DiscoveryPlaylistTrackFactory.build(playlist_id=playlist_id, position=1, artist_names=["Artist Two"])
        playlist = DiscoveryPlaylistFactory.build(
            id=playlist_id,
            user_id=user.id,
            profile_id=taste_profile_db.id,
            tracks=[track_1, track_2],
        )

        saved = await discovery_playlist_repository.save(playlist)

        assert len(saved.tracks) == 2

    async def test__list__returns_playlists_ordered_desc(
        self,
        user: User,
        discovery_playlist_repository: DiscoveryPlaylistRepository,
    ) -> None:
        pl_older = await DiscoveryPlaylistModelFactory.create_async(user_id=user.id)
        pl_newer = await DiscoveryPlaylistModelFactory.create_async(user_id=user.id)

        playlists = await discovery_playlist_repository.list(user.id)

        assert len(playlists) >= 2
        ids = [p.id for p in playlists]
        assert pl_newer.id in ids
        assert pl_older.id in ids
        # Newer should appear before older
        assert ids.index(pl_newer.id) < ids.index(pl_older.id)

    async def test__list__returns_empty_for_unknown_user(
        self,
        discovery_playlist_repository: DiscoveryPlaylistRepository,
    ) -> None:
        playlists = await discovery_playlist_repository.list(uuid.uuid4())
        assert playlists == []

    async def test__list__tracks_not_included(
        self,
        user: User,
        discovery_playlist_repository: DiscoveryPlaylistRepository,
    ) -> None:
        pl_db = await DiscoveryPlaylistModelFactory.create_async(user_id=user.id)
        await DiscoveryPlaylistTrackModelFactory.create_async(playlist_id=pl_db.id)

        playlists = await discovery_playlist_repository.list(user.id)

        matching = [p for p in playlists if p.id == pl_db.id]
        assert len(matching) == 1
        assert matching[0].tracks == []

    async def test__get__returns_playlist_with_tracks(
        self,
        user: User,
        discovery_playlist_repository: DiscoveryPlaylistRepository,
    ) -> None:
        pl_db = await DiscoveryPlaylistModelFactory.create_async(user_id=user.id)
        track_db = await DiscoveryPlaylistTrackModelFactory.create_async(playlist_id=pl_db.id, position=0)

        result = await discovery_playlist_repository.get(user.id, pl_db.id)

        assert result is not None
        assert result.id == pl_db.id
        assert len(result.tracks) == 1
        assert result.tracks[0].id == track_db.id

    async def test__get__returns_none_when_not_found(
        self,
        user: User,
        discovery_playlist_repository: DiscoveryPlaylistRepository,
    ) -> None:
        result = await discovery_playlist_repository.get(user.id, uuid.uuid4())
        assert result is None

    async def test__get__returns_none_for_wrong_user(
        self,
        user: User,
        discovery_playlist_repository: DiscoveryPlaylistRepository,
    ) -> None:
        pl_db = await DiscoveryPlaylistModelFactory.create_async(user_id=user.id)

        result = await discovery_playlist_repository.get(uuid.uuid4(), pl_db.id)
        assert result is None

    async def test__rate_track__updates_score(
        self,
        async_session_db: AsyncSession,
        user: User,
        discovery_playlist_repository: DiscoveryPlaylistRepository,
    ) -> None:
        pl_db = await DiscoveryPlaylistModelFactory.create_async(user_id=user.id)
        track_db = await DiscoveryPlaylistTrackModelFactory.create_async(playlist_id=pl_db.id, position=0)

        await discovery_playlist_repository.rate_track(user.id, track_db.id, 7)

        await async_session_db.refresh(track_db)
        assert track_db.score == 7

    async def test__rate_track__raises_when_track_not_found(
        self,
        user: User,
        discovery_playlist_repository: DiscoveryPlaylistRepository,
    ) -> None:
        with pytest.raises(DiscoveryPlaylistNotFoundError):
            await discovery_playlist_repository.rate_track(user.id, uuid.uuid4(), 5)
