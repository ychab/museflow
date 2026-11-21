import asyncio
from collections.abc import Coroutine
from typing import Any

from museflow.infrastructure.entrypoints.wiring import Wiring

# The event loop and the wiring of the running worker process, open between `open_process` and `close_process`.
process: WorkerProcess | None = None


class WorkerProcess:
    """The event loop of one worker process, with the wiring opened in it, kept for the life of the process.

    The pooled connections of the wiring are bound to the loop that opened them: every task of the process runs on
    this one, so that they share the pool, where `asyncio.run()` per task would rebuild it every time. The runner is
    synchronous, so it enters and exits the async context manager of the wiring by hand.
    """

    def __init__(self) -> None:
        self._runner = asyncio.Runner()
        self._opened = Wiring.open()
        self.wiring = self._runner.run(self._opened.__aenter__())

    def run[T](self, main: Coroutine[Any, Any, T]) -> T:
        return self._runner.run(main)

    def close(self) -> None:
        try:
            self._runner.run(self._opened.__aexit__(None, None, None))
        finally:
            self._runner.close()


# --- Process ---


def open_process() -> None:
    """Opens the event loop and the wiring of a worker process: call it in the process, after the fork."""
    global process
    process = WorkerProcess()


def close_process() -> None:
    global process

    if process is not None:
        process.close()
        process = None


# --- Tasks ---


def run_task[T](main: Coroutine[Any, Any, T]) -> T:
    """Runs the coroutine of a task on the event loop of the process."""
    return _get_process().run(main)


def get_wiring() -> Wiring:
    """The wiring of the process, for the coroutine of a task."""
    return _get_process().wiring


def _get_process() -> WorkerProcess:
    if process is None:
        raise RuntimeError("No worker process open: run the task in a worker started by Celery")
    return process
