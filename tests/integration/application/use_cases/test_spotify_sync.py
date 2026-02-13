import copy
import json
import re
from typing import Any
from typing import Final

from sqlalchemy import func
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import pytest
from pytest_httpx import HTTPXMock

from spotifagent.application.services.spotify import SpotifySessionFactory
from spotifagent.application.use_cases.spotify_sync import SyncReport
from spotifagent.application.use_cases.spotify_sync import spotify_sync
from spotifagent.domain.entities.music import Artist
from spotifagent.domain.entities.music import Track
from spotifagent.domain.entities.users import User
from spotifagent.domain.ports.repositories.music import ArtistRepositoryPort
from spotifagent.domain.ports.repositories.music import TrackRepositoryPort
from spotifagent.infrastructure.adapters.clients.spotify import SpotifyClientAdapter
from spotifagent.infrastructure.adapters.database.models import Artist as ArtistModel
from spotifagent.infrastructure.adapters.database.models import Track as TrackModel

from tests import ASSETS_DIR
from tests.integration.factories.music import ArtistModelFactory
from tests.integration.factories.music import TrackModelFactory
from tests.integration.factories.users import UserModelFactory

DEFAULT_PAGINATION_LIMIT: Final[int] = 5
DEFAULT_PAGINATION_TOTAL: Final[int] = 20


def load_spotify_response(filename: str = "top_artists") -> dict[str, Any]:
    filepath = ASSETS_DIR / "httpmock" / "spotify" / f"{filename}.json"
    return json.loads(filepath.read_text())


def paginate_spotify_response(spotify_response: dict[str, Any]) -> list[dict[str, Any]]:
    response_chunks: list[dict[str, Any]] = []

    offset: int = 0
    limit: int = DEFAULT_PAGINATION_LIMIT
    total: int = DEFAULT_PAGINATION_TOTAL
    while offset + limit <= total:
        response_chunk = copy.deepcopy(spotify_response)
        response_chunk["offset"] = offset
        response_chunk["limit"] = limit
        response_chunk["total"] = total
        response_chunk["items"] = response_chunk["items"][offset : offset + limit]

        response_chunks.append(response_chunk)
        offset += limit

    return response_chunks


