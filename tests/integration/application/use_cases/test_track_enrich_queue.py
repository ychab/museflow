import pytest

from museflow.application.inputs.enrich import EnrichTracksJobInput
from museflow.application.ports.unit_of_work import UnitOfWorkPort
from museflow.application.use_cases.track_enrich_queue import queue_track_enrichment
from museflow.domain.entities.user import User
from museflow.domain.enums import EnrichField
from museflow.domain.enums import JobKind
from museflow.domain.enums import JobStatus
from museflow.domain.exceptions import JobAlreadyActiveError

from tests.integration.factories.models.job import JobModelFactory


class TestQueueTrackEnrichment:
    async def test__nominal(self, user: User, uow: UnitOfWorkPort) -> None:
        job_in = EnrichTracksJobInput(fields=frozenset({EnrichField.MOOD, EnrichField.GENRE}))

        job = await queue_track_enrichment(user=user, job_in=job_in, uow=uow)

        assert job.kind == JobKind.TRACK_ENRICH
        assert job.status == JobStatus.PENDING
        assert job.input == {"fields": ["genre", "mood"]}
        async with uow:
            assert await uow.jobs.get(user.id, job.id) == job

    async def test__already_active(self, user: User, uow: UnitOfWorkPort) -> None:
        await JobModelFactory.create_async(
            user_id=user.id,
            kind=JobKind.TRACK_ENRICH,
            status=JobStatus.RUNNING,
            input=EnrichTracksJobInput().model_dump(mode="json"),
        )

        with pytest.raises(JobAlreadyActiveError):
            await queue_track_enrichment(user=user, job_in=EnrichTracksJobInput(), uow=uow)

    async def test__other_kind_active(self, user: User, uow: UnitOfWorkPort) -> None:
        # One job of each kind at a time: an import running does not hold the enrichment back
        await JobModelFactory.create_async(user_id=user.id, status=JobStatus.RUNNING)

        job = await queue_track_enrichment(user=user, job_in=EnrichTracksJobInput(), uow=uow)

        assert job.input == {"fields": ["genre", "locale", "mood"]}
