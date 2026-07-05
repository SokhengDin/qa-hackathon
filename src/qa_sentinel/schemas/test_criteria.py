from pydantic import BaseModel, Field


class TestStep(BaseModel):
    step_id            : str
    instruction        : str
    depends_on         : list[str] = Field(default_factory=list)
    expected_outcome   : str
    failure_class_hints: list[str] = Field(default_factory=list)


class TestCriteria(BaseModel):
    app_name : str
    base_url : str
    steps    : list[TestStep]

    def steps_by_id(self) -> dict[str, TestStep]:
        return {s.step_id: s for s in self.steps}