class TestSpotifySync:
    @pytest.fixture
    def artists_response(self) -> dict[str, Any]:
        return load_spotify_response(filename="top_artists")

    @pytest.fixture
    def artists_response_paginated(self, artists_response: dict[str, Any]) -> list[dict[str, Any]]:
        return paginate_spotify_response(artists_response)

    @pytest.fixture
    def tracks_response(self) -> dict[str, Any]:
        return load_spotify_response(filename="top_tracks")

    @pytest.fixture
    def tracks_response_paginated(self, tracks_response: dict[str, Any]) -> list[dict[str, Any]]:
        return paginate_spotify_response(tracks_response)

    @pytest.fixture
    async def user(self) -> User:
        user_db = await UserModelFactory.create_async(with_spotify_account=True)
        return User.model_validate(user_db)

    @pytest.fixture
    async def artists_update(
        self,
        request: pytest.FixtureRequest,
        user: User,
        artists_response_paginated: list[dict[str, Any]],
    ) -> list[Artist]:
        page_max = getattr(request, "param", len(artists_response_paginated))
        artists: list[Artist] = []

        for page in artists_response_paginated[:page_max]:
            for item in page["items"]:
                artist = await ArtistModelFactory.create_async(user_id=user.id, provider_id=item["id"])
                artists.append(Artist.model_validate(artist))

        return artists

    @pytest.fixture
    async def artists_delete(self, user: User) -> list[Artist]:
        return [
            Artist.model_validate(artist)
            for artist in await ArtistModelFactory.create_batch_async(size=3, user_id=user.id)
        ]

    @pytest.fixture
    async def tracks_update(
        self,
        request: pytest.FixtureRequest,
        user: User,
        tracks_response_paginated: list[dict[str, Any]],
    ) -> list[Track]:
        page_max = getattr(request, "param", len(tracks_response_paginated))
        tracks: list[Track] = []

        for page in tracks_response_paginated[:page_max]:
            for item in page["items"]:
                track = await TrackModelFactory.create_async(user_id=user.id, provider_id=item["id"])
                tracks.append(Track.model_validate(track))

        return tracks

    @pytest.fixture
    async def tracks_delete(self, user: User) -> list[Track]:
        return [
            Track.model_validate(track)
            for track in await TrackModelFactory.create_batch_async(size=3, user_id=user.id)
        ]

    async def test__artists__purge(
        self,
        async_session_db: AsyncSession,
        user: User,
        artists_delete: list[Artist],
        spotify_session_factory: SpotifySessionFactory,
        artist_repository: ArtistRepositoryPort,
        track_repository: TrackRepositoryPort,
    ) -> None:
        pass
        report = await spotify_sync(
            user=user,
            spotify_session_factory=spotify_session_factory,
            artist_repository=artist_repository,
            track_repository=track_repository,
            purge_artists=True,
        )
        assert report == SyncReport(purge_artist=len(artists_delete))

        stmt = select(func.count()).select_from(ArtistModel).where(ArtistModel.user_id == user.id)
        result = await async_session_db.execute(stmt)
        assert result.scalar() == 0

    async def test__tracks__purge(
        self,
        async_session_db: AsyncSession,
        user: User,
        tracks_delete: list[Track],
        spotify_session_factory: SpotifySessionFactory,
        artist_repository: ArtistRepositoryPort,
        track_repository: TrackRepositoryPort,
    ) -> None:
        report = await spotify_sync(
            user=user,
            spotify_session_factory=spotify_session_factory,
            artist_repository=artist_repository,
            track_repository=track_repository,
            purge_tracks=True,
        )
        assert report == SyncReport(purge_track=len(tracks_delete))

        stmt = select(func.count()).select_from(TrackModel).where(TrackModel.user_id == user.id)
        result = await async_session_db.execute(stmt)
        assert result.scalar() == 0

    async def test__artists__sync__create(
        self,
        async_session_db: AsyncSession,
        user: User,
        spotify_client: SpotifyClientAdapter,
        spotify_session_factory: SpotifySessionFactory,
        artist_repository: ArtistRepositoryPort,
        track_repository: TrackRepositoryPort,
        httpx_mock: HTTPXMock,
        artists_response: dict[str, Any],
        artists_response_paginated: list[dict[str, Any]],
    ) -> None:
        expected_count = len(artists_response["items"])

        url_pattern = re.compile(r".*/me/top/artists.*")
        for response in artists_response_paginated:
            httpx_mock.add_response(
                url=url_pattern,
                method="GET",
                json=response,
            )

        report = await spotify_sync(
            user=user,
            spotify_session_factory=spotify_session_factory,
            artist_repository=artist_repository,
            track_repository=track_repository,
            sync_artists=True,
            page_limit=len(artists_response_paginated),
        )
        assert report == SyncReport(artist_created=expected_count)

        stmt = select(func.count()).select_from(ArtistModel).where(ArtistModel.user_id == user.id)
        result = await async_session_db.execute(stmt)
        assert result.scalar() == expected_count

    async def test__artists__sync__update(
        self,
        async_session_db: AsyncSession,
        user: User,
        artists_update: list[Artist],
        spotify_client: SpotifyClientAdapter,
        spotify_session_factory: SpotifySessionFactory,
        artist_repository: ArtistRepositoryPort,
        track_repository: TrackRepositoryPort,
        httpx_mock: HTTPXMock,
        artists_response_paginated: list[dict[str, Any]],
    ) -> None:
        expected_count = len(artists_update)

        url_pattern = re.compile(r".*/me/top/artists.*")
        for response in artists_response_paginated:
            httpx_mock.add_response(
                url=url_pattern,
                method="GET",
                json=response,
            )

        report = await spotify_sync(
            user=user,
            spotify_session_factory=spotify_session_factory,
            artist_repository=artist_repository,
            track_repository=track_repository,
            sync_artists=True,
            page_limit=len(artists_response_paginated),
        )
        assert report == SyncReport(artist_updated=expected_count)

        stmt = select(ArtistModel).where(ArtistModel.user_id == user.id)
        result = await async_session_db.execute(stmt)
        artists_db = result.scalars().all()

        assert len(artists_db) == expected_count
        assert sorted([a.id for a in artists_db]) == sorted([a.id for a in artists_update])

    async def test__tracks__sync__create(
        self,
        async_session_db: AsyncSession,
        user: User,
        spotify_client: SpotifyClientAdapter,
        spotify_session_factory: SpotifySessionFactory,
        artist_repository: ArtistRepositoryPort,
        track_repository: TrackRepositoryPort,
        httpx_mock: HTTPXMock,
        tracks_response: dict[str, Any],
        tracks_response_paginated: list[dict[str, Any]],
    ) -> None:
        expected_count = len(tracks_response["items"])

        url_pattern = re.compile(r".*/me/top/tracks.*")
        for response in tracks_response_paginated:
            httpx_mock.add_response(
                url=url_pattern,
                method="GET",
                json=response,
            )

        report = await spotify_sync(
            user=user,
            spotify_session_factory=spotify_session_factory,
            artist_repository=artist_repository,
            track_repository=track_repository,
            sync_tracks=True,
            page_limit=len(tracks_response_paginated),
        )
        assert report == SyncReport(track_created=expected_count)

        stmt = select(func.count()).select_from(TrackModel).where(TrackModel.user_id == user.id)
        result = await async_session_db.execute(stmt)
        assert result.scalar() == expected_count

    async def test__tracks__sync__update(
        self,
        async_session_db: AsyncSession,
        user: User,
        tracks_update: list[Track],
        spotify_client: SpotifyClientAdapter,
        spotify_session_factory: SpotifySessionFactory,
        artist_repository: ArtistRepositoryPort,
        track_repository: TrackRepositoryPort,
        httpx_mock: HTTPXMock,
        tracks_response_paginated: list[dict[str, Any]],
    ) -> None:
        expected_count = len(tracks_update)

        url_pattern = re.compile(r".*/me/top/tracks.*")
        for response in tracks_response_paginated:
            httpx_mock.add_response(
                url=url_pattern,
                method="GET",
                json=response,
            )

        report = await spotify_sync(
            user=user,
            spotify_session_factory=spotify_session_factory,
            artist_repository=artist_repository,
            track_repository=track_repository,
            sync_tracks=True,
            page_limit=len(tracks_response_paginated),
        )
        assert report == SyncReport(track_updated=expected_count)

        stmt = select(TrackModel).where(TrackModel.user_id == user.id)
        result = await async_session_db.execute(stmt)
        tracks_db = result.scalars().all()

        assert len(tracks_db) == expected_count
        assert sorted([t.id for t in tracks_db]) == sorted([t.id for t in tracks_update])

    async def test__all__purge__sync(
        self,
        async_session_db: AsyncSession,
        user: User,
        artists_delete: list[Artist],
        tracks_delete: list[Track],
        spotify_client: SpotifyClientAdapter,
        spotify_session_factory: SpotifySessionFactory,
        artist_repository: ArtistRepositoryPort,
        track_repository: TrackRepositoryPort,
        httpx_mock: HTTPXMock,
        artists_response: dict[str, Any],
        artists_response_paginated: list[dict[str, Any]],
        tracks_response: dict[str, Any],
        tracks_response_paginated: list[dict[str, Any]],
    ) -> None:
        url_artist_pattern = re.compile(r".*/me/top/artists.*")
        url_track_pattern = re.compile(r".*/me/top/tracks.*")

        for response in artists_response_paginated:
            httpx_mock.add_response(
                url=url_artist_pattern,
                method="GET",
                json=response,
            )

        for response in tracks_response_paginated:
            httpx_mock.add_response(
                url=url_track_pattern,
                method="GET",
                json=response,
            )

        expect_artists = len(artists_response["items"])
        expect_tracks = len(tracks_response["items"])

        report = await spotify_sync(
            user=user,
            spotify_session_factory=spotify_session_factory,
            artist_repository=artist_repository,
            track_repository=track_repository,
            purge_artists=True,
            purge_tracks=True,
            sync_artists=True,
            sync_tracks=True,
            page_limit=len(tracks_response_paginated),
        )
        assert report == SyncReport(
            purge_artist=len(artists_delete),
            purge_track=len(tracks_delete),
            artist_created=expect_artists,
            track_created=expect_tracks,
        )

        stmt = select(func.count()).select_from(ArtistModel).where(ArtistModel.user_id == user.id)
        result = await async_session_db.execute(stmt)
        assert result.scalar() == expect_artists

        stmt = select(func.count()).select_from(TrackModel).where(TrackModel.user_id == user.id)
        result = await async_session_db.execute(stmt)
        assert result.scalar() == expect_tracks

    @pytest.mark.parametrize(
        ("artists_update", "tracks_update"),
        [(3, 2)],
        indirect=["artists_update", "tracks_update"],
    )
    async def test__all__sync__update(
        self,
        async_session_db: AsyncSession,
        user: User,
        artists_update: list[Artist],
        tracks_update: list[Track],
        spotify_client: SpotifyClientAdapter,
        spotify_session_factory: SpotifySessionFactory,
        artist_repository: ArtistRepositoryPort,
        track_repository: TrackRepositoryPort,
        httpx_mock: HTTPXMock,
        artists_response: dict[str, Any],
        artists_response_paginated: list[dict[str, Any]],
        tracks_response: dict[str, Any],
        tracks_response_paginated: list[dict[str, Any]],
    ) -> None:
        url_artist_pattern = re.compile(r".*/me/top/artists.*")
        url_track_pattern = re.compile(r".*/me/top/tracks.*")

        for response in artists_response_paginated:
            httpx_mock.add_response(
                url=url_artist_pattern,
                method="GET",
                json=response,
            )

        for response in tracks_response_paginated:
            httpx_mock.add_response(
                url=url_track_pattern,
                method="GET",
                json=response,
            )

        expect_artists_created = int(
            ((DEFAULT_PAGINATION_TOTAL / DEFAULT_PAGINATION_LIMIT) - 3) * DEFAULT_PAGINATION_LIMIT
        )
        expect_tracks_created = int(
            ((DEFAULT_PAGINATION_TOTAL / DEFAULT_PAGINATION_LIMIT) - 2) * DEFAULT_PAGINATION_LIMIT
        )
        expect_artists_updated = 3 * DEFAULT_PAGINATION_LIMIT  # As specified by the fixture param
        expect_tracks_updated = 2 * DEFAULT_PAGINATION_LIMIT  # As specified by the fixture param

        report = await spotify_sync(
            user=user,
            spotify_session_factory=spotify_session_factory,
            artist_repository=artist_repository,
            track_repository=track_repository,
            sync_artists=True,
            sync_tracks=True,
            page_limit=len(tracks_response_paginated),
        )
        assert report == SyncReport(
            artist_created=expect_artists_created,
            artist_updated=expect_artists_updated,
            track_created=expect_tracks_created,
            track_updated=expect_tracks_updated,
        )

        stmt = select(func.count()).select_from(ArtistModel).where(ArtistModel.user_id == user.id)
        result = await async_session_db.execute(stmt)
        assert result.scalar() == expect_artists_created + expect_artists_updated

        stmt = select(func.count()).select_from(TrackModel).where(TrackModel.user_id == user.id)
        result = await async_session_db.execute(stmt)
        assert result.scalar() == expect_tracks_created + expect_tracks_updated
