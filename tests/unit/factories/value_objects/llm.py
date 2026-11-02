from polyfactory import Use
from polyfactory.factories.dataclass_factory import DataclassFactory

from museflow.domain.value_objects.llm import LLMUsage


class LLMUsageFactory(DataclassFactory[LLMUsage]):
    __model__ = LLMUsage
    __set_as_default_factory_for_type__ = True

    # Bounded to fit the columns: 4-byte integers and Numeric(12, 6).
    calls = Use(DataclassFactory.__faker__.pyint, min_value=1, max_value=10)
    prompt_tokens = Use(DataclassFactory.__faker__.pyint, max_value=100_000)
    completion_tokens = Use(DataclassFactory.__faker__.pyint, max_value=100_000)
    reasoning_tokens = Use(DataclassFactory.__faker__.pyint, max_value=100_000)
    cost = Use(DataclassFactory.__faker__.pydecimal, left_digits=1, right_digits=6, positive=True)
