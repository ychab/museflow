from museflow.application.ports.archive import ArchivePort
from museflow.application.ports.providers.history import StreamingHistoryPort
from museflow.application.ports.storage import FileStoragePort
from museflow.domain.entities.user import User
from museflow.domain.exceptions import StreamingHistoryFilesNotFoundError


async def extract_history_archive(
    user: User,
    archive: bytes,
    prefix: str,
    file_storage: FileStoragePort,
    archive_reader: ArchivePort,
    streaming_history: StreamingHistoryPort,
) -> int:
    """Extracts the provider's streaming history files of the export archive into the user's file storage, under the
    prefix, and returns how many. The other files of the export are skipped.

    Each file goes under a folder of its rank in the archive: two files of the same name, from two folders of the
    archive, are both kept (the import skips the plays saved twice). A second run writes them under the same keys. On
    an error, the files already written stay: the caller deletes the prefix, as it does after the import.

    Raises:
        ArchiveInvalidError: If the archive can't be read.
        ArchiveTooLargeError: If it goes beyond a cap.
        StreamingHistoryFilesNotFoundError: If it holds no streaming history file.
    """
    pattern = streaming_history.file_pattern

    files_count = 0
    for archive_file in archive_reader.extract(archive, pattern=pattern):
        key = f"{prefix}/{archive_file.rank}/{archive_file.name}"
        await file_storage.put(user_id=user.id, key=key, content=archive_file.content)
        files_count += 1

    if not files_count:
        raise StreamingHistoryFilesNotFoundError(f"No {pattern} files found in the archive")
    return files_count
