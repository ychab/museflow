from abc import ABC
from abc import abstractmethod
from typing import Any


class PasswordHasherPort(ABC):
    """Interface for hashing and verifying passwords.

    This port abstracts the underlying password hashing mechanism, allowing the
    application to use different hashing algorithms without changing the core
    business logic.
    """

    @abstractmethod
    def hash(self, password: str) -> str:
        """Hashes a plain text password.

        Args:
            password: The plain text password to hash.

        Returns:
            The hashed password string.
        """
        pass

    @abstractmethod
    def verify(self, plain_password: str, hashed_password: str) -> bool:
        """Verifies a plain password against a previously hashed password.

        Args:
            plain_password: The plain text password provided by the user.
            hashed_password: The stored hashed password.

        Returns:
            True if the plain password matches the hashed password, False otherwise.
        """
        pass


class AccessTokenManagerPort(ABC):
    """Interface for creating, decoding, and managing access tokens (e.g., JWT).

    This port handles the lifecycle of access tokens used for user authentication
    and authorization within the application.
    """

    @abstractmethod
    def create(self, data: dict[str, Any]) -> str:
        """Creates a signed access token with an embedded payload and expiration.

        Args:
            data: A dictionary containing the claims to be encoded in the token.

        Returns:
            The encoded and signed access token string.
        """
        pass

    @abstractmethod
    def decode(self, token: str) -> dict[str, Any]:
        """Decodes and validates an access token.

        Args:
            token: The access token string to decode.

        Returns:
            A dictionary containing the decoded claims if the token is valid.

        Raises:
            Any exception related to token validation (e.g., expiration, invalid signature).
        """
        pass


class StateTokenGeneratorPort(ABC):
    """Interface for generating random state tokens.

    These tokens are typically used in OAuth flows to maintain state between
    redirects and prevent CSRF attacks.
    """

    @abstractmethod
    def generate(self, length: int = 30) -> str:
        """Generates a random string of a specified length.

        Args:
            length: The desired length of the generated string.

        Returns:
            A random string suitable for use as a state token.
        """
        pass
