from polyfactory import Use
from polyfactory.factories.dataclass_factory import DataclassFactory

from museflow.domain.value_objects.llm import LLMUsage


class LLMUsageFactory(DataclassFactory[LLMUsage]):
    __model__ = LLMUsage
    __set_as_default_factory_for_type__ = True

    # The domain sets no limit, unlike the Numeric(12, 6) column: an unbounded decimal would not fit on save.
    cost = Use(DataclassFactory.__faker__.pydecimal, left_digits=1, right_digits=6, positive=True)
