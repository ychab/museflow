from collections.abc import AsyncGenerator

import pytest

from museflow.infrastructure.entrypoints.wiring import Wiring


@pytest.fixture
async def wiring() -> AsyncGenerator[Wiring]:
    """The real wiring: the live tests reach the remote services only, its engine never connects."""
    async with Wiring.open() as wiring:
        yield wiring
