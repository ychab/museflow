from enum import StrEnum


class ReasoningEffort(StrEnum):
    NONE = "none"  # Reasoning disabled
    MINIMAL = "minimal"  # ~10% of max_tokens spent on reasoning
    LOW = "low"  # ~20%
    MEDIUM = "medium"  # ~50%
    HIGH = "high"  # ~80%
    XHIGH = "xhigh"  # ~95%
    MAX = "max"  # ~95%, the model's ceiling
