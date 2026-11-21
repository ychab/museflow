from abc import ABC
from abc import abstractmethod

from museflow.application.outputs.progress import ProgressEvent


class ProgressPort(ABC):
    """Abstract port for the display that follows a long-running flow as it runs.

    A one-way notification: the flow never waits for an answer, and nothing it publishes changes what it does. The
    events are data; each adapter words them for its own client.
    """

    @abstractmethod
    async def publish(self, event: ProgressEvent) -> None:
        """Publishes one event: a step that starts, or the outcome of the step that ran."""
        ...
