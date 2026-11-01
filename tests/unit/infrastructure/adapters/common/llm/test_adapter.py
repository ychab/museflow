from unittest import mock

from museflow.infrastructure.adapters.common.llm.adapter import OpenRouterAdapterMixin
from museflow.infrastructure.adapters.common.llm.client import OpenRouterClient


class TestOpenRouterAdapterMixin:
    async def test__context_manager__closes_client(self) -> None:
        client = mock.AsyncMock(spec=OpenRouterClient)

        async with OpenRouterAdapterMixin(client=client) as adapter:
            assert isinstance(adapter, OpenRouterAdapterMixin)
            client.close.assert_not_awaited()

        client.close.assert_awaited_once_with()
