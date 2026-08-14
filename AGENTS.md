# Repository Instructions

## Purpose

This repository renders the `hotchpotch` GitHub user profile. Curated project
presentation metadata lives in `repos.json`. Repository listings are generated
by `scripts/update_profile.py` and are maintained between the
`profile-repositories` HTML comment markers.

Read `PROFILE_UPDATE.md` before changing profile classifications, GitHub
topics, the generated README section, or the update workflow.

## Mandatory privacy rule

Only public source repositories may appear in commands, logs, generated
content, documentation examples, or `README.md`.

- Collect repositories with `gh repo list --source --visibility public`.
- Request and validate `isPrivate` for every collected repository.
- Stop before printing repository data, changing topics, or writing files if
  any returned repository has `isPrivate != false`.
- Never weaken, bypass, or remove the public-only checks.
- Do not copy repository names from an unfiltered `gh` result into an issue,
  document, test fixture, log, or generated artifact.
- When reporting a privacy validation failure, report only the rejected count,
  not repository names or metadata.

An externally owned repository may be included only when the user explicitly
identifies it as a project they maintain. Add it explicitly to `repos.json`;
the updater must fetch it separately with `gh repo view` and apply the same
`isPrivate == false` validation before accepting or printing it.

## Profile classification

Use these GitHub topics for profile classification:

- `nlp`
- `information-retrieval`
- `machine-learning`
- `data-science`
- `artificial-intelligence`
- `tools`

Preserve unrelated existing topics and add only missing classification topics.
Treat each `profile_topics` list in `repos.json` as the source of truth; do not
infer profile topics from repository descriptions.

For every newly created public project, consider and set the appropriate
classification topics. Before applying curated topics in bulk, run a preview
and review every proposed classification.

Every public repository must have a curated `repos.json` entry. Descriptions
must be English and contain 5–10 words, with balanced inline-code backticks.
Use one leading emoji per repository and keep emojis unique. Set
`japan_focused` for products specifically aimed at Japanese users. Render stars
only when the current count is greater than 10. The updater synchronizes
`url`, `stars`, and `pushed_at`; humans curate all other fields.

Use the boolean `hidden` field to keep a public repository in the verified
inventory while omitting it from every README project list. Do not delete a
public repository from `repos.json` merely because it should not be displayed.
Follow the hidden-name policy documented in `PROFILE_UPDATE.md`, including for
new `secon-dev-*` repositories and names containing `test`.

Within each README category, sort repositories by GitHub stars descending and
then by display name. Keep older non-topical projects in the collapsed `<details>`
section. Preserve topical NLP/IR/ML/DS/AI projects in the combined topical list
regardless of age. Determine the five-year boundary from `pushedAt`, not
`updatedAt`; repository metadata and topic changes can modify `updatedAt`
without a code update. Treat a missing `pushedAt` value as older.

Render NLP, IR, ML, DS, and AI repositories together in one combined
`NLP, IR, ML, DS & AI` list; do not create separate subheadings for those
topics. Do not render a last-updated label in the profile.

## Required update workflow

Start with a read-only preview:

```console
python3 scripts/update_profile.py
```

The output must confirm `private: 0`. Review proposed topic changes before
running:

```console
python3 scripts/update_profile.py --apply-topics
```

Generate the README only after classification review:

```console
python3 scripts/update_profile.py --write
```

Then stage and inspect the exact generated change:

```console
git add repos.json README.md
git diff --cached -- repos.json README.md
```

Verify repository membership, emojis, descriptions, Japan flags, categories,
star ordering, the five-year boundary, and the absence of private information.
If anything is questionable, do not commit; fix it and repeat the generation
and review. Commit and push only after the staged diff has been judged correct.

Do not commit or push unless the user has requested those actions.

## Development and verification

Keep `scripts/update_profile.py` compatible with Python 3.10 or newer and use
the Python standard library unless a dependency is clearly justified.

Before handing off changes to the updater or its documentation, run:

```console
python3 scripts/update_profile.py --help
python3 scripts/update_profile.py
git diff --check
```

For README generation tests, write to a temporary copy rather than modifying
the working README unless the task explicitly includes updating `README.md`.
Do not commit `__pycache__`, `.pyc`, temporary reports, or captured GitHub API
responses.
