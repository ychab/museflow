import random
import secrets
import string
from collections.abc import Sequence
from datetime import UTC
from datetime import datetime
from datetime import timedelta
from functools import cache
from typing import Any
from typing import Final

from pydantic import SecretStr

import jwt
from argon2 import PasswordHasher as Argon2Hasher
from argon2.exceptions import Argon2Error
from argon2.exceptions import InvalidHashError
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESSIV
from cryptography.hazmat.primitives.hashes import SHA256
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from museflow.application.ports.security import AccessTokenManagerPort
from museflow.application.ports.security import PasswordHasherPort
from museflow.application.ports.security import StateTokenGeneratorPort
from museflow.application.ports.security import TokenCipherPort
from museflow.domain.exceptions import TokenDecryptionError
from museflow.infrastructure.config.settings.app import app_settings


class Argon2PasswordHasher(PasswordHasherPort):
    """An implementation of the `PasswordHasherPort` using the Argon2 algorithm.

    This class provides a secure way to hash and verify passwords, using the
    `argon2-cffi` library.
    """

    def __init__(self) -> None:
        self._ph = Argon2Hasher()

    def hash(self, password: str) -> str:
        return self._ph.hash(password)

    def verify(self, plain_password: str, hashed_password: str) -> bool:
        try:
            return self._ph.verify(hashed_password, plain_password)
        except Argon2Error, InvalidHashError:
            return False

    def verify_simulate(self, plain_password: str) -> None:
        self.verify(plain_password, _get_dummy_hash())


class JwtAccessTokenManager(AccessTokenManagerPort):
    """An implementation of the `AccessTokenManagerPort` using JSON Web Tokens (JWT).

    This class handles the creation and decoding of JWTs for user authentication,
    relying on the `PyJWT` library.
    """

    def create(self, data: dict[str, Any]) -> str:
        to_encode = data.copy()
        expire = datetime.now(UTC) + timedelta(minutes=app_settings.JWT_EXPIRE_MINUTES)

        to_encode.update({"exp": expire, "iat": datetime.now(UTC)})

        return jwt.encode(
            to_encode, app_settings.JWT_SIGNING_KEY.get_secret_value(), algorithm=app_settings.JWT_ALGORITHM
        )

    def decode(self, token: str) -> dict[str, Any]:
        return jwt.decode(
            token, app_settings.JWT_SIGNING_KEY.get_secret_value(), algorithms=[app_settings.JWT_ALGORITHM]
        )


class AesSivTokenCipher(TokenCipherPort):
    """An implementation of `TokenCipherPort` using AES-SIV (RFC 5297), from the `cryptography` library.

    SIV derives its IV from the value and the context instead of drawing it at random: the encryption is
    deterministic, as the port requires, and stays authenticated (an altered value fails to decrypt). Equal values in
    one context give equal bytes, which reveals nothing here: the tokens are random and each row has its own context.

    Decryption tries the current key, then the former ones (as `MultiFernet` does): a wrong key fails the
    authentication, so it never gives a wrong value, and the stored bytes need no key id.
    """

    # AES-256-SIV takes two AES-256 keys: 64 bytes
    _KEY_LENGTH: Final[int] = 64
    _KEY_INFO: Final[bytes] = b"museflow provider token encryption"

    def __init__(self, key: SecretStr, fallback_keys: Sequence[SecretStr] = ()) -> None:
        # The current key first: it encrypts, and is tried first to decrypt
        self._aes_sivs = [AESSIV(self._derive_key(secret)) for secret in (key, *fallback_keys)]

    def encrypt(self, plaintext: str, context: str) -> bytes:
        return self._aes_sivs[0].encrypt(plaintext.encode(), [context.encode()])

    def encrypt_with_each_key(self, plaintext: str, context: str) -> list[bytes]:
        return [aes_siv.encrypt(plaintext.encode(), [context.encode()]) for aes_siv in self._aes_sivs]

    def decrypt(self, ciphertext: bytes, context: str) -> str:
        for aes_siv in self._aes_sivs:
            try:
                plaintext = aes_siv.decrypt(ciphertext, [context.encode()])
            except InvalidTag:
                continue
            return plaintext.decode()

        raise TokenDecryptionError("The token was altered, or encrypted with none of the keys or for another context")

    @classmethod
    def _derive_key(cls, secret: SecretStr) -> bytes:
        # HKDF turns a secret of the settings (any string of 32+ characters) into a key of the length AES-SIV needs
        return HKDF(algorithm=SHA256(), length=cls._KEY_LENGTH, salt=None, info=cls._KEY_INFO).derive(
            secret.get_secret_value().encode()
        )


class SystemStateTokenGenerator(StateTokenGeneratorPort):
    """An implementation of `StateTokenGeneratorPort` using `random.SystemRandom`.

    This class generates cryptographically secure random strings suitable for use as
    state tokens in OAuth flows.
    """

    UNICODE_ASCII_CHARACTER_SET: Final[str] = string.ascii_letters + string.digits

    def generate(self, length: int = 30) -> str:
        rand = random.SystemRandom()
        return "".join(rand.choice(self.UNICODE_ASCII_CHARACTER_SET) for _ in range(length))


@cache
def _get_dummy_hash() -> str:
    # Hashed once per process: the hasher is created per request, and a request must only pay for the verification.
    return Argon2Hasher().hash(secrets.token_urlsafe())
