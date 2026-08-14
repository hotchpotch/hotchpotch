#!/usr/bin/env python3
"""Synchronize curated public repository metadata and the profile README."""

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
DEFAULT_CONFIG = Path("repos.json")
START_MARKER = "<!-- profile-repositories:start -->"
END_MARKER = "<!-- profile-repositories:end -->"
PROFILE_TOPICS = {
    "nlp",
    "information-retrieval",
    "machine-learning",
    "data-science",
    "artificial-intelligence",
    "tools",
}
TOPICAL_TOPICS = PROFILE_TOPICS - {"tools"}
WORD_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9+.#/'-]*")


@dataclass(frozen=True)
class Repository:
    name: str
    name_with_owner: str
    url: str
    stars: int
    pushed_at: str
    is_private: bool
    topics: frozenset[str]

    @classmethod
    def from_api(cls, value: dict[str, Any]) -> "Repository":
        return cls(
            name=value["name"],
            name_with_owner=value["nameWithOwner"],
            url=value["url"],
            stars=int(value["stargazerCount"]),
            pushed_at=value.get("pushedAt") or "",
            is_private=bool(value["isPrivate"]),
            topics=frozenset(
                topic["name"] for topic in value.get("repositoryTopics") or []
            ),
        )


def run_gh(args: Sequence[str]) -> str:
    command = ["gh", *args]
    result = subprocess.run(command, check=False, text=True, capture_output=True)
    if result.returncode:
        detail = result.stderr.strip() or result.stdout.strip()
        raise RuntimeError(f"GitHub CLI failed: {' '.join(command)}\n{detail}")
    return result.stdout


def api_fields() -> str:
    return ",".join(
        (
            "name",
            "nameWithOwner",
            "url",
            "isPrivate",
            "stargazerCount",
            "pushedAt",
            "repositoryTopics",
        )
    )


def load_config(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if value.get("schema_version") != 1:
        raise RuntimeError("repos.json must use schema_version 1")
    repositories = value.get("repositories")
    if not isinstance(repositories, dict) or not repositories:
        raise RuntimeError("repos.json must contain a non-empty repositories object")
    validate_curated_metadata(repositories)
    return value


def validate_curated_metadata(repositories: dict[str, Any]) -> None:
    required = {
        "display_name",
        "emoji",
        "description",
        "japan_focused",
        "category",
        "profile_topics",
        "url",
        "stars",
        "pushed_at",
    }
    seen_emojis: dict[str, str] = {}
    for full_name, metadata in repositories.items():
        missing = required - set(metadata)
        if missing:
            raise RuntimeError(
                f"repos.json entry {full_name} is missing: {', '.join(sorted(missing))}"
            )
        description = metadata["description"]
        words = WORD_PATTERN.findall(description)
        if not 5 <= len(words) <= 10:
            raise RuntimeError(
                f"repos.json entry {full_name} must have a 5-10 word description; "
                f"found {len(words)}"
            )
        if description.count("`") % 2:
            raise RuntimeError(f"repos.json entry {full_name} has unbalanced backticks")
        emoji = metadata["emoji"]
        if emoji in seen_emojis:
            raise RuntimeError(
                f"repos.json duplicates emoji {emoji} for {seen_emojis[emoji]} and "
                f"{full_name}"
            )
        seen_emojis[emoji] = full_name
        if metadata["category"] not in {"nlp-ai", "tools"}:
            raise RuntimeError(f"repos.json entry {full_name} has an invalid category")
        topics = set(metadata["profile_topics"])
        if not topics or not topics <= PROFILE_TOPICS:
            raise RuntimeError(f"repos.json entry {full_name} has invalid profile topics")


def collect_repositories(
    owner: str, configured_names: Iterable[str]
) -> list[Repository]:
    owned_raw = run_gh(
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
            api_fields(),
        )
    )
    repositories = [Repository.from_api(item) for item in json.loads(owned_raw)]
    external_names = sorted(
        full_name
        for full_name in configured_names
        if full_name.split("/", 1)[0] != owner
    )
    for full_name in external_names:
        raw = run_gh(("repo", "view", full_name, "--json", api_fields()))
        repositories.append(Repository.from_api(json.loads(raw)))

    private_count = sum(repo.is_private for repo in repositories)
    if private_count:
        raise RuntimeError(
            f"Safety check failed: GitHub returned {private_count} private repositories"
        )
    return repositories


def validate_inventory(
    repositories: list[Repository], configured: dict[str, Any]
) -> None:
    fetched_names = {repo.name_with_owner for repo in repositories}
    configured_names = set(configured)
    missing_config = fetched_names - configured_names
    unavailable = configured_names - fetched_names
    if missing_config:
        raise RuntimeError(
            "Public repositories missing curated repos.json entries: "
            + ", ".join(sorted(missing_config))
        )
    if unavailable:
        raise RuntimeError(
            "Configured repositories were not returned as public: "
            + ", ".join(sorted(unavailable))
        )


def sync_dynamic_metadata(
    config: dict[str, Any], repositories: list[Repository]
) -> bool:
    changed = False
    configured = config["repositories"]
    for repo in repositories:
        metadata = configured[repo.name_with_owner]
        values = {
            "url": repo.url,
            "stars": repo.stars,
            "pushed_at": repo.pushed_at or None,
        }
        for key, value in values.items():
            if metadata.get(key) != value:
                metadata[key] = value
                changed = True
    return changed


