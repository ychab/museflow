import asyncio
from collections.abc import Coroutine
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from museflow.infrastructure.entrypoints.wiring import Wiring

# The wiring of the running command, open between the start and the end of `init_logic_runner`.
wiring: Wiring | None = None


# --- Event loop ---


def run_logic[T](main: Coroutine[Any, Any, T]) -> T:
    """Runs a command's logic like `asyncio.run`, with the wiring open for the run."""
    with init_logic_runner() as runner:
        result = runner.run(main)
    return result


@contextmanager
def init_logic_runner() -> Iterator[asyncio.Runner]:
    """An `asyncio.Runner` with the wiring open, for a command that prints between two steps of its logic.

    The wiring is opened in the runner's event loop, which the pooled connections of its resources are bound to, and
    closed in that loop when the command ends: a second loop could not reuse them. The runner is synchronous, so it
    enters and exits the async context manager by hand.
    """
    global wiring

    with asyncio.Runner() as runner:
        opened = Wiring.open()
        wiring = runner.run(opened.__aenter__())

        try:
            yield runner
        finally:
            wiring = None
            runner.run(opened.__aexit__(None, None, None))


# --- Wiring ---


def get_wiring() -> Wiring:
    """The wiring of the running command.

    Raises:
        RuntimeError: If the command runs its logic without `run_logic` or `init_logic_runner`.
    """
    if wiring is None:
        raise RuntimeError("No wiring open: run the command logic through run_logic()")
    return wiring
