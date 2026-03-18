import asyncio
import dataclasses
import operator

from sqlalchemy import func
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import pytest

from museflow.application.ports.repositories.music import ArtistRepository
from museflow.application.ports.repositories.music import TrackRepository
from museflow.domain.entities.music import Artist
from museflow.domain.entities.music import Track
from museflow.domain.entities.music import TrackArtist
from museflow.domain.entities.user import User
from museflow.domain.types import SortOrder
from museflow.domain.types import TrackOrderBy
from museflow.domain.types import TrackSource
from museflow.infrastructure.adapters.database.models import Artist as ArtistModel
from museflow.infrastructure.adapters.database.models import ArtistDict
from museflow.infrastructure.adapters.database.models import Track as TrackModel

from tests.integration.factories.models.music import ArtistModelFactory
from tests.integration.factories.models.music import TrackModelFactory
from tests.unit.factories.entities.music import ArtistFactory
from tests.unit.factories.entities.music import TrackFactory


class TestArtistSQLRepository:
    @pytest.fixture
    async def artists(self, user: User) -> list[Artist]:
        artists_db = await ArtistModelFactory.create_batch_async(size=10, user_id=user.id)
        return [artist_db.to_entity() for artist_db in artists_db]

    @pytest.fixture
    async def artists_other(self) -> list[Artist]:
        artists_db = await ArtistModelFactory.create_batch_async(size=2)
        return [artist_db.to_entity() for artist_db in artists_db]

    @pytest.fixture
    def artists_create(self, user: User) -> list[Artist]:
        return ArtistFactory.batch(size=10, user_id=user.id)

    @pytest.fixture
    def artists_update(self, artists: list[Artist]) -> list[Artist]:
        return [dataclasses.replace(artist, genres=["foo"]) for artist in artists]

    @pytest.fixture
    def artists_mix(self, user: User, artists: list[Artist]) -> list[Artist]:
        return [
            *ArtistFactory.batch(size=5, user_id=user.id),  # 5 created
            *[dataclasses.replace(artist, genres=["foo"]) for artist in artists[:5]],  # 5 updated
        ]

    @pytest.fixture
    async def artists_delete(self, user: User) -> list[Artist]:
        artists_user = await ArtistModelFactory.create_batch_async(size=3, user_id=user.id)
        artists_others = await ArtistModelFactory.create_batch_async(size=2)

        return [artist_db.to_entity() for artist_db in artists_user + artists_others]

    @pytest.mark.parametrize(("offset", "limit"), [(None, None), (2, 5)])
    async def test__get_list__nominal(
        self,
        user: User,
        offset: int | None,
        limit: int | None,
        artists: list[Artist],
        artists_other: list[Artist],
        artist_repository: ArtistRepository,
    ) -> None:
        artists_expected = artists[offset : offset + limit] if offset is not None and limit is not None else artists

        artist_list = await artist_repository.get_list(user.id, offset=offset, limit=limit)

        # Check that we have the expected items.
        assert len(artist_list) == len(artists_expected)
        assert sorted([a.provider_id for a in artist_list]) == sorted([str(a.provider_id) for a in artists_expected])

        # Check that items have been collected only for that user.
        assert set([a.user_id for a in artist_list]) == {user.id}

    async def test__get_list__none(self, user: User, artist_repository: ArtistRepository) -> None:
        artist_list = await artist_repository.get_list(user.id)
        assert len(artist_list) == 0

    async def test__bulk_upsert__create(
        self,
        async_session_db: AsyncSession,
        user: User,
        artists_create: list[Artist],
        artist_repository: ArtistRepository,
    ) -> None:
        artist_ids, create_count = await artist_repository.bulk_upsert(
            artists_create,
            batch_size=int(len(artists_create) / 5),
        )

        # Check that we have the expected number of items.
        assert len(artist_ids) == len(artists_create) == create_count == 10

        # Check that objects has been really created in DB.
        stmt = select(ArtistModel).where(ArtistModel.id.in_(artist_ids))
        results = await async_session_db.execute(stmt)
        artists_db = results.scalars().all()
        assert len(artists_db) == len(artist_ids)

        # Check that items have been created only for that user.
        assert set([a.user_id for a in artists_db]) == {user.id}
        # Check that at least one field was inserted as expected.
        assert sorted([a.provider_id for a in artists_db]) == sorted([str(a.provider_id) for a in artists_create])

    async def test__bulk_upsert__update(
        self,
        async_session_db: AsyncSession,
        user: User,
        artists: list[Artist],
        artists_update: list[Artist],
        artist_repository: ArtistRepository,
    ) -> None:
        artist_ids, create_count = await artist_repository.bulk_upsert(
            artists_update,
            batch_size=int(len(artists_update) / 5),
        )

        # Check that we have the expected number of items.
        assert len(artist_ids) == len(artists_update) == len(artists) == 10
        assert create_count == 0

        # Check that objects has been really updated in DB.
        stmt = select(ArtistModel).where(ArtistModel.id.in_(artist_ids))
        results = await async_session_db.execute(stmt)
        artists_db = results.scalars().all()
        assert len(artists_db) == len(artists_update)

        # Check that items have been created only for that user.
        assert set([a.user_id for a in artists_db]) == {user.id}
        # Check that at least one field was updated as expected.
        assert set([artist_db.genres[0] for artist_db in artists_db]) == {"foo"}

    async def test__bulk_upsert__both(
        self,
        async_session_db: AsyncSession,
        user: User,
        artists_mix: list[Artist],
        artist_repository: ArtistRepository,
    ) -> None:
        artist_ids, create_count = await artist_repository.bulk_upsert(artists_mix, 300)

        # Check that we have the expected number of items.
        assert len(artist_ids) == len(artists_mix) == 10
        assert create_count == 5

        # Check that objects has been really updated in DB.
        stmt = select(ArtistModel).where(ArtistModel.id.in_(artist_ids)).order_by(ArtistModel.created_at.asc())
        results = await async_session_db.execute(stmt)
        artists_db = results.scalars().all()
        assert len(artists_db) == len(artists_mix)

        # Check that items have been upserted only for that user.
        assert set([a.user_id for a in artists_db]) == {user.id}

        # Check created as expected.
        assert sorted([a.provider_id for a in artists_db[:5]]) == sorted([str(a.provider_id) for a in artists_mix[:5]])
        # Check updated as expected.
        assert set([a.genres[0] for a in artists_db[5:]]) == {"foo"}

    async def test__purge(
        self,
        async_session_db: AsyncSession,
        user: User,
        artists_delete: list[Artist],
        artist_repository: ArtistRepository,
    ) -> None:
        count = await artist_repository.purge(user.id)
        assert count == 3

        # Check if all artists have been deleted for that user.
        stmt = select(func.count()).select_from(ArtistModel).where(ArtistModel.user_id == user.id)
        results = await async_session_db.execute(stmt)
        assert results.scalar() == 0

        # Be sure to keep other users items!
        stmt = select(func.count()).select_from(ArtistModel).where(ArtistModel.user_id != user.id)
        results = await async_session_db.execute(stmt)
        assert results.scalar() == 2


