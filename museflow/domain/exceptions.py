from typing import Literal

ProviderPageErrorCodes = Literal["unsupported_local_files"]


# --- User exceptions ---


class UserNotFoundError(Exception): ...


class UserAlreadyExistsError(Exception): ...


class UserEmailAlreadyExistsError(Exception): ...


class UserInactiveError(Exception): ...


class UserInvalidCredentialsError(Exception): ...


# --- Rate limit exceptions ---


class RateLimitExceededError(Exception): ...


# --- Provider exceptions ---


class ProviderAuthTokenNotFoundError(Exception): ...


class ProviderExchangeCodeError(Exception): ...


class ProviderOAuthStateInvalidError(Exception): ...


class ProviderPageValidationError(Exception):
    def __init__(self, msg: str, code: ProviderPageErrorCodes | None = None) -> None:
        self.code = code
        super().__init__(msg)


class ProviderRateLimitExceededError(RateLimitExceededError): ...


class ProviderNoActiveDeviceError(Exception): ...


class ProviderPremiumRequiredError(Exception): ...


class ProviderSearchQueryInvalidError(Exception): ...


# --- Advisor exceptions ---


class AdvisorRateLimitExceededError(RateLimitExceededError): ...


# --- Profiler exceptions ---


class TasteProfilerRateLimitExceededError(RateLimitExceededError): ...


class TasteProfileBuildError(Exception): ...


class TasteProfileBuildPausedError(Exception):
    def __init__(self, batch_index: int, total_batches: int, reason: str) -> None:
        self.batch_index = batch_index
        self.total_batches = total_batches
        self.reason = reason
        super().__init__(f"Build paused at batch {batch_index}/{total_batches} — {reason} — use --resume to continue")


class TasteProfileNoSeedError(Exception): ...


class TasteProfileNotFoundError(Exception): ...


class TasteProfileStatusNotReadyError(Exception): ...


# --- Enricher exceptions ---


class EnricherRateLimitExceededError(RateLimitExceededError): ...


class EnricherUnavailableError(Exception):
    """The enricher cannot serve any batch (auth, credits, unknown model, no provider, outage): stop the run."""


class TrackEnrichmentError(Exception):
    """A single batch was rejected, e.g. for its content: the run goes on."""


class TrackEnrichmentAbortedError(Exception):
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


class RateScoreInvalidError(Exception): ...


# --- Playlist exceptions ---


class PlaylistNotFoundError(Exception): ...


class PlaylistNoTracksError(Exception): ...


# --- Discovery exceptions ---


class DiscoveryTrackNoNewError(Exception): ...


class DiscoveryTasteStrategyError(Exception): ...


# --- Streaming history exceptions ---


class StreamingHistoryError(Exception): ...


class StreamingHistoryDirectoryNotFoundError(StreamingHistoryError): ...


class StreamingHistoryInvalidFormatError(StreamingHistoryError): ...
