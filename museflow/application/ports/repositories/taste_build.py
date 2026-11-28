import uuid
from abc import ABC
from abc import abstractmethod
from datetime import timedelta


class TasteProfileBuildRepository(ABC):
    """The lease a taste profile build holds on a profile name, so that two builds never run on it at once.

    Each build draws a `build_id`, its fencing token: the lease names the build holding it, and every write of a build
    checks it first. The lease times use the database clock, the same for every process.
    """

    @abstractmethod
    async def claim(
        self,
        user_id: uuid.UUID,
        name: str,
        build_id: uuid.UUID,
        job_id: uuid.UUID | None,
        lease_duration: timedelta,
    ) -> bool:
        """Takes the lease of the profile name, unless another build holds it and its lease has not expired.

        Args:
            job_id: The job running the build, if any. A lease held by a try of the same job is taken over at once,
                expired or not: that try died, since a job runs one try at a time.

        Returns:
            True if the build now holds the lease, False if another build does.
        """
        ...

    @abstractmethod
    async def renew(self, user_id: uuid.UUID, name: str, build_id: uuid.UUID, lease_duration: timedelta) -> bool:
        """Extends the lease, only if the build still holds it, expired or not.

        Call it in the block of each write of the build: the lease row stays locked until the block commits, so no
        other build can take the lease over between the check and the write.

        Returns:
            True if the build still holds the lease, False if another build took it over.
        """
        ...

    @abstractmethod
    async def is_held(self, user_id: uuid.UUID, name: str) -> bool:
        """Tells whether a build holds the lease of the profile name, unexpired."""
        ...

    @abstractmethod
    async def release(self, user_id: uuid.UUID, name: str, build_id: uuid.UUID) -> None:
        """Gives the lease up, only if the build still holds it."""
        ...
