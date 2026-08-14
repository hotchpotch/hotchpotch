# GitHub Profile Update Guide

This repository is the source of the `hotchpotch` GitHub profile page.
`repos.json` stores curated presentation metadata, while
`scripts/update_profile.py` synchronizes public GitHub facts and regenerates
`README.md`.

## Non-negotiable privacy rule

Private repositories must never be accepted into the profile inventory,
printed, or written to `README.md`.

The updater enforces this twice:

1. It calls `gh repo list` with both `--source` and `--visibility public`.
2. It verifies that every returned item has `isPrivate == false` before it
   prints repository data, changes topics, or writes the README.

If GitHub returns even one private item, the script exits without making any
changes and does not print the private repository name.

## Requirements

- Python 3.10 or newer
- GitHub CLI (`gh`)
- An authenticated `gh` session with permission to edit repository topics

Check authentication before an update:

```console
gh auth status
```

## Classification

Each public source repository receives one or more profile topics:

- `nlp`
- `information-retrieval`
- `machine-learning`
- `data-science`
- `artificial-intelligence`
- `tools`

Existing GitHub topics are preserved. The updater only adds missing profile
topics listed in each repository's `profile_topics` field in `repos.json`.

Public repositories maintained outside the `hotchpotch` account must be added
explicitly to `repos.json`. Each external entry is fetched separately with
`gh repo view` and must pass the same `isPrivate == false` check before it is
accepted. The current external NLP project is `hakari-bench/hakari-bench`.

Whenever a new public project is created, add a curated `repos.json` entry and
consider which profile topics best describe it. The updater intentionally
fails when a public repository has no curated entry, preventing unreviewed
GitHub descriptions from reaching the profile.

Each `repos.json` entry contains:

- `display_name`, one distinctive `emoji`, and a curated English `description`
- `japan_focused`, which adds 🇯🇵 before the description
- `category` and `profile_topics`
- synchronized `url`, `stars`, and `pushed_at` values

Descriptions must contain 5–10 English words. Inline code such as `` `Rust` ``
is allowed. Emojis must be unique. Repository lines use this format:

```text
{emoji} {linked display name} ({N stars}, when N > 10) - {🇯🇵 when applicable} {description}
```

Repository lists are sorted by GitHub stars descending, then by display name.
Star counts of 10 or fewer are omitted from the rendered README.

The README sections are:

1. NLP, IR, ML, DS & AI, as one combined list sorted by stars
2. Tools & Other Projects
3. Older projects, collapsed in a `<details>` element

Place `<sub>Last updated: YYYY-MM-dd</sub>` immediately above the
`NLP, IR, ML, DS & AI` heading.

The older-project boundary is five years before the update date and is measured
from GitHub's `pushedAt` value (the last code push). Do not use `updatedAt` for
this rule because metadata changes such as adding a topic also change that
value. Topic-based NLP/IR/ML/DS/AI projects remain in their topical sections
even when older. A repository that has never received a code push has no
`pushedAt` value and is treated as an older project.

## Update procedure

Run a preview first. This fetches current public metadata, verifies privacy, and
prints the topics that would be added. It does not change GitHub or the README.

```console
python3 scripts/update_profile.py
```

Review the proposed classifications. If a repository is missing or
misclassified, edit `repos.json`, rerun the preview, and review it again.

Apply missing GitHub topics:

```console
python3 scripts/update_profile.py --apply-topics
```

Synchronize stars and push dates in `repos.json`, then regenerate `README.md`:

```console
python3 scripts/update_profile.py --write
```

The first write appends `<!-- profile-repositories:start -->` and
`<!-- profile-repositories:end -->` after the existing profile content. Later
runs replace only the content between those markers.

Inspect the result before committing:

```console
git diff -- README.md repos.json PROFILE_UPDATE.md scripts/update_profile.py
```

For a reproducible preview with a specific date:

```console
python3 scripts/update_profile.py --date 2026-08-14
```

## Suggested schedule

Run the preview and README update monthly. A scheduled GitHub Actions workflow
should use the same script, grant only the repository permissions needed to
read public metadata and edit this profile repository, and retain the strict
public-only checks. Topic updates should remain an explicit maintenance step
unless the workflow has been carefully reviewed for cross-repository write
permissions.

For every periodic update, follow this process:

1. Run the updater according to this guide and inspect its complete output.
2. Confirm that the public-only verification passed and review every proposed
   topic change.
3. Regenerate `repos.json` and `README.md`, then stage both with
   `git add repos.json README.md`.
4. Inspect the staged diff with `git diff --cached -- repos.json README.md`.
   Check repository membership, emoji uniqueness, 5–10 word English
   descriptions, Japan flags, categories, star ordering, older project
   boundary, and update date. In particular, verify that no private repository
   or private information appears.
5. If any problem is found, do not commit. Fix the classification or updater,
   regenerate the README, stage it again, and repeat the review.
6. Only after determining that the staged result is correct, stage any other
   intentional updater changes, commit them, and push the commit to publish the
   profile update.

For example:

```console
python3 scripts/update_profile.py
python3 scripts/update_profile.py --write
git add repos.json README.md
git diff --cached -- repos.json README.md
git commit -m "Update GitHub profile repositories"
git push
```

After every automated or manual run, confirm that the log contains a line in
this form before accepting the generated README:

```text
Verified N public repositories; private: 0
```
