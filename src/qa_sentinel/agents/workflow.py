from google.adk import Workflow

from qa_sentinel.agents.fixer import fixer_agent
from qa_sentinel.agents.pr_agent import pr_agent
from qa_sentinel.agents.test_runner import test_runner_agent
from qa_sentinel.agents.verifier import verifier_agent

root_agent = Workflow(
    name  = "qa_sentinel_pipeline",
    edges = [
        ("START"          , test_runner_agent),
        # TestRunner's own after_agent_callback (compute_step_verdict) sets
        # actions.route based on the step's real outcome:
        #   - clean pass, no prior fix attempt -> no route, graph ends here.
        #   - "needs_fix"       -> route to FixerAgent (medium/high confidence failure).
        #   - "needs_human_review" -> no further automated action (low confidence,
        #     or fix attempts exhausted per MAX_FIX_ATTEMPTS).
        #   - "fix_confirmed"   -> a pass AFTER at least one fix attempt: the
        #     loop-back re-test genuinely succeeded, proceed to Verifier/PRAgent.
        (test_runner_agent, {
            "needs_fix"    : fixer_agent,
            "fix_confirmed": verifier_agent,
        }),
        # FixerAgent writes+restarts+self-verifies, then loops back to
        # TestRunner to re-run the ORIGINAL failing step for real, through the
        # actual browser — this is the "second primitive only fires because
        # the first is already running" loop, not a one-shot guess.
        (fixer_agent, test_runner_agent),
        (verifier_agent, pr_agent),  # only proceeds if verifier confirms the branch landed
    ],
)
