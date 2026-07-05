import re

import yaml

from qa_sentinel.schemas.test_criteria import TestCriteria, TestStep

FRONTMATTER_RE  = re.compile(r"^---\n(.*?)\n---\n(.*)$", re.DOTALL)
STEP_HEADING_RE = re.compile(r"^##\s+(\S+)\s*$", re.MULTILINE)
FIELD_RE        = re.compile(r"^-\s*(\w+):\s*(.*)$")


def parse_test_criteria_md(content: str) -> TestCriteria:
    """Parses the .md test-criteria format a user uploads alongside
    POST /api/agent/runs: YAML frontmatter for app-level fields (app_name,
    base_url), then one '## step_id' heading per step, with a free-text
    instruction paragraph followed by '- field: value' bullet lines for
    expected_outcome/depends_on/failure_class_hints.

    See configs/test_criteria/example_app.md for a worked example."""
    match = FRONTMATTER_RE.match(content.strip() + "\n")
    if not match:
        raise ValueError("test criteria .md must start with a --- frontmatter block")

    frontmatter = yaml.safe_load(match.group(1)) or {}
    body        = match.group(2)

    if "app_name" not in frontmatter or "base_url" not in frontmatter:
        raise ValueError("frontmatter must include app_name and base_url")

    headings = list(STEP_HEADING_RE.finditer(body))
    if not headings:
        raise ValueError("no '## step_id' step headings found")

    steps = []
    for i, heading_match in enumerate(headings):
        step_id = heading_match.group(1)
        start   = heading_match.end()
        end     = headings[i + 1].start() if i + 1 < len(headings) else len(body)
        section = body[start:end].strip()

        steps.append(_parse_step(step_id, section))

    return TestCriteria(app_name=frontmatter["app_name"], base_url=frontmatter["base_url"], steps=steps)


def _parse_step(step_id: str, section: str) -> TestStep:
    lines = section.splitlines()

    instruction_lines = []
    fields: dict[str, str] = {}

    for line in lines:
        field_match = FIELD_RE.match(line.strip())
        if field_match:
            fields[field_match.group(1)] = field_match.group(2).strip()
        elif line.strip():
            instruction_lines.append(line.strip())

    if not fields.get("expected_outcome"):
        raise ValueError(f"step '{step_id}' is missing an expected_outcome field")

    return TestStep(
        step_id             = step_id,
        instruction         = " ".join(instruction_lines),
        expected_outcome    = fields["expected_outcome"],
        depends_on          = _parse_csv_field(fields.get("depends_on", "")),
        failure_class_hints = _parse_csv_field(fields.get("failure_class_hints", "")),
    )


def _parse_csv_field(raw: str) -> list[str]:
    return [item.strip() for item in raw.split(",") if item.strip()]
