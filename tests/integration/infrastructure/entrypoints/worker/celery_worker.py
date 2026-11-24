import os
import signal
import subprocess
import sys
import uuid
from pathlib import Path
from types import TracebackType
from typing import Final
from typing import Self

from tenacity import Retrying
from tenacity import retry_if_result
from tenacity import stop_after_delay

from museflow.infrastructure.entrypoints.worker.main import celery_app


class CeleryWorker:
    """A real Celery worker, prefork, run in a process of its own like `celery worker`, with the test tasks loaded.

    Started as a context manager, ready once it answers a ping; stopped on exit. `kill` ends it at once, its processes
    with it, as a crash would: nothing gets acknowledged.
    """

    _READY_TIMEOUT_SECONDS: Final[float] = 30.0

    _process: subprocess.Popen[bytes]

    def __init__(
        self,
        broker_url: str,
        database_uri: str,
        file_storage_dir: Path,
        log_file: Path,
        queues: list[str] | None = None,
    ) -> None:
        """`queues`: those it consumes, all of them by default, as `celery worker` without `--queues`."""
        self.name = f"test-{uuid.uuid4().hex[:8]}@museflow"
        self._broker_url = broker_url
        self._database_uri = database_uri
        self._file_storage_dir = file_storage_dir
        self._log_file = log_file
        self._queues = queues

    def __enter__(self) -> Self:
        self.start()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        self.stop()

    @property
    def logs(self) -> str:
        return self._log_file.read_text() if self._log_file.exists() else ""

    def start(self) -> None:
        env = {
            **os.environ,
            "BROKER_URL": self._broker_url,
            "DATABASE_URI": self._database_uri,
            "MUSEFLOW_FILE_STORAGE_DIR": str(self._file_storage_dir),
            # Caps small enough for a test's zip bomb to stay small
            "MUSEFLOW_HISTORY_EXTRACTED_FILE_MAX_SIZE_MB": "1",
            "MUSEFLOW_HISTORY_EXTRACTED_TOTAL_MAX_SIZE_MB": "2",
            "MUSEFLOW_LOG_HANDLERS_WORKER": '["console"]',
            # A retry without waiting
            "MUSEFLOW_WORKER_TASK_RETRY_BACKOFF_MAX_SECONDS": "1",
        }
        command = [
            sys.executable,
            "-m",
            "celery",
            "--app",
            "museflow.infrastructure.entrypoints.worker.main",
            "worker",
            "--include",
            "tests.integration.infrastructure.entrypoints.worker.stub_tasks",
            "--hostname",
            self.name,
            "--concurrency",
            "1",
            "--without-gossip",
            "--without-mingle",
        ]
        if self._queues is not None:
            command += ["--queues", ",".join(self._queues)]

        with self._log_file.open("ab") as log:
            # A session of its own, so that `kill` reaches its child processes too
            self._process = subprocess.Popen(
                command, env=env, stdout=log, stderr=subprocess.STDOUT, start_new_session=True
            )

        self._wait_ready()

    def stop(self) -> None:
        """A warm shutdown, as `docker compose stop` asks; nothing left to do once killed."""
        self._process.terminate()
        self._process.wait(timeout=10)

    def kill(self) -> None:
        os.killpg(self._process.pid, signal.SIGKILL)
        self._process.wait()

    def _wait_ready(self) -> None:
        # The ping goes to the worker's own queue, which only exists once it started: a ping sent earlier is lost
        ping = Retrying(
            stop=stop_after_delay(self._READY_TIMEOUT_SECONDS),
            retry=retry_if_result(lambda replies: not replies),
        )
        ping(celery_app.control.ping, destination=[self.name], timeout=0.5)
