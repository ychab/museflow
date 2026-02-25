import random
import string
from datetime import UTC
from datetime import datetime
from datetime import timedelta
from typing import Any

import jwt
from argon2 import PasswordHasher as Argon2Hasher
from argon2.exceptions import Argon2Error
from argon2.exceptions import InvalidHashError

from museflow.domain.ports.security import AccessTokenManagerPort
from museflow.domain.ports.security import PasswordHasherPort
from museflow.domain.ports.security import StateTokenGeneratorPort
from museflow.infrastructure.config.settings.app import app_settings


class Argon2PasswordHasher(PasswordHasherPort):
    """
    Implementation of PasswordHasher port using Argon2.
    """

    def __init__(self) -> None:
        self._ph = Argon2Hasher()

    def hash(self, password: str) -> str:
        return self._ph.hash(password)

    def verify(self, plain_password: str, hashed_password: str) -> bool:
        try:
            return self._ph.verify(hashed_password, plain_password)
        except (Argon2Error, InvalidHashError):
            return False


class JwtAccessTokenManager(AccessTokenManagerPort):
    """
    Implementation of TokenManager port using PyJWT.
    """

    def create(self, data: dict[str, Any]) -> str:
        to_encode = data.copy()
        expire = datetime.now(UTC) + timedelta(minutes=app_settings.ACCESS_TOKEN_EXPIRE_MINUTES)

        to_encode.update({"exp": expire, "iat": datetime.now(UTC)})

        return jwt.encode(to_encode, app_settings.SECRET_KEY, algorithm=app_settings.ACCESS_TOKEN_ALGORITHM)

    def decode(self, token: str) -> dict[str, Any]:
        return jwt.decode(token, app_settings.SECRET_KEY, algorithms=[app_settings.ACCESS_TOKEN_ALGORITHM])


class SystemStateTokenGenerator(StateTokenGeneratorPort):
    """
    Implementation of RandomTokenGenerator port using random.SystemRandom.
    """

    UNICODE_ASCII_CHARACTER_SET = string.ascii_letters + string.digits

    def generate(self, length: int = 30) -> str:
        rand = random.SystemRandom()
        return "".join(rand.choice(self.UNICODE_ASCII_CHARACTER_SET) for _ in range(length))
