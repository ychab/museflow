from polyfactory import Use
from polyfactory.factories import DataclassFactory

from museflow.domain.entities.llm import LLMUsageRecord

from tests.unit.factories.value_objects.llm import LLMUsageFactory


class LLMUsageRecordFactory(DataclassFactory[LLMUsageRecord]):
    __model__ = LLMUsageRecord
    __use_defaults__ = True

    usage = Use(LLMUsageFactory.build)
