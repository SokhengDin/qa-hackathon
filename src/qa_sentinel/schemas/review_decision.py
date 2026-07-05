from typing import Literal

from pydantic import BaseModel


class ReviewDecision(BaseModel):
    step_id      : str
    decision     : Literal["approved", "rejected", "false_positive"]
    reviewer_note: str | None = None
