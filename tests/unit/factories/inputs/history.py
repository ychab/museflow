from polyfactory import Use
from polyfactory.factories.dataclass_factory import DataclassFactory

from museflow.application.inputs.history import StreamingHistoryEntry


class StreamingHistoryEntryFactory(DataclassFactory[StreamingHistoryEntry]):
    __model__ = StreamingHistoryEntry

    name = Use(DataclassFactory.__faker__.name)
    artist = Use(DataclassFactory.__faker__.name)
