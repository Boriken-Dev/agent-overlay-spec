# Agent Overlay Specification

**A vendor-neutral format for agent overlays: directories of instructions, skills, tools and
environment that any agent manager can read without running anything.** Teams keep their engineering
guidance, skills and helpers in focused overlays, and each project or agent takes the ones it needs.

An overlay is a directory, and files in conventional places (`bin/`, `skills/`, `env`) work without
a manifest. `overlay.cfg` is its optional manifest: TOML unless its first line names another format,
and always static data. It declares what the overlay needs (environment variables,
path additions, a runtime, a setup step) so a consumer can decide where it can run before running
anything, and it can be pinned by one digest of the whole tree.

## Installation

Nothing to install. The format is this text, a
[JSON Schema](schemas/overlay.schema.json) of the manifest's data model, and
[conformance vectors](https://github.com/Boriken-Dev/agent-overlay-spec/tree/main/tests/vectors) any
implementation can test against.

## 30-second tour

```text
team-review/
├── overlay.cfg
├── kb/review.md
├── bin/review-check.py
└── skills/review/SKILL.md
```

```toml
name = "team-review"
description = "Review conventions for shared services."
requires = ["engineering"]
routing = ["- Service reviews → `$TEAM_REVIEW_OVERLAY_ROOT/kb/review.md`"]

[env]
REVIEW_TOKEN = { provider = "env", key = "REVIEW_TOKEN", optional = true }
```

A consumer reads this without executing anything, sets `TEAM_REVIEW_OVERLAY_ROOT`, takes the token
from its own environment (and reports that it did), and, because they are where it looks, puts
`bin/` first on `PATH` and offers the `review` skill.

## Learn more

- [Quick start](getting-started.md) and [authoring](authoring.md)
- [Format reference](spec/v0/index.md): [manifest](spec/v0/manifest.md),
  [environment](spec/v0/environment.md), [runtime and setup](spec/v0/runtime.md),
  [integrity](spec/v0/integrity.md), [security](spec/v0/security.md),
  [store and catalogs](spec/v0/catalog.md)
- [Implementations](implementations.md) and [compatibility with dotagents](compatibility.md)
- [Changelog](changelog.md)

The current edition is `0.1.0-draft`, not a 1.0 standard. [dotagents](https://github.com/jose-pr/dotagents)
is the reference implementation, not a required dependency.
