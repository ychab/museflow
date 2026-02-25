class UserNotFound(Exception):
    pass


class UserAlreadyExistsException(Exception):
    pass


class UserEmailAlreadyExistsException(Exception):
    pass


class UserInactive(Exception):
    pass


class UserInvalidCredentials(Exception):
    pass


class ProviderAuthTokenNotFoundError(Exception):
    pass


class ProviderExchangeCodeError(Exception):
    pass


class ProviderPageValidationError(Exception):
    pass
