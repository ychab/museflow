import logging
from dataclasses import dataclass
from dataclasses import field
from dataclasses import replace

from spotifagent.application.services.spotify import SpotifySessionFactory
from spotifagent.application.services.spotify import SpotifyUserSession
from spotifagent.application.services.spotify import TimeRange
from spotifagent.domain.entities.users import User
from spotifagent.domain.exceptions import SpotifyAccountNotFoundError
from spotifagent.domain.ports.repositories.music import TopArtistRepositoryPort
from spotifagent.domain.ports.repositories.music import TopTrackRepositoryPort

logger = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class SyncReport:
    purge_top_artist: int = 0
    purge_top_track: int = 0

    top_artist_created: int = 0
    top_artist_updated: int = 0

    top_track_created: int = 0
    top_track_updated: int = 0

    errors: list[str] = field(default_factory=list)

    @property
    def has_errors(self) -> bool:
        return len(self.errors) > 0


async def spotify_sync_top_items(
    user: User,
    spotify_session_factory: SpotifySessionFactory,
    top_artist_repository: TopArtistRepositoryPort,
    top_track_repository: TopTrackRepositoryPort,
    purge_top_artists: bool = False,
    purge_top_tracks: bool = False,
    sync_top_artists: bool = False,
    sync_top_tracks: bool = False,
    page_limit: int = 50,
    time_range: TimeRange = "long_term",
    batch_size: int = 300,
) -> SyncReport:
    """
    For a given user, synchronize its Spotify top items, including top artists
    and top tracks, depending on the given flags.

    :param user: A user object
    :param spotify_session_factory: Spotify session factory
    :param top_artist_repository: Top artists repository
    :param top_track_repository: Top tracks repository
    :param purge_top_artists: Whether to purge top artists
    :param purge_top_tracks: Whether to purge top tracks
    :param sync_top_artists: Whether to sync top artists (fetch and save)
    :param sync_top_tracks: Whether to sync top tracks (fetch and save)
    :param page_limit: The number of items to fetch
    :param time_range: The time range to fetch
    :param batch_size: The number of items to bulk upsert in DB
    :return: SyncReport
    """
    report = SyncReport()

    # First of all, purge top items if required.
    if purge_top_artists:
        report = await _purge_top_artists(user, top_artist_repository, report)
        if report.has_errors:
            return report

    if purge_top_tracks:
        report = await _purge_top_tracks(user, top_track_repository, report)
        if report.has_errors:
            return report

    # Then init a spotify user session.
    try:
        spotify_session = spotify_session_factory.create(user)
    except SpotifyAccountNotFoundError:
        logger.debug(f"Spotify account not found for user {user.email}")
        return replace(report, errors=["You must connect your Spotify account first."])

    # Then fetch top artists and upsert them in DB.
    if sync_top_artists:
        report = await _sync_top_artists(
            spotify_session=spotify_session,
            top_artist_repository=top_artist_repository,
            page_limit=page_limit,
            time_range=time_range,
            batch_size=batch_size,
            report=report,
        )

    # Then fetch top tracks and upsert them in DB.
    if sync_top_tracks:
        report = await _sync_top_tracks(
            spotify_session=spotify_session,
            top_track_repository=top_track_repository,
            page_limit=page_limit,
            time_range=time_range,
            batch_size=batch_size,
            report=report,
        )

    return report


async def _purge_top_artists(
    user: User,
    top_artist_repository: TopArtistRepositoryPort,
    report: SyncReport,
) -> SyncReport:
    logger.info(f"About purging top artists for user {user.email}...")

    try:
        count_top_artist = await top_artist_repository.purge(user_id=user.id)
    except Exception:
        logger.exception(f"An error occurred while purging top artists for user {user.email}")
        report = replace(report, errors=["An error occurred while purging your top artists."])
    else:
        report = replace(report, purge_top_artist=count_top_artist)
        logger.info(f"Successfully purged {count_top_artist} top artists for user {user.email}")

    return report


async def _purge_top_tracks(
    user: User,
    top_track_repository: TopTrackRepositoryPort,
    report: SyncReport,
) -> SyncReport:
    logger.info(f"About purging top tracks for user {user.email}...")

    try:
        count_top_track = await top_track_repository.purge(user_id=user.id)
    except Exception:
        logger.exception(f"An error occurred while purging top tracks for user {user.email}")
        report = replace(report, errors=["An error occurred while purging your top tracks."])
    else:
        report = replace(report, purge_top_track=count_top_track)
        logger.info(f"Successfully purged {count_top_track} top tracks for user {user.email}")

    return report


async def _sync_top_artists(
    spotify_session: SpotifyUserSession,
    top_artist_repository: TopArtistRepositoryPort,
    page_limit: int,
    time_range: TimeRange,
    batch_size: int,
    report: SyncReport,
) -> SyncReport:
    logger.info(f"About synchronizing top artists for user {spotify_session.user.email}...")

    try:
        top_artists = await spotify_session.get_top_artists(limit=page_limit, time_range=time_range)
    except Exception:
        logger.exception(f"An error occurred while fetching top artists for user {spotify_session.user.email}")
        return replace(report, errors=["An error occurred while fetching Spotify top artists."])
    else:
        logger.info(f"Fetched {len(top_artists)} top artists for user {spotify_session.user.email}")

    try:
        top_artist_ids, created = await top_artist_repository.bulk_upsert(top_artists, batch_size=batch_size)
    except Exception:
        logger.exception(f"An error occurred while upserting top artists for user {spotify_session.user.email}")
        return replace(report, errors=["An error occurred while saving Spotify top artists."])
    else:
        logger.info(f"Upserted {len(top_artist_ids)} top artists for user {spotify_session.user.email}")

    return replace(report, top_artist_created=created, top_artist_updated=len(top_artist_ids) - created)


async def _sync_top_tracks(
    spotify_session: SpotifyUserSession,
    top_track_repository: TopTrackRepositoryPort,
    page_limit: int,
    time_range: TimeRange,
    batch_size: int,
    report: SyncReport,
) -> SyncReport:
    logger.info(f"About synchronizing top tracks for user {spotify_session.user.email}...")

    try:
        top_tracks = await spotify_session.get_top_tracks(limit=page_limit, time_range=time_range)
    except Exception:
        logger.exception(f"An error occurred while fetching top tracks for user {spotify_session.user.email}")
        return replace(report, errors=["An error occurred while fetching Spotify top tracks."])
    else:
        logger.info(f"Fetched {len(top_tracks)} top tracks for user {spotify_session.user.email}")

    try:
        top_track_ids, created = await top_track_repository.bulk_upsert(top_tracks, batch_size=batch_size)
    except Exception:
        logger.exception(f"An error occurred while upserting top tracks for user {spotify_session.user.email}")
        return replace(report, errors=["An error occurred while saving Spotify top tracks."])
    else:
        logger.info(f"Upserted {len(top_track_ids)} top tracks for user {spotify_session.user.email}")

    return replace(report, top_track_created=created, top_track_updated=len(top_track_ids) - created)
