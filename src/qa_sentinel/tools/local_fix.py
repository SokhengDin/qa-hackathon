import json
import subprocess
from pathlib import Path

from google import genai
from google.genai import types

from qa_sentinel.config.settings import settings

WORKDIR_ROOT = Path("/tmp/qa_sentinel_fix_workdirs")
MODEL = "gemini-3.5-flash"

FIX_SYSTEM_INSTRUCTION = """
You are given the contents of one or more source files from a web app, plus
evidence (console errors, failed network requests, a description of what a UI
test expected vs. what happened) showing a real bug in one of those files.

Respond with ONLY a JSON object, no markdown fences, no prose, in this exact
shape:
{"file": "<path relative to repo root>", "content": "<the FULL corrected file content>", "summary": "<one paragraph explaining the fix>"}

Make the smallest correct change that fixes the described bug. Do not rewrite
unrelated code. Preserve the file's existing style.
""".strip()


def _run_git(args: list[str], cwd: Path) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def _authenticated_clone_url(repo_url: str) -> str:
    if not settings.GITHUB_TOKEN or "github.com" not in repo_url:
        return repo_url
    return repo_url.replace("https://github.com/", f"https://{settings.GITHUB_TOKEN}@github.com/")


def _default_branch(workdir: Path) -> str:
    ref = _run_git(["symbolic-ref", "refs/remotes/origin/HEAD"], cwd=workdir)
    return ref.rsplit("/", 1)[-1]


def _clone_or_reuse(repo_url: str, workdir: Path) -> None:
    if workdir.exists() and (workdir / ".git").exists():
        _run_git(["fetch", "origin"], cwd=workdir)
        default_branch = _default_branch(workdir)
        _run_git(["checkout", default_branch], cwd=workdir)
        _run_git(["reset", "--hard", f"origin/{default_branch}"], cwd=workdir)
        return

    workdir.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["git", "clone", _authenticated_clone_url(repo_url), str(workdir)],
        capture_output=True,
        text=True,
        check=True,
    )


def _candidate_files(app_dir: Path, network_failures: list[dict]) -> list[Path]:
    candidates = []
    for pattern in ("server.js", "main.py", "app.py", "index.js"):
        match = app_dir / pattern
        if match.exists():
            candidates.append(match)
    if not candidates:
        candidates = [p for p in app_dir.glob("*.js") if p.is_file()]
    return candidates[:3]


def _propose_fix(evidence: dict, files: list[Path]) -> dict:
    client = genai.Client(api_key=settings.GEMINI_API_KEY)

    file_blobs = "\n\n".join(
        f"--- {f.name} ---\n{f.read_text()}" for f in files
    )

    prompt = (
        f"Console errors: {evidence.get('console_errors', [])}\n"
        f"Network failures: {evidence.get('network_failures', [])}\n"
        f"Model's stated intent when the failure occurred: "
        f"{evidence.get('model_stated_intent') or evidence.get('details') or evidence.get('error', '')}\n\n"
        f"Files:\n{file_blobs}"
    )

    response = client.models.generate_content(
        model=MODEL,
        contents=[types.Content(role="user", parts=[types.Part(text=prompt)])],
        config=types.GenerateContentConfig(system_instruction=FIX_SYSTEM_INSTRUCTION),
    )

    text = response.text.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    return json.loads(text)


def dispatch_fix_locally(evidence: dict, repo_url: str, app_subpath: str = "") -> dict:
    """Clones (or reuses) the target repo on this same machine, asks Gemini to
    diagnose+write a fix for the evidenced bug, applies it, and pushes a
    branch — entirely local, no Antigravity managed-agent round-trip. Used in
    place of dispatch_fix_to_antigravity when Antigravity API quota is
    unavailable.

    Returns:
        dict with status, branch_name, and a summary of the fix.
    """
    step_id = evidence.get("step_id", "unknown-step")
    branch_name = f"qa-sentinel/fix-{step_id}"
    workdir = WORKDIR_ROOT / Path(repo_url).stem

    try:
        _clone_or_reuse(repo_url, workdir)
    except subprocess.CalledProcessError as exc:
        return {"status": "error", "message": f"git clone/fetch failed: {exc.stderr}"}

    app_dir = (workdir / app_subpath) if app_subpath else workdir
    files = _candidate_files(app_dir, evidence.get("network_failures", []))

    if not files:
        return {"status": "error", "message": f"No candidate source files found under {app_dir}"}

    try:
        fix = _propose_fix(evidence, files)
    except Exception as exc:
        return {"status": "error", "message": f"Model did not return a usable fix: {exc}"}

    target_file = app_dir / fix["file"]
    if not target_file.resolve().is_relative_to(workdir.resolve()):
        return {"status": "error", "message": "Model proposed a fix outside the repo — refusing to write it."}

    target_file.write_text(fix["content"])

    try:
        try:
            _run_git(["checkout", "-b", branch_name], cwd=workdir)
        except subprocess.CalledProcessError:
            _run_git(["checkout", branch_name], cwd=workdir)
        _run_git(["add", "-A"], cwd=workdir)
        _run_git(["-c", "user.email=qa-sentinel@local", "-c", "user.name=QA Sentinel",
                  "commit", "-m", f"Fix: {step_id}"], cwd=workdir)
        _run_git(["push", "--force", "origin", branch_name], cwd=workdir)
    except subprocess.CalledProcessError as exc:
        return {"status": "error", "message": f"git commit/push failed: {exc.stderr}"}

    return {
        "status": "success",
        "branch_name": branch_name,
        "output_text": fix.get("summary", "Fix applied."),
    }
