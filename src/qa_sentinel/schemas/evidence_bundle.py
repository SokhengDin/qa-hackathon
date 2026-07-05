from datetime import datetime

from pydantic import BaseModel, Field


class EvidenceBundle(BaseModel):
    step_id             : str
    screenshot_path     : str
    console_errors      : list[dict] = Field(default_factory=list)
    network_failures    : list[dict] = Field(default_factory=list)
    model_stated_intent : str
    confidence          : float
    timestamp           : datetime = Field(default_factory=datetime.utcnow)

    @property
    def has_console_evidence(self) -> bool:
        return len(self.console_errors) > 0

    @property
    def has_network_evidence(self) -> bool:
        return len(self.network_failures) > 0
