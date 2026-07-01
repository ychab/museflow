import uuid

from sqlalchemy import func
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from museflow.application.ports.repositories.playlist import PlaylistRepository
from museflow.application.ports.repositories.track import TrackRepository
from museflow.domain.entities.user import User
from museflow.domain.enums import MusicProvider
from museflow.domain.enums import PlaylistType
from museflow.infrastructure.adapters.database.models.playlist import Playlist as PlaylistModel
from museflow.infrastructure.adapters.database.models.playlist import PlaylistTrack as PlaylistTrackModel

from tests.integration.factories.models.playlist import PlaylistModelFactory
from tests.integration.factories.models.taste import TasteProfileModelFactory
from tests.integration.factories.models.track import TrackModelFactory
from tests.unit.factories.entities.playlist import PlaylistFactory


class TestPlaylistSQLRepository:
    async def test__save__creates_playlist_and_tracks(
        self,
        async_session_db: AsyncSession,
        user: User,
        track_repository: TrackRepository,
        playlist_repository: PlaylistRepository,
    ) -> None:
        taste_profile_db = await TasteProfileModelFactory.create_async(user_id=user.id)

        # Create a real Track in museflow_track first (FK constraint)
        track_db = await TrackModelFactory.create_async(user_id=user.id)
        track = track_db.to_entity()

        playlist_id = uuid.uuid4()
        playlist = PlaylistFactory.build(
            id=playlist_id,
            user_id=user.id,
            profile_id=taste_profile_db.id,
            tracks=[track],
        )

        saved = await playlist_repository.save(playlist)

        assert saved.id == playlist.id
        assert saved.user_id == user.id
        assert saved.name == playlist.name

        playlist_count = (
            await async_session_db.execute(
                select(func.count()).select_from(PlaylistModel).where(PlaylistModel.id == playlist.id)
            )
        ).scalar()
        assert playlist_count == 1

        track_count = (
            await async_session_db.execute(
                select(func.count())
                .select_from(PlaylistTrackModel)
                .where(PlaylistTrackModel.playlist_id == playlist.id)
            )
        ).scalar()
        assert track_count == 1

    async def test__save__includes_tracks_in_result(
        self,
        user: User,
        playlist_repository: PlaylistRepository,
    ) -> None:
        taste_profile_db = await TasteProfileModelFactory.create_async(user_id=user.id)

        track_db_1 = await TrackModelFactory.create_async(user_id=user.id)
        track_db_2 = await TrackModelFactory.create_async(user_id=user.id)
        track_1 = track_db_1.to_entity()
        track_2 = track_db_2.to_entity()

        playlist_id = uuid.uuid4()
        playlist = PlaylistFactory.build(
            id=playlist_id,
            user_id=user.id,
            profile_id=taste_profile_db.id,
            tracks=[track_1, track_2],
        )

        saved = await playlist_repository.save(playlist)

        assert len(saved.tracks) == 2

    async def test__list__returns_playlists_ordered_desc(
        self,
        user: User,
        playlist_repository: PlaylistRepository,
    ) -> None:
        playlist_older = await PlaylistModelFactory.create_async(user_id=user.id)
        playlist_newer = await PlaylistModelFactory.create_async(user_id=user.id)

        playlists = await playlist_repository.list(user.id)

        assert len(playlists) >= 2
        ids = [p.id for p in playlists]
        assert playlist_newer.id in ids
        assert playlist_older.id in ids
        # Newer should appear before older
        assert ids.index(playlist_newer.id) < ids.index(playlist_older.id)

    async def test__list__returns_empty_for_unknown_user(
        self,
        playlist_repository: PlaylistRepository,
    ) -> None:
        playlists = await playlist_repository.list(uuid.uuid4())
        assert playlists == []

    async def test__list__tracks_not_included(
        self,
        user: User,
        playlist_repository: PlaylistRepository,
    ) -> None:
        # Playlist has a track in the DB, but list() should not hydrate tracks
        track_db = await TrackModelFactory.create_async(user_id=user.id)
        playlist_db = await PlaylistModelFactory.create_async(user_id=user.id, track_ids=[track_db.id])

        playlists = await playlist_repository.list(user.id)

        matching = [p for p in playlists if p.id == playlist_db.id]
        assert len(matching) == 1
        assert matching[0].tracks == []

    async def test__get__returns_playlist_with_tracks(
        self,
        user: User,
        playlist_repository: PlaylistRepository,
    ) -> None:
        track_db = await TrackModelFactory.create_async(user_id=user.id)
        playlist_db = await PlaylistModelFactory.create_async(user_id=user.id, track_ids=[track_db.id])

        result = await playlist_repository.get(user.id, playlist_db.id)

        assert result is not None
        assert result.id == playlist_db.id
        assert len(result.tracks) == 1
        assert result.tracks[0].id == track_db.id

    async def test__get__returns_none_when_not_found(
        self,
        user: User,
        playlist_repository: PlaylistRepository,
    ) -> None:
        result = await playlist_repository.get(user.id, uuid.uuid4())
        assert result is None

    async def test__get__returns_none_for_wrong_user(
        self,
        user: User,
        playlist_repository: PlaylistRepository,
    ) -> None:
        playlist_db = await PlaylistModelFactory.create_async(user_id=user.id)

        result = await playlist_repository.get(uuid.uuid4(), playlist_db.id)
        assert result is None

    async def test__get_track_ids__filters_by_type_and_user(
        self,
        user: User,
        playlist_repository: PlaylistRepository,
    ) -> None:
        history_track_db = await TrackModelFactory.create_async(user_id=user.id)
        discovery_track_db = await TrackModelFactory.create_async(user_id=user.id)
        other_user_track_db = await TrackModelFactory.create_async()

        await PlaylistModelFactory.create_async(
            user_id=user.id, type=PlaylistType.HISTORY, track_ids=[history_track_db.id]
        )
        await PlaylistModelFactory.create_async(
            user_id=user.id, type=PlaylistType.DISCOVERY, track_ids=[discovery_track_db.id]
        )
        await PlaylistModelFactory.create_async(
            user_id=other_user_track_db.user_id, type=PlaylistType.HISTORY, track_ids=[other_user_track_db.id]
        )

        track_ids = await playlist_repository.get_track_ids(user.id, type=PlaylistType.HISTORY)

        assert track_ids == frozenset({history_track_db.id})

    async def test__get_track_ids__distinct_across_playlists(
        self,
        user: User,
        playlist_repository: PlaylistRepository,
    ) -> None:
        track_db = await TrackModelFactory.create_async(user_id=user.id)

        await PlaylistModelFactory.create_async(user_id=user.id, type=PlaylistType.HISTORY, track_ids=[track_db.id])
        await PlaylistModelFactory.create_async(user_id=user.id, type=PlaylistType.HISTORY, track_ids=[track_db.id])

        track_ids = await playlist_repository.get_track_ids(user.id, type=PlaylistType.HISTORY)

        assert track_ids == frozenset({track_db.id})

    async def test__get_track_ids__empty_when_no_match(
        self,
        user: User,
        playlist_repository: PlaylistRepository,
    ) -> None:
        track_ids = await playlist_repository.get_track_ids(user.id, type=PlaylistType.HISTORY)
        assert track_ids == frozenset()

    async def test__delete__deletes_playlist_and_returns_true(
        self,
        async_session_db: AsyncSession,
        user: User,
        playlist_repository: PlaylistRepository,
    ) -> None:
        playlist_db = await PlaylistModelFactory.create_async(user_id=user.id)

        deleted = await playlist_repository.delete(user.id, playlist_db.id)
        assert deleted is True

        playlist_count = (
            await async_session_db.execute(
                select(func.count()).select_from(PlaylistModel).where(PlaylistModel.id == playlist_db.id)
            )
        ).scalar()
        assert playlist_count == 0

        track_count = (
            await async_session_db.execute(
                select(func.count())
                .select_from(PlaylistTrackModel)
                .where(PlaylistTrackModel.playlist_id == playlist_db.id)
            )
        ).scalar()
        assert track_count == 0

    async def test__delete__returns_false_when_not_found(
        self,
        user: User,
        playlist_repository: PlaylistRepository,
    ) -> None:
        deleted = await playlist_repository.delete(user.id, uuid.uuid4())
        assert deleted is False

    async def test__delete__returns_false_for_wrong_user(
        self,
        user: User,
        playlist_repository: PlaylistRepository,
    ) -> None:
        playlist_db = await PlaylistModelFactory.create_async(user_id=user.id)

        deleted = await playlist_repository.delete(uuid.uuid4(), playlist_db.id)

        assert deleted is False

    async def test__purge__deletes_all_for_user(
        self,
        user: User,
        playlist_repository: PlaylistRepository,
    ) -> None:
        await PlaylistModelFactory.create_async(user_id=user.id)
        await PlaylistModelFactory.create_async(user_id=user.id)

        count = await playlist_repository.purge(user.id)

        assert count == 2
        assert await playlist_repository.list(user.id) == []

    async def test__purge__filters_by_type(
        self,
        user: User,
        playlist_repository: PlaylistRepository,
    ) -> None:
        await PlaylistModelFactory.create_async(user_id=user.id, type=PlaylistType.DISCOVERY)

        count = await playlist_repository.purge(user.id, type=PlaylistType.DISCOVERY)

        assert count == 1

    async def test__purge__filters_by_provider(
        self,
        user: User,
        playlist_repository: PlaylistRepository,
    ) -> None:
        await PlaylistModelFactory.create_async(user_id=user.id, provider=MusicProvider.SPOTIFY)

        count = await playlist_repository.purge(user.id, provider=MusicProvider.SPOTIFY)

        assert count == 1

    async def test__purge__returns_zero_when_no_match(
        self,
        playlist_repository: PlaylistRepository,
    ) -> None:
        count = await playlist_repository.purge(uuid.uuid4())
        assert count == 0

    async def test__purge__does_not_affect_other_users(
        self,
        user: User,
        playlist_repository: PlaylistRepository,
    ) -> None:
        playlist_db = await PlaylistModelFactory.create_async()
        await PlaylistModelFactory.create_async(user_id=user.id)

        count = await playlist_repository.purge(user.id)

        assert count == 1
        result = await playlist_repository.get(playlist_db.user_id, playlist_db.id)
        assert result is not None
