# Agent Overlay Specification (AOS)

[![Version](https://img.shields.io/github/v/tag/Boriken-Dev/agent-overlay-spec?include_prereleases&label=edition)](https://github.com/Boriken-Dev/agent-overlay-spec/tags)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](https://github.com/Boriken-Dev/agent-overlay-spec/blob/main/LICENSE)
[![Docs](https://img.shields.io/badge/docs-latest-blue.svg)](https://boriken-dev.github.io/agent-overlay-spec/)
[![CI](https://img.shields.io/github/actions/workflow/status/Boriken-Dev/agent-overlay-spec/test.yml)](https://github.com/Boriken-Dev/agent-overlay-spec/actions/workflows/test.yml)

**A vendor-neutral format for agent overlays: directories of instructions, skills, tools and
environment that any agent manager can read without running anything.** An overlay declares what it
needs (environment, path additions, setup, a runtime) as static data in `OVERLAY.md` or `overlay.cfg`, and a
consumer pins the whole tree by one digest. See the
[documentation](https://boriken-dev.github.io/agent-overlay-spec/).

> **Status:** AOS `0.1.0-draft` is a development specification, open for review. It is not a 1.0
> standard, and fields marked **Proposed** have no implementation yet.

## Features

- **A directory is an overlay.** The manifest is optional; files keep their relative paths, and
  conventional ones (`bin/` on `PATH`, `skills/`, `env`, `setup.sh`) take effect by default.
- **One file, or a document of its own.** `OVERLAY.md` holds the manifest as front matter and the
  overlay's context as its body, as `SKILL.md` does for a skill; `overlay.cfg` holds the same fields for
  overlays written by tools. Both in one overlay is refused.
- **One data model, several syntaxes.** Front matter is YAML and `overlay.cfg` is TOML unless a first
  line names another format (`#!json`, `#!toml`, `#!yaml`). Every reader reads TOML and a restricted
  YAML; nothing is guessed from content.
- **Skills from where they live.** `skills` lists what an overlay offers: bundled, a name its consumer's
  catalogs resolve, or a source with a pin, like `requirements.txt` without carrying copies.
- **Static by rule.** Reading a manifest never executes, includes or interpolates anything, so a
  small parser in any language reads it.
- **Environment as data.** Plain values, paths inside the overlay, secret references by name and
  provider (never a value), env files, and `PATH`-style additions with a defined separator.
- **Setup and runtime, declared.** A named interpreter per OS, a timeout with a default, a network
  need, a minimum runtime version and a lockfile; packages from `lib/python/requirements.txt` and
  `lib/node/package.json` in shared, named or isolated environments; setup told its phase on
  every add, sync and removal.
- **Hooks that only tighten.** `hook.py` or a `hooks` table runs at a session's events (before the
  environment, a session's start and end, a prompt, a tool call), adds context, blocks or denies, and
  never approves; off until the user allows it at the overlay's digest.
- **Integrity.** A canonical tree digest with test vectors, a source and pin form, and weakenings
  an implementation must report rather than apply silently.
- **Conformance vectors as data**, so implementations in any language test against the same files.

## Installation

Nothing to install. Read the [specification](https://github.com/Boriken-Dev/agent-overlay-spec/blob/main/SPEC.md),
validate a parsed manifest against the
[JSON Schema](https://boriken-dev.github.io/agent-overlay-spec/schemas/overlay.schema.json), and run
the [vectors](https://github.com/Boriken-Dev/agent-overlay-spec/tree/main/tests/vectors) against
your implementation.

## Quick start

The smallest overlay is a directory with one file, and a `bin/` in it goes on `PATH` with no
manifest. Add `OVERLAY.md` when you want metadata or declarations, and what the agent should read
first as its body:

```markdown
---
name: review-basics
description: Shared code review guidance.
routing:
  - Reviewing code → `$REVIEW_BASICS_OVERLAY_ROOT/kb/review.md`
---
Review the change for what it does, not how it is written.
```

Or write the manifest as `overlay.cfg`, TOML by default:

```toml
name = "review-basics"
description = "Shared code review guidance."
routing = ["- Reviewing code → `$REVIEW_BASICS_OVERLAY_ROOT/kb/review.md`"]
```

The same manifest in JSON:

```json
#!json
{
  "name": "review-basics",
  "description": "Shared code review guidance.",
  "routing": ["- Reviewing code → `$REVIEW_BASICS_OVERLAY_ROOT/kb/review.md`"]
}
```

## API overview

| Part | What it defines |
| --- | --- |
| [Package](https://boriken-dev.github.io/agent-overlay-spec/spec/v0/package/) | The directory, names and paths |
| [Manifest](https://boriken-dev.github.io/agent-overlay-spec/spec/v0/manifest/) | `OVERLAY.md` and `overlay.cfg`: the split, format selection, restricted YAML, data model, static reading, fields |
| [Environment](https://boriken-dev.github.io/agent-overlay-spec/spec/v0/environment/) | Values, secret references, env files, path additions, root variables, env scripts |
| [Runtime and setup](https://boriken-dev.github.io/agent-overlay-spec/spec/v0/runtime/) | Interpreters, per-OS setup, timeouts, network, runtimes and lockfiles |
| [Integrity](https://boriken-dev.github.io/agent-overlay-spec/spec/v0/integrity/) | The tree digest, pins and verification |
| [Store and catalogs](https://boriken-dev.github.io/agent-overlay-spec/spec/v0/catalog/) | Informational fields and icons for a store, catalogs of many overlays, and what a store may believe |
| [Security](https://boriken-dev.github.io/agent-overlay-spec/spec/v0/security/) | Trust, weakenings and what must be reported |
| [Conformance](https://boriken-dev.github.io/agent-overlay-spec/spec/v0/conformance/) | Classes of implementation and the vectors |

[dotagents](https://github.com/jose-pr/dotagents) is the reference implementation. AOS does not
require it, Git, Python or any agent product.

## Development

```bash
python -m venv .venv
.venv/bin/python -m pip install -r requirements-test.txt -r requirements-docs.txt
.venv/bin/python -m pytest
.venv/bin/mkdocs build --strict
```

The tests validate every example and fixture against the schema and run the conformance vectors
through a small reference reader in `tests/`.

### Releasing

Editions follow [Semantic Versioning](https://semver.org/), recorded in
[`CHANGELOG.md`](https://github.com/Boriken-Dev/agent-overlay-spec/blob/main/CHANGELOG.md). Pushing a
`v*` tag runs the tests and a strict docs build, then creates a GitHub release from the tag's
changelog section; no package is published. For a final edition the release then dispatches the
docs workflow at the tag, which owns every Pages deploy.

## License

MIT — see [LICENSE](https://github.com/Boriken-Dev/agent-overlay-spec/blob/main/LICENSE).
