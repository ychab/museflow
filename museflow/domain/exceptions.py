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


# --- Advisor exceptions ---


class AdvisorRateLimitExceeded(RateLimitExceeded): ...


# --- Profiler exceptions ---


class ProfilerRateLimitExceeded(RateLimitExceeded): ...


class TasteProfileBuildException(Exception): ...


class TasteProfileNoSeedException(Exception): ...


class TasteProfileNotFoundException(Exception): ...


# --- Similarity track exceptions ---


class SimilarTrackResponseException(Exception): ...


# --- Discovery track exceptions ---


class DiscoveryTrackException(Exception): ...


class DiscoveryTrackNoNew(DiscoveryTrackException): ...


# --- Streaming history exceptions ---


class StreamingHistoryException(Exception): ...


class StreamingHistoryDirectoryNotFound(StreamingHistoryException): ...


class StreamingHistoryInvalidFormat(StreamingHistoryException): ...
