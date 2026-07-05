import subprocess
import time
from pathlib import Path
from urllib.parse import urlparse

from qa_sentinel.config.settings import settings

WORKDIR_ROOT = Path("/tmp/qa_sentinel_fix_workdirs")
SHELL_TIMEOUT_S = 30
RESTART_WAIT_S  = 10


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


def _workdir_for(repo_url: str) -> Path:
    return WORKDIR_ROOT / Path(urlparse(repo_url).path).stem


def clone_or_reset_repo(repo_url: str) -> dict:
    """Clones the target repo into a stable local working directory (or, if
    already cloned from a prior step in this run, fetches and hard-resets to
    the latest default-branch commit). Always leaves the workdir on the real
    default branch — never assumes 'main'."""
    workdir = _workdir_for(repo_url)

    try:
        if workdir.exists() and (workdir / ".git").exists():
            _run_git(["fetch", "origin"], cwd=workdir)
            default_branch = _default_branch(workdir)
            _run_git(["checkout", default_branch], cwd=workdir)
            _run_git(["reset", "--hard", f"origin/{default_branch}"], cwd=workdir)
        else:
            workdir.parent.mkdir(parents=True, exist_ok=True)
            subprocess.run(
                ["git", "clone", _authenticated_clone_url(repo_url), str(workdir)],
                capture_output=True,
                text=True,
                check=True,
            )
    except subprocess.CalledProcessError as exc:
        return {"status": "error", "message": f"git clone/fetch failed: {exc.stderr}"}

    return {"status": "success", "workdir": str(workdir)}


def read_file(repo_url: str, path: str) -> dict:
    """Reads a file's contents from the local clone, relative to the repo root."""
    workdir = _workdir_for(repo_url)
    target = (workdir / path).resolve()

    if not target.is_relative_to(workdir.resolve()):
        return {"status": "error", "message": "Path escapes the repo root — refusing to read it."}
    if not target.exists():
        return {"status": "error", "message": f"No such file: {path}"}

    return {"status": "success", "content": target.read_text()}


def write_file(repo_url: str, path: str, content: str) -> dict:
    """Overwrites a file's contents in the local clone, relative to the repo root."""
    workdir = _workdir_for(repo_url)
    target = (workdir / path).resolve()

    if not target.is_relative_to(workdir.resolve()):
        return {"status": "error", "message": "Path escapes the repo root — refusing to write it."}

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content)
    return {"status": "success"}


def run_shell_command(repo_url: str, command: str) -> dict:
    """Runs a shell command with cwd set to the local clone's repo root.
    Used for things like `npm install`, `curl` against the live app, or
    checking what's running on a port. Times out after SHELL_TIMEOUT_S."""
    workdir = _workdir_for(repo_url)

    try:
        result = subprocess.run(
            command,
            shell=True,
            cwd=workdir,
            capture_output=True,
            text=True,
            timeout=SHELL_TIMEOUT_S,
        )
        return {
            "status"   : "success",
            "exit_code": result.returncode,
            "stdout"   : result.stdout[-4000:],
            "stderr"   : result.stderr[-2000:],
        }
    except subprocess.TimeoutExpired:
        return {"status": "error", "message": f"Command timed out after {SHELL_TIMEOUT_S}s: {command}"}


def git_commit_and_push(repo_url: str, step_id: str) -> dict:
    """Commits all changes in the local clone and force-pushes a dedicated
    qa-sentinel/fix-<step_id> branch. Only call this once you've confirmed
    (by restarting the live app and re-checking it yourself) that the fix
    actually works — this tool does not verify anything, it only commits."""
    workdir     = _workdir_for(repo_url)
    branch_name = f"qa-sentinel/fix-{step_id}"

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

    return {"status": "success", "branch_name": branch_name}


def _port_is_free(port: int) -> bool:
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", port)) != 0


def _wait_until(predicate, timeout_s: int, interval_s: float = 0.5) -> bool:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(interval_s)
    return False


def restart_live_app(port: int, repo_url: str, start_command: str) -> dict:
    """Kills whatever is listening on `port` (the live app TestRunner has been
    testing against) and restarts it from the FIXED local clone, on the same
    port, so the next TestRunner pass exercises the real fix through the
    actual running app — not a throwaway copy. Waits for the port to actually
    free up before rebinding (fuser -k only sends the signal, it does not
    wait for the process to exit), and waits for the new process to actually
    start listening before declaring success."""
    workdir = _workdir_for(repo_url)

    kill = subprocess.run(
        f"fuser -k {port}/tcp || true",
        shell=True, capture_output=True, text=True, timeout=SHELL_TIMEOUT_S,
    )
    if not _wait_until(lambda: _port_is_free(port), timeout_s=10):
        return {
            "status" : "error",
            "message": f"Port {port} was still in use {10}s after attempting to kill it.",
            "kill_output": kill.stdout + kill.stderr,
        }

    log_path = workdir / "qa_sentinel_restart.log"
    with open(log_path, "w") as log_file:
        subprocess.Popen(
            start_command,
            shell=True,
            cwd=workdir,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )

    if not _wait_until(lambda: not _port_is_free(port), timeout_s=RESTART_WAIT_S):
        boot_output = log_path.read_text() if log_path.exists() else ""
        return {
            "status" : "error",
            "message": f"App did not start listening on port {port} within {RESTART_WAIT_S}s.",
            "boot_output": boot_output[-2000:],
            "kill_output": kill.stdout + kill.stderr,
        }

    check = subprocess.run(
        f"curl -s -o /dev/null -w '%{{http_code}}' http://localhost:{port} --max-time 5",
        shell=True, capture_output=True, text=True, timeout=SHELL_TIMEOUT_S,
    )

    return {
        "status"      : "success" if check.stdout.strip() not in ("", "000") else "error",
        "http_code"   : check.stdout.strip(),
        "kill_output" : kill.stdout + kill.stderr,
        "restart_log" : str(log_path),
    }