class TestTrackSQLRepository:
    @pytest.fixture
    async def tracks(self, user: User) -> list[Track]:
        tracks_db = await TrackModelFactory.create_batch_async(size=10, user_id=user.id)
        return [track_db.to_entity() for track_db in tracks_db]

    @pytest.fixture
    async def tracks_other(self) -> list[Track]:
        tracks_db = await TrackModelFactory.create_batch_async(size=2)
        return [track_db.to_entity() for track_db in tracks_db]

    @pytest.fixture
    def tracks_create(self, user: User) -> list[Track]:
        return TrackFactory.batch(size=10, user_id=user.id)

    @pytest.fixture
    def tracks_update(self, tracks) -> list[Track]:
        return [dataclasses.replace(track, artists=[TrackArtist(name="SCH", provider_id="foo")]) for track in tracks]

    @pytest.fixture
    def tracks_mix(self, user: User, tracks) -> list[Track]:
        return [
            # 5 created
            *TrackFactory.batch(size=5, user_id=user.id),
            # 5 updated
            *[
                dataclasses.replace(track, artists=[TrackArtist(name="SCH", provider_id="foo")])
                for track in tracks[:5]
            ],
        ]

    @pytest.fixture
    async def tracks_delete(self, user: User) -> list[Track]:
        tracks_top = await TrackModelFactory.create_batch_async(size=4, user_id=user.id, sources=TrackSource.TOP)
        tracks_saved = await TrackModelFactory.create_batch_async(
            size=3,
            user_id=user.id,
            sources=TrackSource.SAVED,
        )
        tracks_playlist = await TrackModelFactory.create_batch_async(
            size=2,
            user_id=user.id,
            sources=TrackSource.PLAYLIST,
        )
        tracks_multi = await TrackModelFactory.create_batch_async(
            size=1,
            user_id=user.id,
            sources=TrackSource.TOP | TrackSource.SAVED,
        )
        tracks_other = await TrackModelFactory.create_batch_async(size=1)

        return [
            track.to_entity() for track in tracks_top + tracks_saved + tracks_playlist + tracks_multi + tracks_other
        ]

    async def test__get_list__none(self, user: User, track_repository: TrackRepository) -> None:
        track_list = await track_repository.get_list(user.id)
        assert len(track_list) == 0

    @pytest.mark.parametrize(
        "sources",
        [
            pytest.param(TrackSource.TOP, id="top_only"),
            pytest.param(TrackSource.SAVED, id="saved_only"),
            pytest.param(TrackSource.PLAYLIST, id="playlist_only"),
            pytest.param(TrackSource.TOP | TrackSource.SAVED, id="top_and_saved"),
            pytest.param(TrackSource.TOP | TrackSource.PLAYLIST, id="top_and_playlist"),
            pytest.param(TrackSource.SAVED | TrackSource.PLAYLIST, id="saved_and_playlist"),
            pytest.param(TrackSource.TOP | TrackSource.SAVED | TrackSource.PLAYLIST, id="all_explicit"),
            pytest.param(None, id="all_implicit"),
        ],
    )
    async def test__get_list__filtering(
        self,
        user: User,
        sources: TrackSource | None,
        tracks_other: list[Track],
        track_repository: TrackRepository,
    ) -> None:
        top_tracks = await TrackModelFactory.create_batch_async(size=2, user_id=user.id, sources=TrackSource.TOP)
        saved_tracks = await TrackModelFactory.create_batch_async(size=2, user_id=user.id, sources=TrackSource.SAVED)
        playlist_tracks = await TrackModelFactory.create_batch_async(
            size=2,
            user_id=user.id,
            sources=TrackSource.PLAYLIST,
        )

        expected_tracks = [
            t for t in top_tracks + saved_tracks + playlist_tracks if sources is None or (t.sources & sources)
        ]

        track_list = await track_repository.get_list(user.id, sources=sources)

        # Check that we have the expected items.
        assert len(track_list) == len(expected_tracks)
        assert {t.id for t in track_list} == {t.id for t in expected_tracks}

    async def test__get_list__filtering__genres__track(self, user: User, track_repository: TrackRepository) -> None:
        track_user_db = await TrackModelFactory.create_async(user_id=user.id, genres=["rock", "pop"])

        # Track with the same genre for another user
        await TrackModelFactory.create_async(genres=["rock"])

        # Track with no matching genres anywhere
        await TrackModelFactory.create_async(
            user_id=user.id,
            genres=["classical"],
        )

        # Test filtering by track genre directly
        tracks_rock = await track_repository.get_list(user.id, genres=["rock"])
        assert len(tracks_rock) == 1
        assert tracks_rock[0].id == track_user_db.id

        # Test multiple genres (OR logic)
        tracks_both = await track_repository.get_list(user.id, genres=["rock", "pop"])
        assert len(tracks_both) == 1
        assert tracks_both[0].id == track_user_db.id

        # Test no match
        tracks_none = await track_repository.get_list(user.id, genres=["metal"])
        assert len(tracks_none) == 0

    async def test__get_list__filtering__genres__artists(self, user: User, track_repository: TrackRepository) -> None:
        # Track with an artist having the genre for the user
        artist_user_db = await ArtistModelFactory.create_async(
            user_id=user.id, genres=["rock", "pop"], provider_id="foo"
        )
        track_user_db = await TrackModelFactory.create_async(
            user_id=user.id,
            artists=[ArtistDict(name="Foo", provider_id=artist_user_db.provider_id)],
            genres=[],
        )

        # Track with an artist having the same genre for another user
        artist_other_db = await ArtistModelFactory.create_async(genres=["rock", "pop"], provider_id="foo")
        await TrackModelFactory.create_async(
            artists=[ArtistDict(name="Foo", provider_id=artist_other_db.provider_id)],
            genres=[],
        )

        # Track with no matching genres anywhere
        artist_other_genre = await ArtistModelFactory.create_async(genres=["classic"], provider_id="baz")
        await TrackModelFactory.create_async(
            user_id=user.id,
            artists=[ArtistDict(name="Classic", provider_id=artist_other_genre.provider_id)],
        )

        # Test filtering by artist genre
        tracks = await track_repository.get_list(user.id, genres=["rock"])
        assert len(tracks) == 1
        assert tracks[0].id == track_user_db.id

        # Test multiple genres (OR logic)
        tracks = await track_repository.get_list(user.id, genres=["rock", "pop"])
        assert len(tracks) == 1
        assert tracks[0].id == track_user_db.id

        # Test no match
        tracks = await track_repository.get_list(user.id, genres=["metal"])
        assert len(tracks) == 0

    async def test__get_list__filtering__genres__track_and_artists(
        self,
        user: User,
        track_repository: TrackRepository,
    ) -> None:
        # Track with explicit genre
        track_genre = await TrackModelFactory.create_async(user_id=user.id, genres=["rock"])

        # Track with an artist having the genre
        artist_genre = await ArtistModelFactory.create_async(
            user_id=user.id, genres=["jazz"], provider_id="artist-jazz"
        )
        track_artist_genre = await TrackModelFactory.create_async(
            user_id=user.id,
            artists=[ArtistDict(name="Jazzman", provider_id=artist_genre.provider_id)],
            genres=[],
        )

        # Track for another user to ensure it's not fetched
        await TrackModelFactory.create_async(genres=["rock"])
        artist_other = await ArtistModelFactory.create_async(genres=["jazz"], provider_id="artist-jazz-other")
        await TrackModelFactory.create_async(
            artists=[ArtistDict(name="Other Jazzman", provider_id=artist_other.provider_id)],
        )

        # Test filtering by both track and artist genres
        tracks_both = await track_repository.get_list(user.id, genres=["rock", "jazz"])
        assert len(tracks_both) == 2
        assert {t.id for t in tracks_both} == {track_genre.id, track_artist_genre.id}

    @pytest.mark.parametrize("order_by", [o for o in TrackOrderBy if o != TrackOrderBy.RANDOM])
    @pytest.mark.parametrize("sort_order", list(SortOrder))
    async def test__get_list__ordering(
        self,
        user: User,
        order_by: TrackOrderBy,
        sort_order: SortOrder,
        tracks_other: list[Track],
        track_repository: TrackRepository,
    ) -> None:
        t1 = await TrackModelFactory.create_async(user_id=user.id, popularity=10, top_position=3)
        await asyncio.sleep(0.01)

        t2 = await TrackModelFactory.create_async(user_id=user.id, popularity=50, top_position=2)
        await asyncio.sleep(0.01)

        t3 = await TrackModelFactory.create_async(user_id=user.id, popularity=90, top_position=1)

        tracks = [t1, t2, t3]

        key_func = None
        match order_by:
            case TrackOrderBy.CREATED_AT:
                key_func = operator.attrgetter("created_at")
            case TrackOrderBy.UPDATED_AT:
                key_func = operator.attrgetter("updated_at")
            case TrackOrderBy.POPULARITY:
                key_func = operator.attrgetter("popularity")
            case TrackOrderBy.TOP_POSITION:
                key_func = operator.attrgetter("top_position")
            case _:
                pytest.fail(f"Unhandled sort key: {order_by}")

        expected_tracks = sorted(tracks, key=key_func, reverse=(sort_order == SortOrder.DESC))

        track_list = await track_repository.get_list(user.id, order_by=order_by, sort_order=sort_order)

        # Check that we have the expected items.
        assert len(track_list) == len(expected_tracks)
        assert [t.id for t in track_list] == [t.id for t in expected_tracks]

    async def test__get_list__ordering__random(
        self,
        user: User,
        tracks_other: list[Track],
        track_repository: TrackRepository,
    ) -> None:
        tracks = await TrackModelFactory.create_batch_async(size=10, user_id=user.id)
        track_ids = {t.id for t in tracks}

        random_list_1 = await track_repository.get_list(user.id, order_by=TrackOrderBy.RANDOM)
        random_list_2 = await track_repository.get_list(user.id, order_by=TrackOrderBy.RANDOM)

        assert len(random_list_1) == len(random_list_2) == 10
        assert {t.id for t in random_list_1} == {t.id for t in random_list_2} == track_ids

        # There is a "tiny chance" (1 in 10! ~= 1 in 3.6 million) this fails... If it happens, I will be a millionaire!
        assert [t.id for t in random_list_1] != [t.id for t in random_list_2]

    @pytest.mark.parametrize(("offset", "limit"), [(None, None), (2, 5)])
    async def test__get_list__pagination(
        self,
        user: User,
        offset: int | None,
        limit: int | None,
        tracks: list[Track],
        tracks_other: list[Track],
        track_repository: TrackRepository,
    ) -> None:
        tracks_expected = tracks[offset : offset + limit] if offset is not None and limit is not None else tracks

        track_list = await track_repository.get_list(user.id, offset=offset, limit=limit)

        # Check that we have the expected items.
        assert len(track_list) == len(tracks_expected)
        assert set([t.provider_id for t in track_list]).issubset([t.provider_id for t in tracks])
        assert sorted([t.provider_id for t in track_list]) == sorted([str(t.provider_id) for t in tracks_expected])

        # Check that items have been collected only for that user.
        assert set([t.user_id for t in track_list]) == {user.id}

    async def test__get_known_identifiers__none(self, user: User, track_repository: TrackRepository) -> None:
        known_identifiers = await track_repository.get_known_identifiers(
            user_id=user.id,
            isrcs=[],
            fingerprints=[],
        )
        assert not known_identifiers.isrcs
        assert not known_identifiers.fingerprints

    async def test__get_known_identifiers__isrc(self, user: User, track_repository: TrackRepository) -> None:
        await TrackModelFactory.create_async(user_id=user.id, isrc="foo", fingerprint="")
        await TrackModelFactory.create_async(user_id=user.id, isrc="bar", fingerprint="")
        await TrackModelFactory.create_async(user_id=user.id, isrc="baz", fingerprint="")
        # Another user
        await TrackModelFactory.create_async(isrc="bar", fingerprint="")

        known_identifiers = await track_repository.get_known_identifiers(
            user_id=user.id,
            isrcs=["foo", "bar"],
            fingerprints=["baz"],
        )

        assert known_identifiers.isrcs == frozenset(["foo", "bar"])
        assert not known_identifiers.fingerprints

    async def test__get_known_identifiers__fingerprint(self, user: User, track_repository: TrackRepository) -> None:
        await TrackModelFactory.create_async(user_id=user.id, isrc=None, fingerprint="foo")
        await TrackModelFactory.create_async(user_id=user.id, isrc=None, fingerprint="bar")
        await TrackModelFactory.create_async(user_id=user.id, isrc=None, fingerprint="baz")
        # Another user
        await TrackModelFactory.create_async(isrc=None, fingerprint="bar")

        known_identifiers = await track_repository.get_known_identifiers(
            user_id=user.id,
            isrcs=[],
            fingerprints=["foo", "bar"],
        )

        assert not known_identifiers.isrcs
        assert known_identifiers.fingerprints == frozenset(["foo", "bar"])

    async def test__get_known_identifiers__both(self, user: User, track_repository: TrackRepository) -> None:
        await TrackModelFactory.create_async(user_id=user.id, isrc="foo", fingerprint="foo")
        await TrackModelFactory.create_async(user_id=user.id, isrc="bar", fingerprint="bar")
        await TrackModelFactory.create_async(user_id=user.id, isrc="baz", fingerprint="baz")
        # Another user
        await TrackModelFactory.create_async(isrc="bar", fingerprint="bar")

        known_identifiers = await track_repository.get_known_identifiers(
            user_id=user.id,
            isrcs=["foo", "bar"],
            fingerprints=["baz"],
        )

        assert not known_identifiers.isrcs == frozenset(["foo", "bar"])
        assert known_identifiers.fingerprints == frozenset(["foo", "bar", "baz"])

    async def test__get_distinct_genres__nominal(self, user: User, track_repository: TrackRepository) -> None:
        # Track with genres
        await TrackModelFactory.create_async(user_id=user.id, genres=["rock", "indie"])

        # Artist with genres (one overlapping, one new)
        artist = await ArtistModelFactory.create_async(user_id=user.id, genres=["rock", "alternative"])
        await TrackModelFactory.create_async(
            user_id=user.id,
            artists=[ArtistDict(name="Rock alt", provider_id=artist.provider_id)],
            genres=[],
        )

        # Artist with genres (one overlapping, one new)
        await TrackModelFactory.create_async(genres=["pop"])
        other_artist = await ArtistModelFactory.create_async(genres=["classic"])
        await TrackModelFactory.create_async(
            artists=[ArtistDict(name="Rock alt", provider_id=other_artist.provider_id)],
            genres=[],
        )

        genres = await track_repository.get_distinct_genres(user.id)
        assert sorted(genres) == ["alternative", "indie", "rock"]

    async def test__get_distinct_genres__empty(self, user: User, track_repository: TrackRepository) -> None:
        genres = await track_repository.get_distinct_genres(user.id)
        assert genres == []

    async def test__bulk_upsert__create(
        self,
        async_session_db: AsyncSession,
        user: User,
        tracks_create: list[Track],
        track_repository: TrackRepository,
    ) -> None:
        track_ids, create_count = await track_repository.bulk_upsert(
            tracks_create,
            batch_size=int(len(tracks_create) / 5),
        )

        # Check that we have the expected number of items.
        assert len(track_ids) == len(tracks_create) == create_count == 10

        # Check that objects has been really created in DB.
        stmt = select(TrackModel).where(TrackModel.id.in_(track_ids))
        results = await async_session_db.execute(stmt)
        tracks_db = results.scalars().all()

        assert len(tracks_db) == len(track_ids)
        assert set([t.user_id for t in tracks_db]) == {user.id}
        assert sorted([t.provider_id for t in tracks_db]) == sorted([str(t.provider_id) for t in tracks_create])

    async def test__bulk_upsert__update(
        self,
        async_session_db: AsyncSession,
        user: User,
        tracks: list[Track],
        tracks_update: list[Track],
        track_repository: TrackRepository,
    ) -> None:
        track_ids, create_count = await track_repository.bulk_upsert(
            tracks_update,
            batch_size=int(len(tracks_update) / 5),
        )

        # Check that we have the expected number of items.
        assert len(track_ids) == len(tracks_update) == len(tracks) == 10
        assert create_count == 0

        # Check that objects has been really updated in DB.
        stmt = select(TrackModel).where(TrackModel.id.in_(track_ids))
        results = await async_session_db.execute(stmt)
        tracks_db = results.scalars().all()

        assert len(tracks_db) == len(tracks_update)
        assert set([t.user_id for t in tracks_db]) == {user.id}

        artists = [track_db.artists[0] for track_db in tracks_db]
        expected_artists = [{"name": "SCH", "provider_id": "foo"} for _ in range(len(tracks_db))]
        assert artists == expected_artists

    async def test__bulk_upsert__both(
        self,
        async_session_db: AsyncSession,
        user: User,
        tracks_mix: list[Track],
        track_repository: TrackRepository,
    ) -> None:
        track_ids, create_count = await track_repository.bulk_upsert(tracks_mix, 300)

        # Check that we have the expected number of items.
        assert len(track_ids) == len(tracks_mix) == 10
        assert create_count == 5

        # Check that objects has been really updated in DB.
        stmt = select(TrackModel).where(TrackModel.id.in_(track_ids)).order_by(TrackModel.created_at.asc())
        results = await async_session_db.execute(stmt)
        tracks_db = results.scalars().all()
        assert len(tracks_db) == len(tracks_mix)
        assert set([t.user_id for t in tracks_db]) == {user.id}

        # Check created as expected.
        assert sorted([t.provider_id for t in tracks_db[:5]]) == sorted([str(t.provider_id) for t in tracks_mix[:5]])
        # Check updated as expected.
        artists = [track_db.artists[0] for track_db in tracks_db[5:]]
        expected_artists = [{"name": "SCH", "provider_id": "foo"} for _ in range(len(tracks_db[5:]))]
        assert artists == expected_artists

    async def test__bulk_upsert__sources_are_accumulated(
        self,
        user: User,
        track_repository: TrackRepository,
        async_session_db: AsyncSession,
    ) -> None:
        track = TrackFactory.build(user_id=user.id, sources=TrackSource.TOP)
        await track_repository.bulk_upsert([track], batch_size=1)

        # The same track, but now coming from saved sync
        track = dataclasses.replace(track, sources=TrackSource.SAVED)
        await track_repository.bulk_upsert([track], batch_size=1)

        stmt = select(TrackModel).where(TrackModel.id == track.id)
        tracks_db = (await async_session_db.execute(stmt)).scalar_one()
        assert tracks_db.sources == TrackSource.TOP | TrackSource.SAVED

    @pytest.mark.parametrize(
        ("sources", "expected_deleted", "expected_remaining_user"),
        [
            pytest.param(TrackSource.TOP, 4, 3 + 2 + 1, id="top_only"),
            pytest.param(TrackSource.SAVED, 3, 4 + 2 + 1, id="saved_only"),
            pytest.param(TrackSource.PLAYLIST, 2, 4 + 3 + 1, id="playlist_only"),
            pytest.param(TrackSource.TOP | TrackSource.SAVED, 4 + 3 + 1, 2, id="top_and_saved"),
            pytest.param(TrackSource.TOP | TrackSource.PLAYLIST, 4 + 2, 3 + 1, id="top_and_playlist"),
            pytest.param(TrackSource.SAVED | TrackSource.PLAYLIST, 3 + 2, 4 + 1, id="saved_and_playlist"),
            pytest.param(
                TrackSource.TOP | TrackSource.SAVED | TrackSource.PLAYLIST,
                4 + 3 + 2 + 1,
                0,
                id="all_explicit",
            ),
            pytest.param(None, 4 + 3 + 2 + 1, 0, id="all_implicit"),
        ],
    )
    async def test__purge(
        self,
        async_session_db: AsyncSession,
        user: User,
        tracks_delete: list[Track],
        sources: TrackSource | None,
        expected_deleted: int,
        expected_remaining_user: int,
        track_repository: TrackRepository,
    ) -> None:
        count = await track_repository.purge(user.id, sources=sources)
        assert count == expected_deleted

        stmt = select(func.count()).select_from(TrackModel).where(TrackModel.user_id == user.id)
        results = await async_session_db.execute(stmt)
        assert results.scalar() == expected_remaining_user

        stmt = select(func.count()).select_from(TrackModel).where(TrackModel.user_id != user.id)
        results = await async_session_db.execute(stmt)
        assert results.scalar() == 1

    async def test__purge__clear_bits_only(
        self,
        async_session_db: AsyncSession,
        user: User,
        track_repository: TrackRepository,
    ) -> None:
        track = await TrackModelFactory.create_async(
            user_id=user.id,
            sources=TrackSource.TOP | TrackSource.SAVED,
        )
        track_id = track.id

        count = await track_repository.purge(user.id, sources=TrackSource.TOP)
        assert count == 0

        stmt = select(TrackModel).where(TrackModel.id == track_id)
        track_cleared_db = (await async_session_db.execute(stmt)).scalar_one()
        assert track_cleared_db.sources == TrackSource.SAVED
