"""Errors the agent loop can stop on without a traceback."""


class BudgetExceededError(RuntimeError):
    """A per-run cap on LLM, search, fetch, or embed calls was hit."""


class StepLimitError(RuntimeError):
    """The hand-written loop reached its maximum number of steps."""


class TransientLLMError(RuntimeError):
    """A provider or network failure that is worth retrying."""


class OutputValidationError(RuntimeError):
    """The model output still failed Pydantic validation after repair attempts."""
