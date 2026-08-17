#!/usr/bin/env python3
"""Ask Codex to curate, refresh, review, and publish the GitHub profile."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


PROJECT_ROOT = Path(__file__).resolve().parent.parent
MODEL = "gpt-5.6-sol"
REASONING_EFFORT = "high"
TIMEOUT_SECONDS = 1800
JST = ZoneInfo("Asia/Tokyo")
CODEX_CANDIDATES = (
    Path("~/.nvs/default/bin/codex"),
    Path("~/.local/bin/codex"),
)
LOG_ROOT = Path("~/.local/state/hotchpotch-profile-update")


PROMPT = """\
Update this GitHub profile repository completely and publish the result.

Read and obey AGENTS.md and PROFILE_UPDATE.md before doing anything else. Follow
the required privacy-safe workflow exactly. In particular, only obtain the
repository inventory through scripts/update_profile.py, whose gh query is
public-only and validates isPrivate before printing repository data. Never use
an unfiltered gh repository listing.

Handle routine metadata changes and newly discovered public source repositories.
For each new public repository, inspect only privacy-validated public information
and curate its repos.json entry according to the repository rules: classification,
unique emoji, concise English description, Japan focus, category, and hidden-name
policy. Review every proposed topic change before applying it. Do not guess when
classification is genuinely ambiguous; leave the repository unchanged and fail
with a clear explanation instead.

Generate README.md only after classification review. Stage and inspect exactly
repos.json and README.md plus any intentional updater/documentation changes you
made. Verify all requirements from AGENTS.md, run the required checks, and inspect
the complete staged diff. If it is correct, commit with an appropriate English
message and push the current branch. If there is no change, exit successfully
without creating a commit. Do not modify unrelated files.
"""


def resolve_codex() -> Path:
    explicit = os.environ.get("CODEX_BIN", "").strip()
    if explicit:
        candidate = Path(os.path.expanduser(explicit)).resolve()
        if candidate.exists():
            return candidate
    for raw_candidate in CODEX_CANDIDATES:
        candidate = Path(os.path.expanduser(str(raw_candidate))).resolve()
        if candidate.exists():
            return candidate
    located = shutil.which("codex")
    if located:
        return Path(located).resolve()
    raise RuntimeError("codex executable not found; set CODEX_BIN or install Codex")


def run(command: list[str], *, capture: bool = False) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        check=False,
        text=True,
        capture_output=capture,
    )
    if result.returncode:
        detail = (result.stderr or result.stdout).strip() if capture else ""
        suffix = f"\n{detail}" if detail else ""
        raise RuntimeError(f"command failed ({result.returncode}): {' '.join(command)}{suffix}")
    return result


def require_clean_worktree() -> None:
    result = run(["git", "status", "--porcelain"], capture=True)
    if result.stdout:
        raise RuntimeError("working tree is not clean; refusing automated update")


def codex_command() -> list[str]:
    return [
        str(resolve_codex()),
        "exec",
        "--json",
        "--dangerously-bypass-approvals-and-sandbox",
        "--model",
        MODEL,
        "-c",
        f'model_reasoning_effort="{REASONING_EFFORT}"',
        "-C",
        str(PROJECT_ROOT),
        "-",
    ]


def coerce_output(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def append_log(stdout: str, stderr: str, exit_code: int) -> Path:
    log_root = Path(os.path.expanduser(str(LOG_ROOT)))
    log_root.mkdir(parents=True, exist_ok=True)
    log_path = log_root / f"{datetime.now(JST):%Y-%m-%d}.log"
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(f"[{datetime.now(JST):%Y-%m-%d %H:%M:%S JST}] exit_code={exit_code}\n")
        handle.write(stdout)
        if stdout and not stdout.endswith("\n"):
            handle.write("\n")
        handle.write(stderr)
        if stderr and not stderr.endswith("\n"):
            handle.write("\n")
        handle.write("\n")
    return log_path


def main() -> int:
    try:
        require_clean_worktree()
        run(["git", "pull", "--ff-only"])
        require_clean_worktree()
        try:
            result = subprocess.run(
                codex_command(),
                cwd=PROJECT_ROOT,
                input=PROMPT,
                text=True,
                capture_output=True,
                check=False,
                timeout=TIMEOUT_SECONDS,
            )
            stdout, stderr, exit_code = result.stdout, result.stderr, result.returncode
        except subprocess.TimeoutExpired as error:
            stdout = coerce_output(error.stdout)
            stderr = coerce_output(error.stderr)
            exit_code = 124
        log_path = append_log(stdout, stderr, exit_code)
        if exit_code:
            raise RuntimeError(f"Codex failed with exit code {exit_code}; see {log_path}")
        print(f"Codex profile update completed; log: {log_path}")
    except RuntimeError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
