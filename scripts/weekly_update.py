#!/usr/bin/env python3
"""Safely refresh and publish the generated GitHub profile each week."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Sequence


PROJECT_ROOT = Path(__file__).resolve().parent.parent
UPDATER = PROJECT_ROOT / "scripts" / "update_profile.py"
GENERATED_FILES = ("repos.json", "README.md")
VERIFICATION_SUFFIX = "public repositories; private: 0"


def run(command: Sequence[str], *, capture: bool = False) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        check=False,
        text=True,
        capture_output=capture,
    )
    if capture:
        if result.stdout:
            print(result.stdout, end="")
        if result.stderr:
            print(result.stderr, end="", file=sys.stderr)
    if result.returncode:
        raise RuntimeError(f"command failed ({result.returncode}): {' '.join(command)}")
    return result


def output(command: Sequence[str]) -> str:
    return run(command, capture=True).stdout


def require_clean_worktree() -> None:
    if output(("git", "status", "--porcelain")):
        raise RuntimeError("working tree is not clean; refusing automated update")


def verify_preview(preview: str) -> None:
    if not any(line.endswith(VERIFICATION_SUFFIX) for line in preview.splitlines()):
        raise RuntimeError("public-only verification confirmation was not found")
    if "Planned topic updates for 0 repositories" not in preview:
        raise RuntimeError("topic changes require manual classification review")


def staged_files() -> set[str]:
    names = output(("git", "diff", "--cached", "--name-only", "--diff-filter=ACMR"))
    return set(names.splitlines())


def main() -> int:
    try:
        require_clean_worktree()
        run(("git", "pull", "--ff-only"))
        require_clean_worktree()

        preview = output((sys.executable, str(UPDATER)))
        verify_preview(preview)
        run((sys.executable, str(UPDATER), "--write"), capture=True)
        run(("git", "diff", "--check"))
        run(("git", "add", *GENERATED_FILES))

        changed = staged_files()
        if not changed:
            print("Profile metadata is already current; nothing to publish")
            return 0
        if not changed <= set(GENERATED_FILES):
            raise RuntimeError("unexpected files were staged; refusing to commit")

        run(("git", "diff", "--cached", "--", *GENERATED_FILES))
        run(("git", "commit", "-m", "Update GitHub profile repositories"))
        run(("git", "push", "origin", "HEAD"))
    except RuntimeError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
