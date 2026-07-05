from qa_sentinel.callbacks.confidence_scoring import score_confidence


def test_high_confidence_requires_console_network_and_intent():
    assert score_confidence(has_console=True, has_network=True, intent_explains=True) == 0.9


def test_high_confidence_not_awarded_if_intent_does_not_explain():
    assert score_confidence(has_console=True, has_network=True, intent_explains=False) == 0.5


def test_medium_confidence_with_only_console():
    assert score_confidence(has_console=True, has_network=False, intent_explains=False) == 0.5


def test_medium_confidence_with_only_network():
    assert score_confidence(has_console=False, has_network=True, intent_explains=False) == 0.5


def test_low_confidence_with_no_evidence():
    assert score_confidence(has_console=False, has_network=False, intent_explains=False) == 0.1
