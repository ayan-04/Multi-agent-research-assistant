"""Step counter for the hand-written loop."""

from __future__ import annotations

from src.errors import StepLimitError


class StepGuard:
    def __init__(self, max_steps: int) -> None:
        self.max_steps = max_steps
        self.steps = 0

    def tick(self, action: str) -> None:
        if self.steps >= self.max_steps:
            raise StepLimitError(f"step limit reached before {action}")
        self.steps += 1
