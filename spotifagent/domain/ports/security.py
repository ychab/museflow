from abc import ABC
from abc import abstractmethod
from typing import Any


class PasswordHasherPort(ABC):
    """Interface for hashing and verifying passwords."""

    @abstractmethod
    def hash(self, password: str) -> str:
        """Hash a plain text password."""
        pass

    @abstractmethod
    def verify(self, plain_password: str, hashed_password: str) -> bool:
        """Verify a plain password against a hash."""
        pass


class AccessTokenManagerPort(ABC):
    """Interface for creating and managing access tokens (JWT, etc)."""

    @abstractmethod
    def create(self, data: dict[str, Any]) -> str:
        """Create a signed access token with expiration."""
        pass

    @abstractmethod
    def decode(self, token: str) -> dict[str, Any]:
        """Decode and validate an access token."""
        pass


class StateTokenGeneratorPort(ABC):
    """Interface for generating random state tokens."""

    @abstractmethod
    def generate(self, length: int = 30) -> str:
        """Generate a random string of specified length."""
        pass
