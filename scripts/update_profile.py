#!/usr/bin/env python3
"""Update the repository sections in the hotchpotch GitHub profile README.

Repository metadata is always collected through the GitHub CLI. Private
repositories are rejected both at collection time and before any output or
GitHub mutation.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence


OWNER = "hotchpotch"
START_MARKER = "<!-- profile-repositories:start -->"
END_MARKER = "<!-- profile-repositories:end -->"

# Explicit decisions override keyword classification.
TOPIC_OVERRIDES: dict[str, set[str]] = {
    "Aground-ja_JP-translation": {"tools"},
    "baidu-translate-api-ruby": {"tools"},
    "openai-api-server-via-codex": {"tools"},
}

IR_PATTERN = re.compile(
    r"retriev|search|rag|splade|rerank|embedding|ir[ -]eval|ir[ -]dataset|"
    r"jaqket|jqara|jacwir|unir|\bfts\b|similar[ -]documents|"
    r"wikipedia.*(?:passage|pair)|全文検索",
    re.IGNORECASE,
)
NLP_PATTERN = re.compile(
    r"\bnlp\b|natural[ -]language|language[ -]model|sentence|text|translat|"
    r"mecab|vaporetto|bunkai|hiragana|question[ -]answer",
    re.IGNORECASE,
)
ML_PATTERN = re.compile(
    r"machine[ -]learning|\bml\b|classifier|classification|cross[ -]encoder|"
    r"word2vec|fineweb|trainer|pruning",
    re.IGNORECASE,
)
DS_PATTERN = re.compile(
    r"data[ -]science|dataset|kaggle|notebook|analytics|prediction|predictor",
    re.IGNORECASE,
)
AI_PATTERN = re.compile(
    r"artificial[ -]intelligence|\bai\b|\bllm\b|openai|codex|agent|gpt|"
    r"neural|deep[ -]learning",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class Repository:
    name: str
    url: str
    description: str
    stars: int
    pushed_at: str
    is_private: bool
    topics: frozenset[str]

    @classmethod
    def from_api(cls, value: dict[str, Any]) -> "Repository":
        return cls(
            name=value["name"],
            url=value["url"],
            description=(value.get("description") or "").strip(),
            stars=int(value["stargazerCount"]),
            pushed_at=value.get("pushedAt") or "",
            is_private=bool(value["isPrivate"]),
            topics=frozenset(
                topic["name"] for topic in value.get("repositoryTopics") or []
            ),
        )

    @property
    def search_text(self) -> str:
        return " ".join((self.name, self.description, *sorted(self.topics)))


def run_gh(args: Sequence[str]) -> str:
    command = ["gh", *args]
    result = subprocess.run(command, check=False, text=True, capture_output=True)
    if result.returncode:
        detail = result.stderr.strip() or result.stdout.strip()
        raise RuntimeError(f"GitHub CLI failed: {' '.join(command)}\n{detail}")
    return result.stdout


def collect_public_repositories(owner: str) -> list[Repository]:
    fields = ",".join(
        (
            "name",
            "url",
            "description",
            "isPrivate",
            "stargazerCount",
            "pushedAt",
            "repositoryTopics",
        )
    )
    raw = run_gh(
        (
            "repo",
            "list",
            owner,
            "--limit",
            "1000",
            "--source",
            "--visibility",
            "public",
            "--json",
            fields,
        )
    )
    repositories = [Repository.from_api(item) for item in json.loads(raw)]
    private = [repo for repo in repositories if repo.is_private]
    if private:
        # Do not print private repository names; only report the rejected count.
        raise RuntimeError(
            f"Safety check failed: GitHub returned {len(private)} private repositories"
        )
    return repositories


def inferred_topics(repo: Repository) -> set[str]:
    override = TOPIC_OVERRIDES.get(repo.name)
    if override is not None:
        return set(override)

    text = repo.search_text
    topics: set[str] = set()
    if IR_PATTERN.search(text):
        topics.add("information-retrieval")
    if NLP_PATTERN.search(text):
        topics.add("nlp")
    if ML_PATTERN.search(text):
        topics.add("machine-learning")
    if DS_PATTERN.search(text):
        topics.add("data-science")
    if AI_PATTERN.search(text):
        topics.add("artificial-intelligence")
    return topics or {"tools"}


def sort_repositories(repositories: Iterable[Repository]) -> list[Repository]:
    return sorted(repositories, key=lambda repo: (-repo.stars, repo.name.casefold()))


def markdown_list(repositories: Iterable[Repository]) -> str:
    lines = []
    for repo in sort_repositories(repositories):
        suffix = f" / {repo.description}" if repo.description else ""
        lines.append(f"- [{repo.name}]({repo.url}) ⭐ {repo.stars}{suffix}")
    return "\n".join(lines)


def five_year_cutoff(today: dt.date) -> dt.date:
    try:
        return today.replace(year=today.year - 5)
    except ValueError:
        return today.replace(year=today.year - 5, day=28)


def render_repository_block(repositories: list[Repository], today: dt.date) -> str:
    cutoff = five_year_cutoff(today).isoformat()
    categorized = [(repo, inferred_topics(repo)) for repo in repositories]

    topical = [
        repo
        for repo, topics in categorized
        if topics.intersection(
            {
                "nlp",
                "information-retrieval",
                "machine-learning",
                "data-science",
                "artificial-intelligence",
            }
        )
    ]
    topical_names = {repo.name for repo in topical}
    other = [repo for repo in repositories if repo.name not in topical_names]
    active = [repo for repo in other if repo.pushed_at[:10] >= cutoff]
    older = [repo for repo in other if repo.pushed_at[:10] < cutoff]

    return "\n".join(
        (
            START_MARKER,
            f"<sub>Last updated: {today.isoformat()}</sub>",
            "",
            "## NLP, IR, ML, DS & AI",
            "",
            markdown_list(topical),
            "",
            "## Tools & Other Projects",
            "",
            markdown_list(active),
            "",
            "<details>",
            "<summary><strong>Older projects</strong> — not updated in the last five years</summary>",
            "",
            markdown_list(older),
            "",
            "</details>",
            END_MARKER,
        )
    )


def update_readme(path: Path, block: str) -> None:
    current = path.read_text(encoding="utf-8").rstrip()
    if START_MARKER in current or END_MARKER in current:
        if current.count(START_MARKER) != 1 or current.count(END_MARKER) != 1:
            raise RuntimeError("README has incomplete or duplicate profile markers")
        start = current.index(START_MARKER)
        end = current.index(END_MARKER, start) + len(END_MARKER)
        updated = f"{current[:start].rstrip()}\n\n{block}\n{current[end:].lstrip()}"
    else:
        updated = f"{current}\n\n{block}\n"
    path.write_text(updated, encoding="utf-8")


def add_missing_topics(
    owner: str, repositories: list[Repository], apply: bool
) -> int:
    changes = 0
    for repo in sort_repositories(repositories):
        desired = inferred_topics(repo)
        missing = sorted(desired - repo.topics)
        if not missing:
            continue
        changes += 1
        print(f"{repo.name}: add {', '.join(missing)}")
        if apply:
            args = ["repo", "edit", f"{owner}/{repo.name}"]
            for topic in missing:
                args.extend(("--add-topic", topic))
            run_gh(args)
    return changes


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--owner", default=OWNER)
    parser.add_argument("--readme", type=Path, default=Path("README.md"))
    parser.add_argument("--date", type=dt.date.fromisoformat, default=dt.date.today())
    parser.add_argument(
        "--apply-topics",
        action="store_true",
        help="add inferred profile topics through gh repo edit",
    )
    parser.add_argument(
        "--write", action="store_true", help="update the managed README block"
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        repositories = collect_public_repositories(args.owner)
        if not repositories:
            raise RuntimeError("No public source repositories returned by GitHub")

        print(f"Verified {len(repositories)} public repositories; private: 0")
        changes = add_missing_topics(args.owner, repositories, args.apply_topics)
        action = "Applied" if args.apply_topics else "Planned"
        print(f"{action} topic updates for {changes} repositories")

        block = render_repository_block(repositories, args.date)
        if args.write:
            update_readme(args.readme, block)
            print(f"Updated {args.readme}")
        else:
            print("README unchanged; pass --write to update it")
    except (OSError, RuntimeError, ValueError, json.JSONDecodeError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
