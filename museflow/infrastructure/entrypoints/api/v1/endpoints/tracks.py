from typing import Annotated

from fastapi import APIRouter
from fastapi import File
from fastapi import Form
from fastapi import Request
from fastapi import Response
from fastapi import UploadFile
from fastapi import status

from museflow.application.inputs.history import ImportStreamingHistoryConfigInput
from museflow.application.use_cases.track_history_import_queue import queue_history_import
from museflow.domain.enums import MusicProvider
from museflow.infrastructure.entrypoints.api.dependencies import ArchiveReaderDep
from museflow.infrastructure.entrypoints.api.dependencies import CurrentUserDep
from museflow.infrastructure.entrypoints.api.dependencies import FileStorageDep
from museflow.infrastructure.entrypoints.api.dependencies import UnitOfWorkDep
from museflow.infrastructure.entrypoints.api.schemas import ProblemDetails
from museflow.infrastructure.entrypoints.api.v1.schemas.jobs import JobResponse

router = APIRouter()


@router.post(
    "/streaming-history",
    name="track_streaming_history_import",
    status_code=status.HTTP_202_ACCEPTED,
    responses={
        status.HTTP_409_CONFLICT: {"model": ProblemDetails, "description": "A history import is already running"},
        status.HTTP_413_CONTENT_TOO_LARGE: {"model": ProblemDetails, "description": "The archive is too large"},
        status.HTTP_415_UNSUPPORTED_MEDIA_TYPE: {"model": ProblemDetails, "description": "Not a zip archive"},
    },
)
async def import_streaming_history(
    *,
    archive: Annotated[
        UploadFile, File(description="The zip archive of the extended streaming history, as Spotify delivers it")
    ],
    provider: Annotated[
        MusicProvider, Form(description="The music provider the export comes from")
    ] = MusicProvider.SPOTIFY,
    min_duration_played: Annotated[
        int, Form(ge=0, le=86_400, description="The least a play lasted to be kept, in seconds")
    ] = ImportStreamingHistoryConfigInput.min_ms_played // 1_000,
    purge: Annotated[bool, Form(description="Purges the existing tracks before the import")] = False,
    request: Request,
    response: Response,
    current_user: CurrentUserDep,
    uow: UnitOfWorkDep,
    file_storage: FileStorageDep,
    archive_reader: ArchiveReaderDep,
) -> JobResponse:
    """Queues the import of a streaming history export: poll the job it answers until it is done or failed.

    The archive is stored as is; a worker extracts and imports it. Its size is capped by the reverse proxy in front.
    """
    content = await archive.read()

    job = await queue_history_import(
        user=current_user,
        archive=content,
        provider=provider,
        min_ms_played=min_duration_played * 1_000,
        purge=purge,
        uow=uow,
        file_storage=file_storage,
        archive_reader=archive_reader,
    )

    response.headers["Location"] = request.app.url_path_for("job_get", job_id=str(job.id))
    return JobResponse.model_validate(job)
