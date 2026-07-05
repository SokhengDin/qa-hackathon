from google.adk import Workflow

from qa_sentinel.agents.fix_writer import fix_writer_agent
from qa_sentinel.agents.pr_agent import pr_agent
from qa_sentinel.agents.test_runner import test_runner_agent
from qa_sentinel.agents.verifier import verifier_agent

root_agent = Workflow(
    name  = "qa_sentinel_pipeline",
    edges = [
        ("START"          , test_runner_agent),
        # TestRunner's own after_agent_callback (compute_step_verdict) sets
        # actions.route to "needs_fix" only when the step actually failed with
        # medium/high confidence evidence. A passing step, or a low-confidence
        # failure routed to human review, emits no matching route here and the
        # graph terminates at TestRunner for that step — FixWriter/Verifier/
        # PRAgent never run for steps that don't need them.
        (test_runner_agent, {"needs_fix": fix_writer_agent}),
        (fix_writer_agent , verifier_agent),
        (verifier_agent   , pr_agent),           # only proceeds if verifier confirms fix
    ],
)