def write_config(path: Path, config: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def sort_items(items: Iterable[tuple[str, dict[str, Any]]]):
    return sorted(
        items,
        key=lambda item: (-int(item[1]["stars"]), item[1]["display_name"].casefold()),
    )


def markdown_line(metadata: dict[str, Any]) -> str:
    stars = f" ({metadata['stars']} stars)" if metadata["stars"] > 10 else ""
    japan = "🇯🇵 " if metadata["japan_focused"] else ""
    return (
        f"- {metadata['emoji']} **[{metadata['display_name']}]({metadata['url']})**"
        f"{stars} - {japan}{metadata['description']}"
    )


def markdown_list(items: Iterable[tuple[str, dict[str, Any]]]) -> str:
    return "\n".join(markdown_line(metadata) for _, metadata in sort_items(items))


def five_year_cutoff(today: dt.date) -> dt.date:
    try:
        return today.replace(year=today.year - 5)
    except ValueError:
        return today.replace(year=today.year - 5, day=28)


def render_repository_block(configured: dict[str, Any], today: dt.date) -> str:
    cutoff = five_year_cutoff(today).isoformat()
    items = list(configured.items())
    topical = [item for item in items if item[1]["category"] == "nlp-ai"]
    tools = [item for item in items if item[1]["category"] == "tools"]
    active_tools = [
        item for item in tools if (item[1].get("pushed_at") or "")[:10] >= cutoff
    ]
    older = [
        item for item in tools if (item[1].get("pushed_at") or "")[:10] < cutoff
    ]
    return "\n".join(
        (
            START_MARKER,
            "## NLP, IR, ML, DS & AI",
            "",
            markdown_list(topical),
            "",
            "## Tools & Other Projects",
            "",
            markdown_list(active_tools),
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


def render_intro() -> str:
    return "\n".join(
        (
            "# Hello! 👋",
            "",
            "👤 Hi, I am **Yuichi Tateno**, a Japanese software engineer — online "
            "as **`@hotchpotch`** or **`id:secondlife`**.",
            "",
            "🔎 **Currently:** focused on **IR (information retrieval)** research "
            "and development.",
            "",
            "🌐 **My sites:** **[hotchpotch.dev(en)](https://hotchpotch.dev/)** | "
            "**[secon.dev(ja)](https://secon.dev/)**",
            "",
            '<img height="80" src="https://storage.googleapis.com/'
            'secons-site-images/other/blog_images/secon_icon_nendo.webp" '
            'alt="Robot head drooling into a puddle" /><br />',
            "<sub>My profile icon is a robot head drooling into a puddle.</sub>",
        )
    )


def update_readme(path: Path, block: str) -> None:
    current = path.read_text(encoding="utf-8")
    if START_MARKER in current or END_MARKER in current:
        if current.count(START_MARKER) != 1 or current.count(END_MARKER) != 1:
            raise RuntimeError("README has incomplete or duplicate profile markers")
        end = current.index(END_MARKER) + len(END_MARKER)
        suffix = current[end:].strip()
        updated = f"{render_intro()}\n\n{block}"
        if suffix:
            updated += f"\n\n{suffix}"
        updated += "\n"
    else:
        updated = f"{render_intro()}\n\n{block}\n"
    path.write_text(updated, encoding="utf-8")


def add_missing_topics(repositories: list[Repository], configured: dict[str, Any], apply: bool) -> int:
    changes = 0
    for repo in sorted(repositories, key=lambda item: item.name_with_owner.casefold()):
        desired = set(configured[repo.name_with_owner]["profile_topics"])
        missing = sorted(desired - repo.topics)
        if not missing:
            continue
        changes += 1
        print(f"{repo.name_with_owner}: add {', '.join(missing)}")
        if apply:
            args = ["repo", "edit", repo.name_with_owner]
            for topic in missing:
                args.extend(("--add-topic", topic))
            run_gh(args)
    return changes


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--owner", default=OWNER)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--readme", type=Path, default=Path("README.md"))
    parser.add_argument("--date", type=dt.date.fromisoformat, default=dt.date.today())
    parser.add_argument("--apply-topics", action="store_true")
    parser.add_argument("--write", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        config = load_config(args.config)
        configured = config["repositories"]
        repositories = collect_repositories(args.owner, configured)
        validate_inventory(repositories, configured)
        print(f"Verified {len(repositories)} public repositories; private: 0")
        changes = add_missing_topics(repositories, configured, args.apply_topics)
        action = "Applied" if args.apply_topics else "Planned"
        print(f"{action} topic updates for {changes} repositories")
        metadata_changed = sync_dynamic_metadata(config, repositories)
        if args.write:
            if metadata_changed:
                write_config(args.config, config)
            update_readme(
                args.readme, render_repository_block(configured, args.date)
            )
            print(f"Updated {args.config} and {args.readme}")
        else:
            message = "Metadata updates available" if metadata_changed else "Metadata current"
            print(f"{message}; pass --write to update files")
    except (OSError, RuntimeError, ValueError, json.JSONDecodeError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
