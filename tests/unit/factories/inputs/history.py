from polyfactory import Use
from polyfactory.factories.dataclass_factory import DataclassFactory

from museflow.application.inputs.history import StreamingHistoryEntryInput


class StreamingHistoryEntryFactory(DataclassFactory[StreamingHistoryEntryInput]):
    __model__ = StreamingHistoryEntryInput

    name = Use(DataclassFactory.__faker__.name)
    artist = Use(DataclassFactory.__faker__.name)
