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
from spotifagent.application.use_cases.spotify_sync_top_items import SyncReport
from spotifagent.application.use_cases.spotify_sync_top_items import spotify_sync_top_items
from spotifagent.domain.entities.music import TopArtist
from spotifagent.domain.entities.music import TopTrack
from spotifagent.domain.entities.users import User
from spotifagent.domain.ports.repositories.music import TopArtistRepositoryPort
from spotifagent.domain.ports.repositories.music import TopTrackRepositoryPort
from spotifagent.infrastructure.adapters.clients.spotify import SpotifyClientAdapter
from spotifagent.infrastructure.adapters.database.models import TopArtist as TopArtistModel
from spotifagent.infrastructure.adapters.database.models import TopTrack as TopTrackModel

from tests import ASSETS_DIR
from tests.integration.factories.music import TopArtistModelFactory
from tests.integration.factories.music import TopTrackModelFactory
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


class TestSpotifySyncTopItems:
    @pytest.fixture
    def top_artists_response(self) -> dict[str, Any]:
        return load_spotify_response(filename="top_artists")

    @pytest.fixture
    def top_artists_response_paginated(self, top_artists_response: dict[str, Any]) -> list[dict[str, Any]]:
        return paginate_spotify_response(top_artists_response)

    @pytest.fixture
    def top_tracks_response(self) -> dict[str, Any]:
        return load_spotify_response(filename="top_tracks")

    @pytest.fixture
    def top_tracks_response_paginated(self, top_tracks_response: dict[str, Any]) -> list[dict[str, Any]]:
        return paginate_spotify_response(top_tracks_response)

    @pytest.fixture
    async def user(self) -> User:
        user_db = await UserModelFactory.create_async(with_spotify_account=True)
        return User.model_validate(user_db)

    @pytest.fixture
    async def top_artists_update(
        self,
        request: pytest.FixtureRequest,
        user: User,
        top_artists_response_paginated: list[dict[str, Any]],
    ) -> list[TopArtist]:
        page_max = getattr(request, "param", len(top_artists_response_paginated))
        top_artists: list[TopArtist] = []

        for page in top_artists_response_paginated[:page_max]:
            for item in page["items"]:
                top_artist = await TopArtistModelFactory.create_async(user_id=user.id, provider_id=item["id"])
                top_artists.append(TopArtist.model_validate(top_artist))

        return top_artists

    @pytest.fixture
    async def top_artists_delete(self, user: User) -> list[TopArtist]:
        return [
            TopArtist.model_validate(top_artist)
            for top_artist in await TopArtistModelFactory.create_batch_async(size=3, user_id=user.id)
        ]

    @pytest.fixture
    async def top_tracks_update(
        self,
        request: pytest.FixtureRequest,
        user: User,
        top_tracks_response_paginated: list[dict[str, Any]],
    ) -> list[TopTrack]:
        page_max = getattr(request, "param", len(top_tracks_response_paginated))
        top_tracks: list[TopTrack] = []

        for page in top_tracks_response_paginated[:page_max]:
            for item in page["items"]:
                top_track = await TopTrackModelFactory.create_async(user_id=user.id, provider_id=item["id"])
                top_tracks.append(TopTrack.model_validate(top_track))

        return top_tracks

    @pytest.fixture
    async def top_tracks_delete(self, user: User) -> list[TopTrack]:
        return [
            TopTrack.model_validate(top_track)
            for top_track in await TopTrackModelFactory.create_batch_async(size=3, user_id=user.id)
        ]

    async def test__top_artists__purge(
        self,
        async_session_db: AsyncSession,
        user: User,
        top_artists_delete: list[TopArtist],
        spotify_session_factory: SpotifySessionFactory,
        top_artist_repository: TopArtistRepositoryPort,
        top_track_repository: TopTrackRepositoryPort,
    ) -> None:
        pass
        report = await spotify_sync_top_items(
            user=user,
            spotify_session_factory=spotify_session_factory,
            top_artist_repository=top_artist_repository,
            top_track_repository=top_track_repository,
            purge_top_artists=True,
        )
        assert report == SyncReport(purge_top_artist=len(top_artists_delete))

        stmt = select(func.count()).select_from(TopArtistModel).where(TopArtistModel.user_id == user.id)
        result = await async_session_db.execute(stmt)
        assert result.scalar() == 0

    async def test__top_tracks__purge(
        self,
        async_session_db: AsyncSession,
        user: User,
        top_tracks_delete: list[TopTrack],
        spotify_session_factory: SpotifySessionFactory,
        top_artist_repository: TopArtistRepositoryPort,
        top_track_repository: TopTrackRepositoryPort,
    ) -> None:
        report = await spotify_sync_top_items(
            user=user,
            spotify_session_factory=spotify_session_factory,
            top_artist_repository=top_artist_repository,
            top_track_repository=top_track_repository,
            purge_top_tracks=True,
        )
        assert report == SyncReport(purge_top_track=len(top_tracks_delete))

        stmt = select(func.count()).select_from(TopTrackModel).where(TopTrackModel.user_id == user.id)
        result = await async_session_db.execute(stmt)
        assert result.scalar() == 0

    async def test__top_artists__sync__create(
        self,
        async_session_db: AsyncSession,
        user: User,
        spotify_client: SpotifyClientAdapter,
        spotify_session_factory: SpotifySessionFactory,
        top_artist_repository: TopArtistRepositoryPort,
        top_track_repository: TopTrackRepositoryPort,
        httpx_mock: HTTPXMock,
        top_artists_response: dict[str, Any],
        top_artists_response_paginated: list[dict[str, Any]],
    ) -> None:
        expected_count = len(top_artists_response["items"])

        url_pattern = re.compile(r".*/me/top/artists.*")
        for response in top_artists_response_paginated:
            httpx_mock.add_response(
                url=url_pattern,
                method="GET",
                json=response,
            )

        report = await spotify_sync_top_items(
            user=user,
            spotify_session_factory=spotify_session_factory,
            top_artist_repository=top_artist_repository,
            top_track_repository=top_track_repository,
            sync_top_artists=True,
            page_limit=len(top_artists_response_paginated),
        )
        assert report == SyncReport(top_artist_created=expected_count)

        stmt = select(func.count()).select_from(TopArtistModel).where(TopArtistModel.user_id == user.id)
        result = await async_session_db.execute(stmt)
        assert result.scalar() == expected_count

    async def test__top_artists__sync__update(
        self,
        async_session_db: AsyncSession,
        user: User,
        top_artists_update: list[TopArtist],
        spotify_client: SpotifyClientAdapter,
        spotify_session_factory: SpotifySessionFactory,
        top_artist_repository: TopArtistRepositoryPort,
        top_track_repository: TopTrackRepositoryPort,
        httpx_mock: HTTPXMock,
        top_artists_response_paginated: list[dict[str, Any]],
    ) -> None:
        expected_count = len(top_artists_update)

        url_pattern = re.compile(r".*/me/top/artists.*")
        for response in top_artists_response_paginated:
            httpx_mock.add_response(
                url=url_pattern,
                method="GET",
                json=response,
            )

        report = await spotify_sync_top_items(
            user=user,
            spotify_session_factory=spotify_session_factory,
            top_artist_repository=top_artist_repository,
            top_track_repository=top_track_repository,
            sync_top_artists=True,
            page_limit=len(top_artists_response_paginated),
        )
        assert report == SyncReport(top_artist_updated=expected_count)

        stmt = select(TopArtistModel).where(TopArtistModel.user_id == user.id)
        result = await async_session_db.execute(stmt)
        top_artists_db = result.scalars().all()

        assert len(top_artists_db) == expected_count
        assert sorted([ta.id for ta in top_artists_db]) == sorted([ta.id for ta in top_artists_update])

    async def test__top_tracks__sync__create(
        self,
        async_session_db: AsyncSession,
        user: User,
        spotify_client: SpotifyClientAdapter,
        spotify_session_factory: SpotifySessionFactory,
        top_artist_repository: TopArtistRepositoryPort,
        top_track_repository: TopTrackRepositoryPort,
        httpx_mock: HTTPXMock,
        top_tracks_response: dict[str, Any],
        top_tracks_response_paginated: list[dict[str, Any]],
    ) -> None:
        expected_count = len(top_tracks_response["items"])

        url_pattern = re.compile(r".*/me/top/tracks.*")
        for response in top_tracks_response_paginated:
            httpx_mock.add_response(
                url=url_pattern,
                method="GET",
                json=response,
            )

        report = await spotify_sync_top_items(
            user=user,
            spotify_session_factory=spotify_session_factory,
            top_artist_repository=top_artist_repository,
            top_track_repository=top_track_repository,
            sync_top_tracks=True,
            page_limit=len(top_tracks_response_paginated),
        )
        assert report == SyncReport(top_track_created=expected_count)

        stmt = select(func.count()).select_from(TopTrackModel).where(TopTrackModel.user_id == user.id)
        result = await async_session_db.execute(stmt)
        assert result.scalar() == expected_count

    async def test__top_tracks__sync__update(
        self,
        async_session_db: AsyncSession,
        user: User,
        top_tracks_update: list[TopTrack],
        spotify_client: SpotifyClientAdapter,
        spotify_session_factory: SpotifySessionFactory,
        top_artist_repository: TopArtistRepositoryPort,
        top_track_repository: TopTrackRepositoryPort,
        httpx_mock: HTTPXMock,
        top_tracks_response_paginated: list[dict[str, Any]],
    ) -> None:
        expected_count = len(top_tracks_update)

        url_pattern = re.compile(r".*/me/top/tracks.*")
        for response in top_tracks_response_paginated:
            httpx_mock.add_response(
                url=url_pattern,
                method="GET",
                json=response,
            )

        report = await spotify_sync_top_items(
            user=user,
            spotify_session_factory=spotify_session_factory,
            top_artist_repository=top_artist_repository,
            top_track_repository=top_track_repository,
            sync_top_tracks=True,
            page_limit=len(top_tracks_response_paginated),
        )
        assert report == SyncReport(top_track_updated=expected_count)

        stmt = select(TopTrackModel).where(TopTrackModel.user_id == user.id)
        result = await async_session_db.execute(stmt)
        top_tracks_db = result.scalars().all()

        assert len(top_tracks_db) == expected_count
        assert sorted([ta.id for ta in top_tracks_db]) == sorted([ta.id for ta in top_tracks_update])

    async def test__all__purge__sync(
        self,
        async_session_db: AsyncSession,
        user: User,
        top_artists_delete: list[TopArtist],
        top_tracks_delete: list[TopTrack],
        spotify_client: SpotifyClientAdapter,
        spotify_session_factory: SpotifySessionFactory,
        top_artist_repository: TopArtistRepositoryPort,
        top_track_repository: TopTrackRepositoryPort,
        httpx_mock: HTTPXMock,
        top_artists_response: dict[str, Any],
        top_artists_response_paginated: list[dict[str, Any]],
        top_tracks_response: dict[str, Any],
        top_tracks_response_paginated: list[dict[str, Any]],
    ) -> None:
        url_top_artist_pattern = re.compile(r".*/me/top/artists.*")
        url_top_track_pattern = re.compile(r".*/me/top/tracks.*")

        for response in top_artists_response_paginated:
            httpx_mock.add_response(
                url=url_top_artist_pattern,
                method="GET",
                json=response,
            )

        for response in top_tracks_response_paginated:
            httpx_mock.add_response(
                url=url_top_track_pattern,
                method="GET",
                json=response,
            )

        expect_top_artists = len(top_artists_response["items"])
        expect_top_tracks = len(top_tracks_response["items"])

        report = await spotify_sync_top_items(
            user=user,
            spotify_session_factory=spotify_session_factory,
            top_artist_repository=top_artist_repository,
            top_track_repository=top_track_repository,
            purge_top_artists=True,
            purge_top_tracks=True,
            sync_top_artists=True,
            sync_top_tracks=True,
            page_limit=len(top_tracks_response_paginated),
        )
        assert report == SyncReport(
            purge_top_artist=len(top_artists_delete),
            purge_top_track=len(top_tracks_delete),
            top_artist_created=expect_top_artists,
            top_track_created=expect_top_tracks,
        )

        stmt = select(func.count()).select_from(TopArtistModel).where(TopArtistModel.user_id == user.id)
        result = await async_session_db.execute(stmt)
        assert result.scalar() == expect_top_artists

        stmt = select(func.count()).select_from(TopTrackModel).where(TopTrackModel.user_id == user.id)
        result = await async_session_db.execute(stmt)
        assert result.scalar() == expect_top_tracks

    @pytest.mark.parametrize(
        ("top_artists_update", "top_tracks_update"),
        [(3, 2)],
        indirect=["top_artists_update", "top_tracks_update"],
    )
    async def test__all__sync__update(
        self,
        async_session_db: AsyncSession,
        user: User,
        top_artists_update: list[TopArtist],
        top_tracks_update: list[TopTrack],
        spotify_client: SpotifyClientAdapter,
        spotify_session_factory: SpotifySessionFactory,
        top_artist_repository: TopArtistRepositoryPort,
        top_track_repository: TopTrackRepositoryPort,
        httpx_mock: HTTPXMock,
        top_artists_response: dict[str, Any],
        top_artists_response_paginated: list[dict[str, Any]],
        top_tracks_response: dict[str, Any],
        top_tracks_response_paginated: list[dict[str, Any]],
    ) -> None:
        url_top_artist_pattern = re.compile(r".*/me/top/artists.*")
        url_top_track_pattern = re.compile(r".*/me/top/tracks.*")

        for response in top_artists_response_paginated:
            httpx_mock.add_response(
                url=url_top_artist_pattern,
                method="GET",
                json=response,
            )

        for response in top_tracks_response_paginated:
            httpx_mock.add_response(
                url=url_top_track_pattern,
                method="GET",
                json=response,
            )

        expect_top_artists_created = int(
            ((DEFAULT_PAGINATION_TOTAL / DEFAULT_PAGINATION_LIMIT) - 3) * DEFAULT_PAGINATION_LIMIT
        )
        expect_top_tracks_created = int(
            ((DEFAULT_PAGINATION_TOTAL / DEFAULT_PAGINATION_LIMIT) - 2) * DEFAULT_PAGINATION_LIMIT
        )
        expect_top_artists_updated = 3 * DEFAULT_PAGINATION_LIMIT  # As specified by the fixture param
        expect_top_tracks_updated = 2 * DEFAULT_PAGINATION_LIMIT  # As specified by the fixture param

        report = await spotify_sync_top_items(
            user=user,
            spotify_session_factory=spotify_session_factory,
            top_artist_repository=top_artist_repository,
            top_track_repository=top_track_repository,
            sync_top_artists=True,
            sync_top_tracks=True,
            page_limit=len(top_tracks_response_paginated),
        )
        assert report == SyncReport(
            top_artist_created=expect_top_artists_created,
            top_artist_updated=expect_top_artists_updated,
            top_track_created=expect_top_tracks_created,
            top_track_updated=expect_top_tracks_updated,
        )

        stmt = select(func.count()).select_from(TopArtistModel).where(TopArtistModel.user_id == user.id)
        result = await async_session_db.execute(stmt)
        assert result.scalar() == expect_top_artists_created + expect_top_artists_updated

        stmt = select(func.count()).select_from(TopTrackModel).where(TopTrackModel.user_id == user.id)
        result = await async_session_db.execute(stmt)
        assert result.scalar() == expect_top_tracks_created + expect_top_tracks_updated
