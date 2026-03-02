from typing import Literal

ProviderPageErrorCodes = Literal["unsupported_local_files"]


class UserNotFound(Exception): ...


class UserAlreadyExistsException(Exception): ...


class UserEmailAlreadyExistsException(Exception): ...


class UserInactive(Exception): ...


class UserInvalidCredentials(Exception): ...


class ProviderAuthTokenNotFoundError(Exception): ...


class ProviderExchangeCodeError(Exception): ...


class ProviderPageValidationError(Exception):
    def __init__(self, msg: str, code: ProviderPageErrorCodes | None = None) -> None:
        self.code = code
        super().__init__(msg)
