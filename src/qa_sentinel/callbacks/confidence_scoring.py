def score_confidence(has_console: bool, has_network: bool, intent_explains: bool) -> float:
    """Mirrors the Vultr track's own finance example: a confidence score reflecting
    how many flagged transactions were matched to a clear cause versus left
    unexplained.

    High:   console error + network failure + intent explains the mismatch
            -> auto-proceed to FixWriter.
    Medium: only one of (console error / network failure) present
            -> proceed, but flag "partial evidence" in the PR description.
    Low:    neither present (agent just says "it looked wrong")
            -> route to human review. Never let FixWriter act on this.
    """
    if has_console and has_network and intent_explains:
        return 0.9
    if has_console or has_network:
        return 0.5
    return 0.1
