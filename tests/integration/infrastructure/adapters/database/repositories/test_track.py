import asyncio
import dataclasses
import operator
import uuid
from collections.abc import Callable
from datetime import UTC
from datetime import datetime

from sqlalchemy import func
from sqlalchemy import select
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

import pytest

from museflow.application.ports.repositories.track import TrackRepository
from museflow.application.ports.repositories.track_play import TrackPlayRepository
from museflow.domain.entities.track import ProviderLink
from museflow.domain.entities.track import Track
from museflow.domain.entities.user import User
from museflow.domain.enums import EnrichField
from museflow.domain.enums import MusicProvider
from museflow.domain.enums import SortOrder
from museflow.domain.enums import TrackOrderBy
from museflow.domain.enums import TrackSource
from museflow.domain.exceptions import TrackNotFoundError
from museflow.domain.value_objects.stats import ArtistTally
from museflow.domain.value_objects.track import TrackPlay
from museflow.infrastructure.adapters.database.models import Track as TrackModel

from tests.integration.factories.models.track import TrackModelFactory
from tests.integration.factories.models.user import UserModelFactory
from tests.unit.factories.entities.track import TrackFactory


class TestTrackSQLRepository:
    @pytest.fixture
    async def tracks(self, user: User) -> list[Track]:
        return [await TrackModelFactory.create_entity_async(user_id=user.id) for _ in range(10)]

    @pytest.fixture
    async def tracks_other(self) -> list[Track]:
        other_user_db = await UserModelFactory.create_async()
        return [await TrackModelFactory.create_entity_async(user_id=other_user_db.id) for _ in range(2)]

    @pytest.fixture
    def tracks_create(self, user: User) -> list[Track]:
        return TrackFactory.batch(size=10, user_id=user.id)

    @pytest.fixture
    def tracks_update(self, tracks: list[Track]) -> list[Track]:
        return [dataclasses.replace(track, artists=["SCH"]) for track in tracks]

    @pytest.fixture
    def tracks_mix(self, user: User, tracks: list[Track]) -> list[Track]:
        return [
            # 5 created
            *TrackFactory.batch(size=5, user_id=user.id),
            # 5 updated
            *[dataclasses.replace(track, artists=["SCH"]) for track in tracks[:5]],
        ]

    async def test__get_list__none(self, user: User, track_repository: TrackRepository) -> None:
        track_list = await track_repository.get_list(user.id)
        assert len(track_list) == 0

    async def test__get_list__filtering__user(
        self,
        user: User,
        tracks: list[Track],
        tracks_other: list[Track],
        track_repository: TrackRepository,
    ) -> None:
        track_list = await track_repository.get_list(user.id)

        assert len(track_list) == len(tracks)
        assert {t.id for t in track_list} == {t.id for t in tracks}
        assert set([t.user_id for t in track_list]) == {user.id}

    async def test__get_list__filtering__provider(
        self,
        user: User,
        tracks: list[Track],
        tracks_other: list[Track],
        track_repository: TrackRepository,
    ) -> None:
        track_list = await track_repository.get_list(user.id, provider=MusicProvider.SPOTIFY)

        assert len(track_list) == len(tracks)
        assert {t.id for t in track_list} == {t.id for t in tracks}
        assert all(any(link.provider == MusicProvider.SPOTIFY for link in t.provider_links) for t in track_list)

    async def test__get_list__filtering__source(
        self,
        user: User,
        track_repository: TrackRepository,
    ) -> None:
        history_db = await TrackModelFactory.create_async(user_id=user.id, source=int(TrackSource.HISTORY))
        discovery_db = await TrackModelFactory.create_async(user_id=user.id, source=int(TrackSource.DISCOVERY))
        both_db = await TrackModelFactory.create_async(
            user_id=user.id, source=int(TrackSource.HISTORY | TrackSource.DISCOVERY)
        )

        history_list = await track_repository.get_list(user.id, source=TrackSource.HISTORY)
        assert {t.id for t in history_list} == {history_db.id, both_db.id}

        discovery_list = await track_repository.get_list(user.id, source=TrackSource.DISCOVERY)
        assert {t.id for t in discovery_list} == {discovery_db.id, both_db.id}

    async def test__get_list__filtering__max_score(
        self,
        user: User,
        track_repository: TrackRepository,
    ) -> None:
        low_db = await TrackModelFactory.create_async(user_id=user.id, score=4)
        await TrackModelFactory.create_async(user_id=user.id, score=8)

        result = await track_repository.get_list(user.id, max_score=5)
        assert [t.id for t in result] == [low_db.id]

    async def test__get_list__filtering__unrated_only(
        self,
        user: User,
        track_repository: TrackRepository,
    ) -> None:
        unrated_db = await TrackModelFactory.create_async(user_id=user.id, score=None)
        await TrackModelFactory.create_async(user_id=user.id, score=7)

        unrated_list = await track_repository.get_list(user.id, unrated_only=True)
        assert [t.id for t in unrated_list] == [unrated_db.id]

    async def test__get_list__missing_fields__locale__null_eligible_empty_list_not(
        self,
        user: User,
        track_repository: TrackRepository,
    ) -> None:
        never_enriched_db = await TrackModelFactory.create_async(user_id=user.id, locales=None)
        await TrackModelFactory.create_async(user_id=user.id, locales=[])
        await TrackModelFactory.create_async(user_id=user.id, locales=["fr"])

        result = await track_repository.get_list(user.id, missing_fields=frozenset({EnrichField.LOCALE}))
        assert [t.id for t in result] == [never_enriched_db.id]

    async def test__get_list__filtering__locales__overlap(
        self,
        user: User,
        track_repository: TrackRepository,
    ) -> None:
        duet_db = await TrackModelFactory.create_async(user_id=user.id, locales=["fr", "en"])
        await TrackModelFactory.create_async(user_id=user.id, locales=["de"])
        await TrackModelFactory.create_async(user_id=user.id, locales=[])
        await TrackModelFactory.create_async(user_id=user.id, locales=None)

        result = await track_repository.get_list(user.id, locales=["en"])
        assert [t.id for t in result] == [duet_db.id]

    async def test__get_list__filtering__artist_name(
        self,
        user: User,
        track_repository: TrackRepository,
    ) -> None:
        target_db = await TrackModelFactory.create_async(user_id=user.id, artists=["Radiohead"])
        await TrackModelFactory.create_async(user_id=user.id, artists=["Other Artist"])

        result = await track_repository.get_list(user.id, artist_name="Radiohead")
        assert [t.id for t in result] == [target_db.id]

        result_ci = await track_repository.get_list(user.id, artist_name="radiohead")
        assert [t.id for t in result_ci] == [target_db.id]

    async def test__get_list__min_score_with_explicit_order__order_wins(
        self,
        user: User,
        track_repository: TrackRepository,
    ) -> None:
        low_played = await TrackModelFactory.create_async(user_id=user.id, score=8, played_count=1)
        high_played = await TrackModelFactory.create_async(user_id=user.id, score=5, played_count=10)

        result = await track_repository.get_list(
            user.id,
            min_score=5,
            order=[(TrackOrderBy.PLAYED_COUNT, SortOrder.DESC)],
        )

        assert [t.id for t in result] == [high_played.id, low_played.id]

    async def test__get_list__exclude_ids(
        self,
        user: User,
        track_repository: TrackRepository,
    ) -> None:
        kept = await TrackModelFactory.create_async(user_id=user.id)
        excluded = await TrackModelFactory.create_async(user_id=user.id)

        result = await track_repository.get_list(user.id, exclude_ids=[excluded.id])

        assert [t.id for t in result] == [kept.id]

    async def test__get_list__exclude_skipped(
        self,
        user: User,
        track_repository: TrackRepository,
    ) -> None:
        not_skipped_db = await TrackModelFactory.create_async(user_id=user.id, score=None, score_skipped=False)
        await TrackModelFactory.create_async(user_id=user.id, score=None, score_skipped=True)

        result = await track_repository.get_list(user.id, exclude_skipped=True)

        assert [t.id for t in result] == [not_skipped_db.id]

    async def test__get_list__score_skipped_only(
        self,
        user: User,
        track_repository: TrackRepository,
    ) -> None:
        await TrackModelFactory.create_async(user_id=user.id, score=None, score_skipped=False)
        skipped_db = await TrackModelFactory.create_async(user_id=user.id, score=None, score_skipped=True)

        result = await track_repository.get_list(user.id, score_skipped_only=True)

        assert [t.id for t in result] == [skipped_db.id]

    @pytest.mark.parametrize("order_by", [o for o in TrackOrderBy if o != TrackOrderBy.RANDOM and not o.nullable])
    @pytest.mark.parametrize("sort_order", list(SortOrder))
    async def test__get_list__ordering(
        self,
        user: User,
        order_by: TrackOrderBy,
        sort_order: SortOrder,
        tracks_other: list[Track],
        track_repository: TrackRepository,
    ) -> None:
        # Play counts in another order than the creation, so each ordering gives a different list
        played_counts = [2, 5, 1]
        tracks: list[TrackModel] = []
        for played_count in played_counts:
            tracks.append(await TrackModelFactory.create_async(user_id=user.id, played_count=played_count))
            await asyncio.sleep(0.01)

        def played_count_of(track: TrackModel) -> int:
            return played_counts[tracks.index(track)]

        key_func: Callable[[TrackModel], object]
        match order_by:
            case TrackOrderBy.CREATED_AT:
                key_func = operator.attrgetter("created_at")
            case TrackOrderBy.UPDATED_AT:
                key_func = operator.attrgetter("updated_at")
            case TrackOrderBy.PLAYED_COUNT:
                key_func = played_count_of
            case _:
                pytest.fail(f"Unhandled sort key: {order_by}")
                return

        expected_tracks = sorted(tracks, key=key_func, reverse=(sort_order == SortOrder.DESC))

        track_list = await track_repository.get_list(user.id, order=[(order_by, sort_order)])

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

        random_list_1 = await track_repository.get_list(user.id, order=[(TrackOrderBy.RANDOM, SortOrder.ASC)])
        random_list_2 = await track_repository.get_list(user.id, order=[(TrackOrderBy.RANDOM, SortOrder.ASC)])

        assert len(random_list_1) == len(random_list_2) == 10
        assert {t.id for t in random_list_1} == {t.id for t in random_list_2} == track_ids

        # There is a "tiny chance" (1 in 10! ~= 1 in 3.6 million) this fails... If it happens, I will be a millionaire!
        assert [t.id for t in random_list_1] != [t.id for t in random_list_2]

    async def test__get_list__ordering__nullable(
        self,
        user: User,
        tracks_other: list[Track],
        track_repository: TrackRepository,
    ) -> None:
        t1 = await TrackModelFactory.create_async(user_id=user.id, played_at_last=datetime(2023, 1, 1, tzinfo=UTC))
        t2 = await TrackModelFactory.create_async(user_id=user.id, played_at_last=datetime(2023, 6, 1, tzinfo=UTC))
        t3 = await TrackModelFactory.create_async(user_id=user.id, played_at_last=datetime(2024, 1, 1, tzinfo=UTC))
        t4 = await TrackModelFactory.create_async(user_id=user.id, played_at_last=None)

        tracks_asc = await track_repository.get_list(user.id, order=[(TrackOrderBy.PLAYED_AT_LAST, SortOrder.ASC)])
        assert [t.id for t in tracks_asc] == [t1.id, t2.id, t3.id, t4.id]

        tracks_desc = await track_repository.get_list(user.id, order=[(TrackOrderBy.PLAYED_AT_LAST, SortOrder.DESC)])
        assert [t.id for t in tracks_desc] == [t3.id, t2.id, t1.id, t4.id]

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

        assert len(track_list) == len(tracks_expected)
        assert set([t.provider_links[0].provider_id for t in track_list]).issubset(
            [t.provider_links[0].provider_id for t in tracks]
        )
        assert sorted([t.provider_links[0].provider_id for t in track_list]) == sorted(
            [t.provider_links[0].provider_id for t in tracks_expected]
        )
        assert set([t.user_id for t in track_list]) == {user.id}

    async def test__get_known_identifiers__none(self, user: User, track_repository: TrackRepository) -> None:
        known_identifiers = await track_repository.get_known_identifiers(
            user_id=user.id,
            fingerprints=[],
        )
        assert not known_identifiers.fingerprints

    async def test__get_known_identifiers__fingerprint(self, user: User, track_repository: TrackRepository) -> None:
        await TrackModelFactory.create_async(user_id=user.id, fingerprint="foo")
        await TrackModelFactory.create_async(user_id=user.id, fingerprint="bar")
        await TrackModelFactory.create_async(user_id=user.id, fingerprint="baz")
        await TrackModelFactory.create_async(fingerprint="bar")  # Another user

        known_identifiers = await track_repository.get_known_identifiers(
            user_id=user.id,
            fingerprints=["foo", "bar"],
        )

        assert known_identifiers.fingerprints == frozenset(["foo", "bar"])

    async def test__get_covered_artists__nominal(self, user: User, track_repository: TrackRepository) -> None:
        """Counted on the primary artist, most tracks first, ties by name, capped; other users' tracks ignored."""
        for artist, tracks_count in [
            ("Tied Band", 2),
            ("The Fictional Band", 3),
            ("Another Band", 2),
            ("Lone Band", 1),
        ]:
            for _ in range(tracks_count):
                await TrackModelFactory.create_async(user_id=user.id, artists=[artist, "A Featured Artist"])
        for _ in range(4):
            await TrackModelFactory.create_async(artists=["Lone Band"])  # Another user

        covered_artists = await track_repository.get_covered_artists(user_id=user.id, limit=3)

        assert list(covered_artists.items()) == [("The Fictional Band", 3), ("Another Band", 2), ("Tied Band", 2)]

    async def test__get_artist_tallies__nominal(self, user: User, track_repository: TrackRepository) -> None:
        """Grouped on the primary artist; unrated tracks count in the tracks and plays only; other users ignored."""
        await TrackModelFactory.create_async(user_id=user.id, artists=["Band A", "A Featured Artist"], score=8)
        await TrackModelFactory.create_async(user_id=user.id, artists=["Band A"], score=6, played_count=3)
        await TrackModelFactory.create_async(user_id=user.id, artists=["Band A"], score=None, played_count=2)
        await TrackModelFactory.create_async(user_id=user.id, artists=["Band B"], score=None)
        await TrackModelFactory.create_async(artists=["Band A"], score=10, played_count=5)  # Another user

        tallies = await track_repository.get_artist_tallies(user_id=user.id)

        assert sorted(tallies, key=operator.attrgetter("artist")) == [
            ArtistTally(artist="Band A", track_count=3, plays_count=5, rated_count=2, rated_sum=14),
            ArtistTally(artist="Band B", track_count=1, plays_count=0, rated_count=0, rated_sum=0),
        ]

    async def test__get_artist_tallies__score_range(self, user: User, track_repository: TrackRepository) -> None:
        """Out-of-range scores leave the ratings, not the track count."""
        for score in (2, 5, 7, 9):
            await TrackModelFactory.create_async(user_id=user.id, artists=["Band A"], score=score)

        tallies = await track_repository.get_artist_tallies(user_id=user.id, score_min=5, score_max=7)

        assert tallies == [ArtistTally(artist="Band A", track_count=4, plays_count=0, rated_count=2, rated_sum=12)]

    async def test__get_artist_tallies__source(self, user: User, track_repository: TrackRepository) -> None:
        await TrackModelFactory.create_async(user_id=user.id, artists=["Band A"], score=8, source=TrackSource.HISTORY)
        await TrackModelFactory.create_async(
            user_id=user.id,
            artists=["Band A"],
            score=4,
            source=TrackSource.HISTORY | TrackSource.DISCOVERY,
        )
        await TrackModelFactory.create_async(
            user_id=user.id, artists=["Band B"], score=6, source=TrackSource.DISCOVERY
        )

        tallies = await track_repository.get_artist_tallies(user_id=user.id, source=TrackSource.HISTORY)

        assert tallies == [ArtistTally(artist="Band A", track_count=2, plays_count=0, rated_count=2, rated_sum=12)]

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

        assert len(track_ids) == len(tracks_create) == create_count == 10
        assert track_ids == {t.fingerprint: t.id for t in tracks_create}

        stmt = select(TrackModel).where(TrackModel.id.in_(track_ids.values()))
        results = await async_session_db.execute(stmt)
        tracks_db = results.scalars().all()

        assert len(tracks_db) == len(track_ids)
        assert set([t.user_id for t in tracks_db]) == {user.id}
        assert sorted([t.provider_links[0]["provider_id"] for t in tracks_db]) == sorted(
            [t.provider_links[0].provider_id for t in tracks_create]
        )

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

        assert len(track_ids) == len(tracks_update) == len(tracks) == 10
        assert create_count == 0

        stmt = select(TrackModel).where(TrackModel.id.in_(track_ids.values()))
        results = await async_session_db.execute(stmt)
        tracks_db = results.scalars().all()

        assert len(tracks_db) == len(tracks_update)
        assert set([t.user_id for t in tracks_db]) == {user.id}

        artists = [track_db.artists[0] for track_db in tracks_db]
        expected_artists = ["SCH" for _ in range(len(tracks_db))]
        assert artists == expected_artists

    async def test__bulk_upsert__conflict__returns_existing_id(
        self,
        tracks: list[Track],
        track_repository: TrackRepository,
    ) -> None:
        existing = tracks[0]
        # Same user and fingerprint, but a new entity ID: the row already in the DB wins.
        track_ids, create_count = await track_repository.bulk_upsert(
            [dataclasses.replace(existing, id=uuid.uuid4())],
            batch_size=10,
        )

        assert track_ids == {existing.fingerprint: existing.id}
        assert create_count == 0

    async def test__bulk_upsert__both(
        self,
        async_session_db: AsyncSession,
        user: User,
        tracks_mix: list[Track],
        track_repository: TrackRepository,
    ) -> None:
        track_ids, create_count = await track_repository.bulk_upsert(tracks_mix, 300)

        assert len(track_ids) == len(tracks_mix) == 10
        assert create_count == 5
        assert track_ids == {t.fingerprint: t.id for t in tracks_mix}

        stmt = select(TrackModel).where(TrackModel.id.in_(track_ids.values())).order_by(TrackModel.created_at.asc())
        results = await async_session_db.execute(stmt)
        tracks_db = results.scalars().all()
        assert len(tracks_db) == len(tracks_mix)
        assert set([t.user_id for t in tracks_db]) == {user.id}

        assert sorted([t.provider_links[0]["provider_id"] for t in tracks_db[:5]]) == sorted(
            [t.provider_links[0].provider_id for t in tracks_mix[:5]]
        )
        artists = [track_db.artists[0] for track_db in tracks_db[5:]]
        expected_artists = ["SCH" for _ in range(len(tracks_db[5:]))]
        assert artists == expected_artists

    async def test__bulk_upsert__play_data__computed_from_the_plays(
        self,
        user: User,
        track_repository: TrackRepository,
        track_play_repository: TrackPlayRepository,
    ) -> None:
        track = TrackFactory.build(user_id=user.id, played_count=7, played_at_last=datetime(2023, 1, 1, tzinfo=UTC))
        track_ids, _ = await track_repository.bulk_upsert([track], batch_size=1)
        first, last = datetime(2024, 1, 1, tzinfo=UTC), datetime(2024, 6, 1, tzinfo=UTC)
        await track_play_repository.bulk_create(
            [TrackPlay(track_id=track_ids[track.fingerprint], played_at=moment) for moment in (first, last)]
        )

        [track_loaded] = await track_repository.get_list(user_id=user.id)

        # The values the entity carried are never written: only its plays count.
        assert (track_loaded.played_count, track_loaded.played_at_first, track_loaded.played_at_last) == (
            2,
            first,
            last,
        )

    async def test__bulk_upsert__same_fingerprint_different_provider_id__deduplicates(
        self,
        user: User,
        track_repository: TrackRepository,
        async_session_db: AsyncSession,
    ) -> None:
        """Importing the same song via two different Spotify IDs (e.g. single vs album) across
        two separate import runs collapses into one DB row; provider_links are accumulated (both IDs kept)."""
        first = TrackFactory.build(
            user_id=user.id,
            provider_links=[ProviderLink(provider=MusicProvider.SPOTIFY, provider_id="single_version")],
        )
        second = dataclasses.replace(
            first,
            provider_links=[ProviderLink(provider=MusicProvider.SPOTIFY, provider_id="album_version")],
        )

        _, created_first = await track_repository.bulk_upsert([first], batch_size=10)
        _, created_second = await track_repository.bulk_upsert([second], batch_size=10)

        assert created_first == 1
        assert created_second == 0

        stmt = select(TrackModel).where(
            TrackModel.user_id == user.id,
            TrackModel.fingerprint == first.fingerprint,
        )
        rows = (await async_session_db.execute(stmt)).scalars().all()
        assert len(rows) == 1
        provider_ids = {link["provider_id"] for link in rows[0].provider_links}
        assert "single_version" in provider_ids
        assert "album_version" in provider_ids

    async def test__bulk_upsert__does_not_overwrite_score_skipped(
        self,
        async_session_db: AsyncSession,
        user: User,
        track_repository: TrackRepository,
    ) -> None:
        track = TrackFactory.build(user_id=user.id, score_skipped=False)
        await track_repository.bulk_upsert([track], batch_size=1)

        await track_repository.skip(user_id=user.id, track_id=track.id)

        track_not_skipped = dataclasses.replace(track, score_skipped=False)
        await track_repository.bulk_upsert([track_not_skipped], batch_size=1)

        stmt = select(TrackModel).where(TrackModel.id == track.id)
        track_db = (await async_session_db.execute(stmt)).scalar_one()
        assert track_db.score_skipped is True

    async def test__bulk_update__empty_list__is_noop(self, track_repository: TrackRepository) -> None:
        await track_repository.bulk_update([], frozenset({EnrichField.GENRE}))

    async def test__rate__updates_score(
        self,
        async_session_db: AsyncSession,
        user: User,
        track_repository: TrackRepository,
    ) -> None:
        track_db = await TrackModelFactory.create_async(user_id=user.id)

        await track_repository.rate(user_id=user.id, track_id=track_db.id, score=7)

        stmt = select(TrackModel).where(TrackModel.id == track_db.id)
        updated = (await async_session_db.execute(stmt)).scalar_one()
        assert updated.score == 7

    async def test__rate__raises_when_track_not_found(
        self,
        user: User,
        track_repository: TrackRepository,
    ) -> None:
        with pytest.raises(TrackNotFoundError):
            await track_repository.rate(user_id=user.id, track_id=uuid.uuid4(), score=5)

    async def test__rate__raises_when_wrong_user(
        self,
        track_repository: TrackRepository,
    ) -> None:
        other_user_db = await UserModelFactory.create_async()
        track_db = await TrackModelFactory.create_async(user_id=other_user_db.id)

        with pytest.raises(TrackNotFoundError):
            await track_repository.rate(user_id=uuid.uuid4(), track_id=track_db.id, score=5)

    async def test__reset_score__resets_matching_source(
        self,
        async_session_db: AsyncSession,
        user: User,
        track_repository: TrackRepository,
    ) -> None:
        history_db = await TrackModelFactory.create_async(user_id=user.id, source=int(TrackSource.HISTORY), score=8)
        discovery_db = await TrackModelFactory.create_async(
            user_id=user.id, source=int(TrackSource.DISCOVERY), score=6
        )

        count = await track_repository.reset_score(user_id=user.id, source=TrackSource.HISTORY)
        assert count == 1

        stmt = select(TrackModel).where(TrackModel.id == history_db.id)
        history_updated = (await async_session_db.execute(stmt)).scalar_one()
        assert history_updated.score is None

        stmt = select(TrackModel).where(TrackModel.id == discovery_db.id)
        discovery_updated = (await async_session_db.execute(stmt)).scalar_one()
        assert discovery_updated.score == 6

    async def test__reset_score__scoped_to_user(
        self,
        async_session_db: AsyncSession,
        user: User,
        track_repository: TrackRepository,
    ) -> None:
        own_db = await TrackModelFactory.create_async(user_id=user.id, source=int(TrackSource.HISTORY), score=8)
        other_user_db = await UserModelFactory.create_async()
        other_db = await TrackModelFactory.create_async(
            user_id=other_user_db.id, source=int(TrackSource.HISTORY), score=5
        )

        count = await track_repository.reset_score(user_id=user.id, source=TrackSource.HISTORY)
        assert count == 1

        stmt = select(TrackModel).where(TrackModel.id == own_db.id)
        assert (await async_session_db.execute(stmt)).scalar_one().score is None

        stmt = select(TrackModel).where(TrackModel.id == other_db.id)
        assert (await async_session_db.execute(stmt)).scalar_one().score == 5

    async def test__delete__by_ids(
        self,
        async_session_db: AsyncSession,
        user: User,
        track_repository: TrackRepository,
    ) -> None:
        target = await TrackModelFactory.create_async(user_id=user.id)
        other = await TrackModelFactory.create_async(user_id=user.id)

        count = await track_repository.delete(user_id=user.id, track_ids=[target.id])

        assert count == 1
        assert (
            await async_session_db.execute(select(TrackModel).where(TrackModel.id == target.id))
        ).scalar_one_or_none() is None
        assert (
            await async_session_db.execute(select(TrackModel).where(TrackModel.id == other.id))
        ).scalar_one_or_none() is not None

    async def test__delete__more_ids_than_bind_params(self, user: User, track_repository: TrackRepository) -> None:
        # asyncpg caps a query at 32767 bind parameters: a whole library must fit in one.
        track_db = await TrackModelFactory.create_async(user_id=user.id)
        track_ids = [track_db.id, *(uuid.uuid4() for _ in range(40_000))]

        count = await track_repository.delete(user_id=user.id, track_ids=track_ids)

        assert count == 1

    async def test__delete__scoped_to_user(
        self,
        async_session_db: AsyncSession,
        user: User,
        track_repository: TrackRepository,
    ) -> None:
        other_user_db = await UserModelFactory.create_async()
        other_track = await TrackModelFactory.create_async(user_id=other_user_db.id)

        count = await track_repository.delete(user_id=user.id, track_ids=[other_track.id])

        assert count == 0
        assert (
            await async_session_db.execute(select(TrackModel).where(TrackModel.id == other_track.id))
        ).scalar_one_or_none() is not None

    async def test__purge(
        self,
        async_session_db: AsyncSession,
        user: User,
        tracks: list[Track],
        tracks_other: list[Track],
        track_repository: TrackRepository,
    ) -> None:
        count = await track_repository.purge(user_id=user.id)

        assert count == len(tracks)
        stmt = select(func.count()).select_from(TrackModel).where(TrackModel.user_id == user.id)
        assert (await async_session_db.execute(stmt)).scalar() == 0
        stmt = select(func.count()).select_from(TrackModel).where(TrackModel.user_id != user.id)
        assert (await async_session_db.execute(stmt)).scalar() == len(tracks_other)

    async def test__unlink_provider__given_ids(
        self,
        async_session_db: AsyncSession,
        user: User,
        track_repository: TrackRepository,
    ) -> None:
        # No second provider exists yet: a raw link stands for one.
        other_link = {"provider": "other", "provider_id": "other-id"}
        orphan_db = await TrackModelFactory.create_async(user_id=user.id)
        multi_db = await TrackModelFactory.create_async(user_id=user.id)
        multi_db_links = [*multi_db.provider_links, other_link]
        await async_session_db.execute(
            update(TrackModel).where(TrackModel.id == multi_db.id).values(provider_links=multi_db_links)
        )
        untouched_db = await TrackModelFactory.create_async(user_id=user.id)

        orphan_ids = await track_repository.unlink_provider(
            user_id=user.id,
            provider=MusicProvider.SPOTIFY,
            track_ids=[orphan_db.id, multi_db.id],
        )

        assert orphan_ids == [orphan_db.id]
        stmt = select(TrackModel.id, TrackModel.provider_links).where(TrackModel.user_id == user.id)
        links = {row.id: row.provider_links for row in await async_session_db.execute(stmt)}
        assert links[orphan_db.id] == []
        assert links[multi_db.id] == [other_link]
        assert links[untouched_db.id] == untouched_db.provider_links

    async def test__unlink_provider__all_tracks(
        self,
        async_session_db: AsyncSession,
        user: User,
        track_repository: TrackRepository,
    ) -> None:
        tracks_db = await TrackModelFactory.create_batch_async(size=2, user_id=user.id)
        other_user_db = await UserModelFactory.create_async()
        other_track_db = await TrackModelFactory.create_async(user_id=other_user_db.id)

        orphan_ids = await track_repository.unlink_provider(user_id=user.id, provider=MusicProvider.SPOTIFY)

        assert sorted(orphan_ids) == sorted(track_db.id for track_db in tracks_db)
        stmt = select(TrackModel.provider_links).where(TrackModel.id == other_track_db.id)
        assert (await async_session_db.execute(stmt)).scalar_one() == other_track_db.provider_links

    async def test__skip__marks_track_as_skipped(
        self,
        async_session_db: AsyncSession,
        user: User,
        track_repository: TrackRepository,
    ) -> None:
        track_db = await TrackModelFactory.create_async(user_id=user.id, score_skipped=False)

        await track_repository.skip(user_id=user.id, track_id=track_db.id)

        stmt = select(TrackModel).where(TrackModel.id == track_db.id)
        updated = (await async_session_db.execute(stmt)).scalar_one()
        assert updated.score_skipped is True

    async def test__skip__raises_when_track_not_found(
        self,
        user: User,
        track_repository: TrackRepository,
    ) -> None:
        with pytest.raises(TrackNotFoundError):
            await track_repository.skip(user_id=user.id, track_id=uuid.uuid4())

    async def test__skip__raises_when_wrong_user(
        self,
        track_repository: TrackRepository,
    ) -> None:
        other_user_db = await UserModelFactory.create_async()
        track_db = await TrackModelFactory.create_async(user_id=other_user_db.id)

        with pytest.raises(TrackNotFoundError):
            await track_repository.skip(user_id=uuid.uuid4(), track_id=track_db.id)
