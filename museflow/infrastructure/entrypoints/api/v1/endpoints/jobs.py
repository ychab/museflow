import uuid

from fastapi import APIRouter

from museflow.application.use_cases.job_get import get_job
from museflow.application.use_cases.job_list import get_jobs
from museflow.infrastructure.entrypoints.api.dependencies import CurrentUserDep
from museflow.infrastructure.entrypoints.api.dependencies import PageParamsDep
from museflow.infrastructure.entrypoints.api.dependencies import UnitOfWorkDep
from museflow.infrastructure.entrypoints.api.v1.schemas.common import PageResponse
from museflow.infrastructure.entrypoints.api.v1.schemas.jobs import JobResponse

router = APIRouter()


@router.get("", name="job_list")
async def list_jobs(
    *,
    page_params: PageParamsDep,
    current_user: CurrentUserDep,
    uow: UnitOfWorkDep,
) -> PageResponse[JobResponse]:
    """The user's background jobs, the newest first."""
    page = await get_jobs(user=current_user, uow=uow, limit=page_params.limit, offset=page_params.offset)
    return PageResponse[JobResponse].model_validate(page)


@router.get("/{job_id}", name="job_get")
async def view_job(job_id: uuid.UUID, current_user: CurrentUserDep, uow: UnitOfWorkDep) -> JobResponse:
    """A background job, polled until it is done or failed: another user's job is a 404, as an unknown one."""
    job = await get_job(user=current_user, job_id=job_id, uow=uow)
    return JobResponse.model_validate(job)
