from typing import Literal

ProviderPageErrorCodes = Literal["unsupported_local_files"]


# --- User exceptions ---


class UserNotFound(Exception): ...


class UserAlreadyExistsException(Exception): ...


class UserEmailAlreadyExistsException(Exception): ...


class UserInactive(Exception): ...


class UserInvalidCredentials(Exception): ...


# --- Rate limit exceptions ---


class RateLimitExceeded(Exception): ...


# --- Provider exceptions ---


class ProviderAuthTokenNotFoundError(Exception): ...


class ProviderExchangeCodeError(Exception): ...


class ProviderPageValidationError(Exception):
    def __init__(self, msg: str, code: ProviderPageErrorCodes | None = None) -> None:
        self.code = code
        super().__init__(msg)


class ProviderRateLimitExceeded(RateLimitExceeded): ...


class ProviderNoActiveDeviceException(Exception): ...


class ProviderPremiumRequiredException(Exception): ...


# --- Advisor exceptions ---


class AdvisorRateLimitExceeded(RateLimitExceeded): ...


# --- Profiler exceptions ---


class TasteProfilerRateLimitExceeded(RateLimitExceeded): ...


class TasteProfileBuildException(Exception): ...


class TasteProfileBuildPausedException(Exception):
    def __init__(self, batch_index: int, total_batches: int, reason: str) -> None:
        self.batch_index = batch_index
        self.total_batches = total_batches
        self.reason = reason
        super().__init__(f"Build paused at batch {batch_index}/{total_batches} — {reason} — use --resume to continue")


class TasteProfileNoSeedException(Exception): ...


class TasteProfileNotFoundException(Exception): ...


class TasteProfileStatusNotReadyException(Exception): ...


# --- Enricher exceptions ---


class EnricherRateLimitExceeded(RateLimitExceeded): ...


class EnricherUnavailableException(Exception):
    """The enricher cannot serve any batch (auth, credits, unknown model, no provider, outage): stop the run."""


class TrackEnrichmentException(Exception):
    """A single batch was rejected, e.g. for its content: the run goes on."""


class TrackEnrichmentAbortedException(Exception):
    def __init__(self, batch_index: int, total_batches: int, enriched_count: int, reason: str) -> None:
        self.batch_index = batch_index
        self.total_batches = total_batches
        self.enriched_count = enriched_count
        self.reason = reason
        super().__init__(
            f"Enrichment stopped at batch {batch_index}/{total_batches} after {enriched_count} track(s): {reason}"
        )


# --- Blacklist exceptions ---


class BlacklistItemNotFoundError(Exception): ...


# --- Track exceptions ---


class TrackNotFoundError(Exception): ...


class RateScoreInvalidException(Exception): ...


# --- Playlist exceptions ---


class PlaylistNotFoundError(Exception): ...


class PlaylistNoTracksError(Exception): ...


# --- Discovery exceptions ---


class DiscoveryTrackNoNew(Exception): ...


class DiscoveryTasteStrategyException(Exception): ...


# --- Streaming history exceptions ---


class StreamingHistoryException(Exception): ...


class StreamingHistoryDirectoryNotFound(StreamingHistoryException): ...


class StreamingHistoryInvalidFormat(StreamingHistoryException): ...
