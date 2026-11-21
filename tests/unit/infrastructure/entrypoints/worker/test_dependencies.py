import pytest

from museflow.infrastructure.entrypoints.worker import dependencies
from museflow.infrastructure.entrypoints.worker.dependencies import close_process
from museflow.infrastructure.entrypoints.worker.dependencies import get_wiring


class TestWorkerProcess:
    def test__get_wiring__not_open(self) -> None:
        with pytest.raises(RuntimeError, match="No worker process open"):
            get_wiring()

    def test__close_process__not_open(self) -> None:
        # The shutdown of a process whose start failed
        close_process()

        assert dependencies.process is None
