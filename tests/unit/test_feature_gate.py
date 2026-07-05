from qa_sentinel.callbacks.feature_gate import feature_gate
from qa_sentinel.schemas.test_criteria import TestStep


class FakeCallbackContext:
    def __init__(self, state: dict):
        self.state = state


def test_blocks_when_dependency_not_passed():
    step = TestStep(
        step_id          = "create_item",
        instruction      = "Create an item",
        depends_on       = ["signup"],
        expected_outcome = "Item appears in list",
    )
    ctx = FakeCallbackContext({"current_step": step, "step.signup.status": "failed"})

    result = feature_gate(ctx)

    assert result == {"skip": True, "reason": "blocked on signup=failed"}


def test_allows_when_dependency_passed():
    step = TestStep(
        step_id          = "create_item",
        instruction      = "Create an item",
        depends_on       = ["signup"],
        expected_outcome = "Item appears in list",
    )
    ctx = FakeCallbackContext({"current_step": step, "step.signup.status": "passed"})

    assert feature_gate(ctx) is None


def test_allows_when_dependency_fixed_and_verified():
    step = TestStep(
        step_id          = "create_item",
        instruction      = "Create an item",
        depends_on       = ["signup"],
        expected_outcome = "Item appears in list",
    )
    ctx = FakeCallbackContext({"current_step": step, "step.signup.status": "fixed_and_verified"})

    assert feature_gate(ctx) is None


def test_allows_when_no_dependencies():
    step = TestStep(
        step_id          = "signup",
        instruction      = "Sign up",
        expected_outcome = "Redirect to dashboard",
    )
    ctx = FakeCallbackContext({"current_step": step})

    assert feature_gate(ctx) is None
