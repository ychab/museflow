from types import TracebackType
from typing import Self

from museflow.domain.value_objects.llm import LLMUsage
from museflow.infrastructure.adapters.common.llm.client import OpenRouterClient


class OpenRouterAdapterMixin:
    """Lifecycle shared by the LLM adapters: each owns the OpenRouter client it is given and closes it."""

    def __init__(self, client: OpenRouterClient) -> None:
        self._client = client

    @property
    def usages(self) -> list[LLMUsage]:
        return self._client.usages

    async def close(self) -> None:
        await self._client.close()

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        await self.close()
