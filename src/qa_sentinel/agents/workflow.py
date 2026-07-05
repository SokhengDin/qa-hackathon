from google.adk import Workflow

from qa_sentinel.agents.fix_writer import fix_writer_agent
from qa_sentinel.agents.pr_agent import pr_agent
from qa_sentinel.agents.test_runner import test_runner_agent
from qa_sentinel.agents.verifier import verifier_agent

root_agent = Workflow(
    name  = "qa_sentinel_pipeline",
    edges = [
        ("START"          , test_runner_agent),
        (test_runner_agent, fix_writer_agent),   # only proceeds if confidence gate passes
        (fix_writer_agent , verifier_agent),
        (verifier_agent   , pr_agent),           # only proceeds if verifier confirms fix
    ],
)
