from datetime import datetime

from qa_sentinel.schemas.evidence_bundle import EvidenceBundle


def test_has_console_evidence_true_when_errors_present():
    bundle = EvidenceBundle(
        step_id             = "create_item",
        screenshot_path     = "/tmp/x.png",
        console_errors      = [{"level": "error", "text": "boom"}],
        model_stated_intent = "Clicked create item button",
        confidence          = 0.9,
    )
    assert bundle.has_console_evidence is True
    assert bundle.has_network_evidence is False


def test_no_evidence_when_lists_empty():
    bundle = EvidenceBundle(
        step_id             = "create_item",
        screenshot_path     = "/tmp/x.png",
        model_stated_intent = "Clicked create item button",
        confidence          = 0.1,
    )
    assert bundle.has_console_evidence is False
    assert bundle.has_network_evidence is False
    assert isinstance(bundle.timestamp, datetime)
